# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import difflib
import graphlib
from pathlib import Path
from typing import Dict, Set, List
from rich.console import Console
from rich.syntax import Syntax

from natural.normalizer.pass1_parser import Pass1Parser
from natural.normalizer.pass2_dispatcher import Pass2Dispatcher
from natural.normalizer.lowering import SemanticLoweringPass
from natural.normalizer.workspace import Workspace
from natural.ir.serializer import serialize_to_yaml
from natural.codegen.python_emitter import PythonEmitter
from natural.codegen.orm_emitter import ORMEmitter

console = Console()


def write_if_changed(file_path: Path, new_content: str, show_diff: bool) -> bool:
    if file_path.exists():
        old_content = file_path.read_text(encoding="utf-8")
        if old_content == new_content:
            return False

        if show_diff:
            diff = difflib.unified_diff(
                old_content.splitlines(),
                new_content.splitlines(),
                fromfile=f"a/{file_path.name}",
                tofile=f"b/{file_path.name}",
                lineterm="",
            )
            diff_text = "\n".join(diff)
            if diff_text:
                console.print(f"\n[bold yellow]Differences for {file_path.name}:[/bold yellow]")
                console.print(Syntax(diff_text, "diff", theme="monokai", background_color="default"))
    else:
        if show_diff:
            console.print(f"\n[bold green]New file created:[/bold green] {file_path.name}")

    file_path.write_text(new_content, encoding="utf-8")
    return True


FALLBACK_ORM_SOURCE = """from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def __getattr__(name):
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    cls_dict = {
        '__tablename__': name.lower(),
        'id': Column('id', Integer, primary_key=True, autoincrement=True),
        'name': Column('name', String(255), default=""),
    }
    return type(name, (Base,), cls_dict)
"""


class ProjectBuilder:
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.workspace = Workspace(include_dirs=[workspace_dir])
        self.parser = Pass1Parser(self.workspace)
        self.dispatcher = Pass2Dispatcher()
        self.dependency_graph: Dict[str, Set[str]] = {}
        self.file_map: Dict[str, Path] = {}

    def scan_workspace(self):
        for file_path in self.workspace_dir.glob("*.*"):
            ext = file_path.suffix.lower()
            if ext not in (".nsp", ".nsn", ".nsa", ".ddm"):
                continue

            module_name = file_path.stem.upper()
            self.file_map[module_name] = file_path
            self.dependency_graph[module_name] = set()

            if ext == ".ddm":
                self.workspace.get_ddm(module_name)
            elif ext == ".nsa":
                self.workspace.get_data_area(module_name, scope=None)
            else:
                try:
                    pass1_ast = self.parser.parse_file(file_path)
                    ir0 = self.dispatcher.lower_module(pass1_ast)
                    for area in ir0.data_areas:
                        if area.name.upper() not in ("INLINE_LOCAL", "INLINE_PARAMETER", "INLINE_GLOBAL"):
                            self.dependency_graph[module_name].add(area.name.upper())
                    for stmt in ir0.body:
                        stmt_type = getattr(stmt, "statement_type", "")
                        if stmt_type in ("FIND", "READ"):
                            self.dependency_graph[module_name].add(stmt.view_name.upper())
                        elif stmt_type == "CALLNAT":
                            self.dependency_graph[module_name].add(stmt.subprogram_name.upper())
                        elif stmt_type == "MOVE_BY_NAME":
                            for cand in (stmt.source.upper(), stmt.target.upper()):
                                clean_cand = cand.replace("#", "")
                                if clean_cand in self.file_map:
                                    self.dependency_graph[module_name].add(clean_cand)
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not extract dependencies for {module_name}: {e}[/yellow]")

    def get_build_order(self) -> List[str]:
        sorter = graphlib.TopologicalSorter(self.dependency_graph)
        try:
            return list(sorter.static_order())
        except graphlib.CycleError as e:
            console.print(f"[bold red]Circular Dependency Detected:[/bold red] {e}")
            raise

    def compile_workspace(self, show_diff: bool = False, emit_main: bool = True):
        self.scan_workspace()
        build_order = self.get_build_order()

        build_dir = self.workspace_dir / "build"
        ir0_dir = build_dir / "ir0"
        ir1_dir = build_dir / "ir1"
        py_dir = build_dir / "python"

        for d in [ir0_dir, ir1_dir, py_dir]:
            d.mkdir(parents=True, exist_ok=True)

        expected_files: Set[Path] = set()
        console.print(f"\n[bold cyan]Build Order:[/bold cyan] {' -> '.join(build_order)}\n")

        for module_name in build_order:
            if module_name not in self.file_map:
                continue

            file_path = self.file_map[module_name]
            ext = file_path.suffix.lower()
            if ext not in (".nsp", ".nsn"):
                continue

            console.print(f"Compiling [bold]{module_name}[/bold]...")
            source_text = file_path.read_text(encoding="utf-8")

            try:
                pass1_ast = self.parser.parse(source_text, module_name=module_name)
                ir0 = self.dispatcher.lower_module(pass1_ast)

                ir0_out = ir0_dir / f"{module_name.lower()}.yaml"
                expected_files.add(ir0_out)
                write_if_changed(ir0_out, serialize_to_yaml(ir0), show_diff)

                semantic_pass = SemanticLoweringPass(ir0, workspace=self.workspace)
                ir1 = semantic_pass.lower()
                ir1_out = ir1_dir / f"{module_name.lower()}.yaml"
                expected_files.add(ir1_out)
                write_if_changed(ir1_out, serialize_to_yaml(ir1), show_diff)

                py_emitter = PythonEmitter(ir1)
                should_emit_main = emit_main and (ext == ".nsp")
                py_source = py_emitter.generate(emit_main=should_emit_main)
                py_out = py_dir / f"{module_name.lower()}.py"
                expected_files.add(py_out)
                write_if_changed(py_out, py_source, show_diff)

            except Exception as e:
                console.print(f"  [bold red]↳ Failed:[/bold red] {e}")

        orm_out = py_dir / "target_orm.py"
        expected_files.add(orm_out)

        ddms = [area for key, area in self.workspace._cache.items() if key.startswith("DDM_")]
        if ddms:
            console.print(f"\nCompiling [bold]TARGET_ORM[/bold]...")
            orm_emitter = ORMEmitter(ddms)
            orm_source = orm_emitter.generate()
        else:
            orm_source = FALLBACK_ORM_SOURCE

        write_if_changed(orm_out, orm_source, show_diff)

        for d in [ir0_dir, ir1_dir, py_dir]:
            for file_path in d.glob("*"):
                if file_path.is_file() and file_path not in expected_files:
                    file_path.unlink()

        console.print(f"\n[bold green]Workspace build complete.[/bold green] Output saved to {build_dir}")
