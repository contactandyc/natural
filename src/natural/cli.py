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

from natural.codegen.schema.mongo import MongoSchemaEmitter
from natural.codegen.schema.openapi import OpenApiSchemaEmitter
from natural.codegen.schema.prisma import PrismaSchemaEmitter
from natural.codegen.schema.sql_ddl import SqlDdlEmitter
from natural.codegen.target import get_target
from natural.ir.serializer import serialize_to_yaml
from natural.normalizer.lowering import SemanticLoweringPass
from natural.normalizer.pass1_parser import Pass1Parser
from natural.normalizer.pass2_dispatcher import Pass2Dispatcher
from natural.normalizer.schema_builder import SchemaBuilder
from natural.normalizer.schema_normalizer import SchemaNormalizer
from natural.normalizer.workspace import Workspace
from natural.orchestrator.builder import ProjectBuilder

app = typer.Typer(
    name="natural",
    help="Software AG Natural to Semantic Intermediate Representation (IR) compiler.",
)
schema_app = typer.Typer(
    name="schema",
    help="Export and inspect target schemas (SQL DDL, MongoDB, Prisma, OpenAPI, SQLAlchemy) from DDMs.",
)
app.add_typer(schema_app, name="schema")
console = Console()


@app.command()
def parse(
        source_file: Path = typer.Argument(..., help="Path to the Natural source file (.nsp, .nsn, .nss)"),
        include_dir: Optional[List[Path]] = typer.Option(None, "--include-dir", "-I", help="Directories to search for .NSA, .DDM, and copycodes"),
        output: Optional[Path] = typer.Option(None, "--output", "-o", help="Optional output file path"),
        display: bool = typer.Option(True, "--display/--no-display", help="Print the generated output to console"),
        target: str = typer.Option("python", "--target", "-t", help="Target language (e.g. python)"),
        emit_code: bool = typer.Option(False, "--emit-code", "-c", help="Generate and print source code in target language"),
        emit_python: bool = typer.Option(False, "--emit-python", "-p", help="Deprecated alias for --emit-code"),
        emit_main: bool = typer.Option(False, "--emit-main", help="Include runnable __main__ block in emitted code"),
        emit_orm: bool = typer.Option(False, "--emit-orm", help="Generate schema/ORM models from DDMs"),
        normalize_arrays: bool = typer.Option(False, "--normalize-arrays", "-N", help="Normalize arrays into relational 1NF child tables"),
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

        backend = get_target(target)

        if emit_orm:
            ddms = [area for key, area in workspace._cache.items() if key.startswith("DDM_")]
            catalog = SchemaBuilder(ddms).build_catalog()
            if normalize_arrays:
                catalog = SchemaNormalizer().normalize(catalog)
            schemas = backend.emit_schema(catalog)
            result_text = list(schemas.values())[0] if schemas else ""
            lang = "python" if target == "python" else "text"
        elif emit_code or emit_python:
            should_emit_main = emit_main or source_file.suffix.lower() == ".nsp"
            result_text = backend.emit_module(ir1_module, emit_main=should_emit_main)
            lang = "python" if target == "python" else "text"
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
        target: str = typer.Option("python", "--target", "-t", help="Target output language (e.g. python)"),
        show_diff: bool = typer.Option(False, "--diff", help="Show Git-style diffs for output files that have changed"),
        emit_main: bool = typer.Option(True, "--emit-main/--no-emit-main", help="Emit runnable entry points into .nsp outputs"),
        normalize_arrays: bool = typer.Option(False, "--normalize-arrays", "-N", help="Normalize arrays into relational 1NF child tables"),
):
    if not workspace_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Workspace directory not found: {workspace_dir}")
        raise typer.Exit(code=1)

    builder = ProjectBuilder(workspace_dir, target=target, normalize_arrays=normalize_arrays)
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
        builder = ProjectBuilder(workspace_dir, target="python")
        builder.compile_workspace(show_diff=False, emit_main=True)

    if not target_py.exists():
        console.print(f"[bold red]Error:[/bold red] Failed to generate {target_py}")
        raise typer.Exit(code=1)

    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{py_dir}{os.pathsep}{current_pythonpath}" if current_pythonpath else str(py_dir)

    cmd = [sys.executable, str(target_py)] + ctx.args
    subprocess.run(cmd, env=env, cwd=py_dir)


@schema_app.command("export")
def schema_export(
        source: Path = typer.Argument(..., help="Path to a .ddm file or directory containing DDMs"),
        target: str = typer.Option("sql", "--target", "-t", help="Target format: sql, mongo, prisma, openapi, sqlalchemy"),
        dialect: str = typer.Option("postgres", "--dialect", "-d", help="SQL dialect for sql target (postgres, mysql, sqlite, oracle)"),
        normalize_arrays: bool = typer.Option(False, "--normalize-arrays", "-N", help="Normalize arrays into relational 1NF child tables"),
        output: Optional[Path] = typer.Option(None, "--output", "-o", help="Optional output directory or file path"),
        display: bool = typer.Option(True, "--display/--no-display", help="Print emitted output to console"),
):
    """Exports Adabas DDMs to target database schema definitions (SQL, MongoDB, Prisma, OpenAPI)."""
    search_dirs = [source] if source.is_dir() else [source.parent]
    ws = Workspace(include_dirs=search_dirs)

    ddms = []
    if source.is_file() and source.suffix.lower() == ".ddm":
        ddm = ws.get_ddm(source.stem.upper())
        if ddm:
            ddms.append(ddm)
    elif source.is_dir():
        for p in source.glob("*.ddm"):
            ddm = ws.get_ddm(p.stem.upper())
            if ddm:
                ddms.append(ddm)

    if not ddms:
        console.print(f"[bold red]Error:[/bold red] No valid DDM files found in: {source}")
        raise typer.Exit(code=1)

    catalog = SchemaBuilder(ddms).build_catalog()
    if normalize_arrays:
        catalog = SchemaNormalizer().normalize(catalog)

    target_key = target.lower()

    if target_key == "sql":
        emitter = SqlDdlEmitter(catalog, dialect=dialect)
        outputs = emitter.generate()
        result_text = "\n\n".join(outputs.values())
        lang = "sql"
    elif target_key == "mongo":
        emitter = MongoSchemaEmitter(catalog)
        outputs = emitter.generate()
        result_text = "\n\n".join(outputs.values())
        lang = "typescript"
    elif target_key == "prisma":
        emitter = PrismaSchemaEmitter(catalog)
        result_text = emitter.generate()
        lang = "text"
    elif target_key == "openapi":
        emitter = OpenApiSchemaEmitter(catalog)
        result_text = emitter.generate()
        lang = "yaml"
    elif target_key == "sqlalchemy":
        backend = get_target("python")
        outputs = backend.emit_schema(catalog)
        result_text = list(outputs.values())[0] if outputs else ""
        lang = "python"
    else:
        console.print(f"[bold red]Error:[/bold red] Unknown target format: {target}. Available: sql, mongo, prisma, openapi, sqlalchemy")
        raise typer.Exit(code=1)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result_text, encoding="utf-8")
        console.print(f"[green]Successfully exported schema to:[/green] {output}")
    if display or not output:
        console.print(Syntax(result_text, lang, theme="monokai", line_numbers=True))


@schema_app.command("inspect")
def schema_inspect(
        source: Path = typer.Argument(..., help="Path to a .ddm file or directory containing DDMs"),
        normalize_arrays: bool = typer.Option(False, "--normalize-arrays", "-N", help="Normalize arrays into relational 1NF child tables"),
):
    """Parses DDMs and displays the target-agnostic SchemaCatalog (IR-S) as audited YAML."""
    search_dirs = [source] if source.is_dir() else [source.parent]
    ws = Workspace(include_dirs=search_dirs)

    ddms = []
    if source.is_file() and source.suffix.lower() == ".ddm":
        ddm = ws.get_ddm(source.stem.upper())
        if ddm:
            ddms.append(ddm)
    elif source.is_dir():
        for p in source.glob("*.ddm"):
            ddm = ws.get_ddm(p.stem.upper())
            if ddm:
                ddms.append(ddm)

    if not ddms:
        console.print(f"[bold red]Error:[/bold red] No valid DDM files found in: {source}")
        raise typer.Exit(code=1)

    catalog = SchemaBuilder(ddms).build_catalog()
    if normalize_arrays:
        catalog = SchemaNormalizer().normalize(catalog)

    yaml_text = serialize_to_yaml(catalog)
    console.print(Syntax(yaml_text, "yaml", theme="monokai", line_numbers=True))


if __name__ == "__main__":
    app()
