# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.syntax import Syntax

from natural.normalizer.pass1_parser import Pass1Parser
from natural.normalizer.pass2_dispatcher import Pass2Dispatcher
from natural.normalizer.lowering import SemanticLoweringPass
from natural.normalizer.workspace import Workspace
from natural.ir.serializer import serialize_to_yaml
from natural.codegen.python_emitter import PythonEmitter
from natural.codegen.orm_emitter import ORMEmitter
from natural.orchestrator.builder import ProjectBuilder

app = typer.Typer(
    name="natural",
    help="Software AG Natural to Semantic Intermediate Representation (IR) compiler.",
)
console = Console()


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
    if not source_file.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {source_file}")
        raise typer.Exit(code=1)

    workspace = Workspace(include_dirs=include_dir or [])
    try:
        parser = Pass1Parser(workspace)
        dispatcher = Pass2Dispatcher()

        pass1_module = parser.parse_file(source_file)
        ir0_module = dispatcher.lower_module(pass1_module)

        semantic_pass = SemanticLoweringPass(ir0_module, workspace=workspace)
        ir1_module = semantic_pass.lower()

        if emit_orm:
            ddms = [area for key, area in workspace._cache.items() if key.startswith("DDM_")]
            if ddms:
                orm_emitter = ORMEmitter(ddms)
                result_text = orm_emitter.generate()
            else:
                result_text = (
                    "from sqlalchemy.orm import declarative_base\n"
                    "Base = declarative_base()\n\n"
                    "def __getattr__(name):\n"
                    "    return type(name, (Base,), {'__tablename__': name.lower()})\n"
                )
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
    if not workspace_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Workspace directory not found: {workspace_dir}")
        raise typer.Exit(code=1)

    builder = ProjectBuilder(workspace_dir)
    builder.compile_workspace(show_diff=show_diff, emit_main=emit_main)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
        ctx: typer.Context,
        workspace_dir: Path = typer.Argument(..., help="Path to workspace directory"),
        module_name: str = typer.Argument(..., help="Name of executable program (e.g. EOM)"),
):
    py_dir = (workspace_dir / "build" / "python").resolve()
    target_py = py_dir / f"{module_name.lower()}.py"

    if not target_py.exists():
        console.print(f"[bold yellow]Module not found at {target_py}. Building workspace first...[/bold yellow]")
        builder = ProjectBuilder(workspace_dir)
        builder.compile_workspace(show_diff=False, emit_main=True)

    if not target_py.exists():
        console.print(f"[bold red]Error:[/bold red] Failed to generate {target_py}")
        raise typer.Exit(code=1)

    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{py_dir}{os.pathsep}{current_pythonpath}" if current_pythonpath else str(py_dir)

    cmd = [sys.executable, str(target_py)] + ctx.args
    subprocess.run(cmd, env=env, cwd=py_dir)


if __name__ == "__main__":
    app()
