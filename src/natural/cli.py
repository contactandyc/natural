# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import difflib
import graphlib
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Dict, Set
import typer
from rich.console import Console
from rich.syntax import Syntax

from natural.normalizer.parser import NaturalParser
from natural.normalizer.lowering import SemanticLoweringPass
from natural.normalizer.workspace import Workspace
from natural.ir.serializer import serialize_to_yaml
from natural.codegen.python_emitter import PythonEmitter
from natural.codegen.orm_emitter import ORMEmitter

app = typer.Typer(
    name="natural",
    help="Software AG Natural to Semantic Intermediate Representation (IR) compiler.",
)
console = Console()


def write_if_changed(file_path: Path, new_content: str, show_diff: bool) -> bool:
    """
    Compares new_content against the file on disk.
    Returns True if the file was written (new or updated), False if unchanged.
    Prints Git-style unified diffs if requested.
    """
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


@app.command()
def parse(
        source_file: Path = typer.Argument(..., help="Path to the Natural source file (.nsp, .nsn, .nss)"),
        include_dir: Optional[List[Path]] = typer.Option(None, "--include-dir", "-I", help="Directories to search for .NSA, .DDM, and copycodes"),
        output: Optional[Path] = typer.Option(None, "--output", "-o", help="Optional output file path"),
        display: bool = typer.Option(True, "--display/--no-display", help="Print the generated output to console"),
        emit_python: bool = typer.Option(False, "--emit-python", "-p", help="Generate and print Python source code"),
        emit_main: bool = typer.Option(False, "--emit-main", help="Include runnable __main__ block in emitted Python"),
        emit_orm: bool = typer.Option(False, "--emit-orm", help="Generate SQLAlchemy ORM models from DDMs"),
):
    """Parses a single Natural source program (Debugging)."""
    if not source_file.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {source_file}")
        raise typer.Exit(code=1)

    workspace = Workspace(include_dirs=include_dir or [])
    parser = NaturalParser()

    try:
        ir0_module = parser.parse_file(source_file)
        semantic_pass = SemanticLoweringPass(ir0_module, workspace=workspace)
        ir1_module = semantic_pass.lower()

        if emit_orm:
            ddms = [area for key, area in workspace._cache.items() if key.startswith("DDM_")]
            orm_emitter = ORMEmitter(ddms)
            result_text = orm_emitter.generate()
            lang = "python"
        elif emit_python:
            emitter = PythonEmitter(ir1_module)
            result_text = emitter.generate(emit_main=emit_main or source_file.suffix.lower() == ".nsp")
            lang = "python"
        else:
            result_text = serialize_to_yaml(ir1_module)
            lang = "yaml"

        if output:
            output.write_text(result_text, encoding="utf-8")
            console.print(f"[green]Successfully written output to:[/green] {output}")
        if display or not output:
            console.print(Syntax(result_text, lang, theme="monokai", line_numbers=True))

    except Exception as e:
        console.print(f"[bold red]Parsing failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def build(
        workspace_dir: Path = typer.Argument(..., help="Path to the Natural workspace directory"),
        show_diff: bool = typer.Option(False, "--diff", help="Show Git-style diffs for output files that have changed"),
        emit_main: bool = typer.Option(True, "--emit-main/--no-emit-main", help="Emit runnable if __name__ == '__main__' into .nsp outputs"),
):
    """Compiles an entire workspace, generates Python/ORM to a build/ directory, and diffs file changes."""
    if not workspace_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Workspace directory not found: {workspace_dir}")
        raise typer.Exit(code=1)

    build_dir = workspace_dir / "build"
    ir0_dir = build_dir / "ir0"
    ir1_dir = build_dir / "ir1"
    py_dir = build_dir / "python"

    for d in [ir0_dir, ir1_dir, py_dir]:
        d.mkdir(parents=True, exist_ok=True)

    workspace = Workspace(include_dirs=[workspace_dir])
    parser = NaturalParser()

    expected_files: Set[Path] = set()
    dependency_graph: Dict[str, Set[str]] = {}
    file_map: Dict[str, Path] = {}

    for file_path in workspace_dir.glob("*.*"):
        ext = file_path.suffix.lower()
        if ext not in (".nsp", ".nsn", ".nsa", ".ddm"):
            continue

        module_name = file_path.stem.upper()
        file_map[module_name] = file_path
        dependency_graph[module_name] = set()

        if ext == ".ddm":
            workspace.get_ddm(module_name)
        elif ext == ".nsa":
            workspace.get_data_area(module_name, scope=None)
        else:
            try:
                ir0 = parser.parse_file(file_path)
                for area in ir0.data_areas:
                    dependency_graph[module_name].add(area.name.upper())
                for stmt in ir0.body:
                    if getattr(stmt, "statement_type", "") == "FIND":
                        dependency_graph[module_name].add(stmt.view_name.upper())
            except Exception:
                pass

    try:
        sorter = graphlib.TopologicalSorter(dependency_graph)
        build_order = list(sorter.static_order())
    except graphlib.CycleError as e:
        console.print(f"[bold red]Circular Dependency Detected:[/bold red] {e}")
        raise typer.Exit(code=1)

    console.print(f"\n[bold cyan]Build Order:[/bold cyan] {' -> '.join(build_order)}\n")

    for module_name in build_order:
        if module_name not in file_map:
            continue

        file_path = file_map[module_name]
        ext = file_path.suffix.lower()

        if ext not in (".nsp", ".nsn"):
            continue

        console.print(f"Compiling [bold]{module_name}[/bold]...")
        source_text = file_path.read_text(encoding="utf-8")

        try:
            ir0 = parser.parse(source_text, module_name=module_name)
            ir0_out = ir0_dir / f"{module_name.lower()}.yaml"
            expected_files.add(ir0_out)

            if write_if_changed(ir0_out, serialize_to_yaml(ir0), show_diff):
                console.print(f"  [green]↳ Updated:[/green] {ir0_out.relative_to(workspace_dir)}")
            else:
                console.print(f"  [dim]↳ Unchanged:[/dim] {ir0_out.relative_to(workspace_dir)}")

            semantic_pass = SemanticLoweringPass(ir0, workspace=workspace)
            ir1 = semantic_pass.lower()
            ir1_out = ir1_dir / f"{module_name.lower()}.yaml"
            expected_files.add(ir1_out)

            if write_if_changed(ir1_out, serialize_to_yaml(ir1), show_diff):
                console.print(f"  [green]↳ Updated:[/green] {ir1_out.relative_to(workspace_dir)}")
            else:
                console.print(f"  [dim]↳ Unchanged:[/dim] {ir1_out.relative_to(workspace_dir)}")

            py_emitter = PythonEmitter(ir1)
            # Standalone programs (.nsp) get __main__ block when emit_main is True
            should_emit_main = emit_main and (ext == ".nsp")
            py_source = py_emitter.generate(emit_main=should_emit_main)
            py_out = py_dir / f"{module_name.lower()}.py"
            expected_files.add(py_out)

            if write_if_changed(py_out, py_source, show_diff):
                console.print(f"  [green]↳ Updated:[/green] {py_out.relative_to(workspace_dir)}")
            else:
                console.print(f"  [dim]↳ Unchanged:[/dim] {py_out.relative_to(workspace_dir)}")

        except Exception as e:
            console.print(f"  [bold red]↳ Failed:[/bold red] {e}")

    ddms = [area for key, area in workspace._cache.items() if key.startswith("DDM_")]
    if ddms:
        console.print(f"\nCompiling [bold]TARGET_ORM[/bold]...")
        orm_emitter = ORMEmitter(ddms)
        orm_source = orm_emitter.generate()
        orm_out = py_dir / "target_orm.py"
        expected_files.add(orm_out)

        if write_if_changed(orm_out, orm_source, show_diff):
            console.print(f"  [green]↳ Updated:[/green] {orm_out.relative_to(workspace_dir)}")
        else:
            console.print(f"  [dim]↳ Unchanged:[/dim] {orm_out.relative_to(workspace_dir)}")

    console.print("\n[dim]Running workspace cleanup...[/dim]")
    for d in [ir0_dir, ir1_dir, py_dir]:
        for file_path in d.glob("*"):
            if file_path.is_file() and file_path not in expected_files:
                file_path.unlink()
                console.print(f"  [yellow]↳ Removed obsolete file:[/yellow] {file_path.relative_to(workspace_dir)}")

    legacy_state = build_dir / ".compiler_state.json"
    if legacy_state.exists():
        legacy_state.unlink()
        console.print(f"  [yellow]↳ Removed legacy state file:[/yellow] {legacy_state.relative_to(workspace_dir)}")

    console.print(f"\n[bold green]Workspace build complete.[/bold green] Output saved to {build_dir}")


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
        ctx: typer.Context,
        workspace_dir: Path = typer.Argument(..., help="Path to workspace directory"),
        module_name: str = typer.Argument(..., help="Name of executable program (e.g. EOM)"),
):
    """Executes a compiled Python module, forwarding any extra options directly to its CLI."""
    target_py = workspace_dir / "build" / "python" / f"{module_name.lower()}.py"
    if not target_py.exists():
        console.print(f"[bold yellow]Module not found at {target_py}. Building workspace first...[/bold yellow]")
        build(workspace_dir, show_diff=False, emit_main=True)

    if not target_py.exists():
        console.print(f"[bold red]Error:[/bold red] Failed to generate {target_py}")
        raise typer.Exit(code=1)

    cmd = [sys.executable, str(target_py)] + ctx.args
    subprocess.run(cmd)


if __name__ == "__main__":
    app()
