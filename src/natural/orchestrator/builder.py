# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import difflib
import graphlib
from pathlib import Path
from typing import Dict, List, Set
from rich.console import Console
from rich.syntax import Syntax

from natural.codegen.target import get_target
from natural.ir.models import SubroutineDefinition
from natural.ir.serializer import serialize_to_yaml
from natural.normalizer.lowering import SemanticLoweringPass
from natural.normalizer.pass1_parser import Pass1Parser
from natural.normalizer.pass2_dispatcher import Pass2Dispatcher
from natural.normalizer.workspace import Workspace

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


class ProjectBuilder:
    def __init__(self, workspace_dir: Path, target: str = "python"):
        self.workspace_dir = workspace_dir
        self.target_name = target
        self.backend = get_target(target)
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

                    def extract_deps(stmts):
                        deps = set()
                        for s in stmts:
                            st = getattr(s, "statement_type", "")
                            if st in ("FIND", "READ", "HISTOGRAM"):
                                if getattr(s, "view_name", None):
                                    deps.add(s.view_name.upper())
                            elif st == "CALLNAT":
                                if getattr(s, "subprogram_name", None):
                                    deps.add(s.subprogram_name.upper())
                            elif st == "FETCH":
                                if getattr(s, "program_name", None):
                                    deps.add(s.program_name.upper())
                            elif st == "MOVE_BY_NAME":
                                for cand in (getattr(s, "source", "").upper(), getattr(s, "target", "").upper()):
                                    clean_cand = cand.replace("#", "")
                                    if clean_cand in self.file_map:
                                        deps.add(clean_cand)
                            for sub in ("body", "then_branch", "else_branch", "on_empty"):
                                if hasattr(s, sub):
                                    deps.update(extract_deps(getattr(s, sub)))
                            if hasattr(s, "branches"):
                                for b in s.branches:
                                    if hasattr(b, "statements"):
                                        deps.update(extract_deps(b.statements))
                            if hasattr(s, "none_branch"):
                                deps.update(extract_deps(s.none_branch))
                        return deps

                    all_stmts = list(ir0.body)
                    for sub_item in ir0.subroutines.values():
                        if isinstance(sub_item, SubroutineDefinition):
                            all_stmts.extend(sub_item.body)
                            if sub_item.on_error:
                                all_stmts.extend(sub_item.on_error.body)
                        else:
                            all_stmts.extend(sub_item)
                    for fn_def in ir0.functions.values():
                        all_stmts.extend(fn_def.body)

                    self.dependency_graph[module_name].update(extract_deps(all_stmts))

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
        target_dir = build_dir / self.backend.target_name

        for d in [ir0_dir, ir1_dir, target_dir]:
            d.mkdir(parents=True, exist_ok=True)

        expected_files: Set[Path] = set()
        console.print(f"\n[bold cyan]Build Order ({self.backend.target_name}):[/bold cyan] {' -> '.join(build_order)}\n")

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

                should_emit_main = emit_main and (ext == ".nsp")
                target_source = self.backend.emit_module(ir1, emit_main=should_emit_main)
                target_out = target_dir / f"{module_name.lower()}{self.backend.file_extension}"
                expected_files.add(target_out)
                write_if_changed(target_out, target_source, show_diff)

            except Exception as e:
                console.print(f"  [bold red]↳ Failed:[/bold red] {e}")

        # Emit target schemas / ORM models
        ddms = [area for key, area in self.workspace._cache.items() if key.startswith("DDM_")]
        schema_outputs = self.backend.emit_schema(ddms)
        for schema_relpath, schema_content in schema_outputs.items():
            schema_out = target_dir / schema_relpath
            expected_files.add(schema_out)
            write_if_changed(schema_out, schema_content, show_diff)

        # Emit target runtime libraries
        runtime_outputs = self.backend.emit_runtime()
        for runtime_relpath, runtime_content in runtime_outputs.items():
            runtime_out = target_dir / runtime_relpath
            runtime_out.parent.mkdir(parents=True, exist_ok=True)
            expected_files.add(runtime_out)
            write_if_changed(runtime_out, runtime_content, show_diff)

        # Clean stale files in the target directory
        for file_path in target_dir.rglob("*"):
            if file_path.is_file() and file_path not in expected_files:
                file_path.unlink()

        for file_path in ir0_dir.glob("*"):
            if file_path.is_file() and file_path not in expected_files:
                file_path.unlink()

        for file_path in ir1_dir.glob("*"):
            if file_path.is_file() and file_path not in expected_files:
                file_path.unlink()

        console.print(f"\n[bold green]Workspace build complete.[/bold green] Output saved to {build_dir}")
