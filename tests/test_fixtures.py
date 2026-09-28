# tests/test_fixtures.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

import difflib
import importlib
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Dict, Tuple

import pytest
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from natural.orchestrator.builder import ProjectBuilder

FIXTURE_DIR = Path(__file__).parent / "fixtures"
console = Console()

HEADER_RE = re.compile(r"^===\s*([A-Za-z0-9_-]+)(?::\s*([^=\n]+?))?\s*===$")


def parse_fixture(raw_text: str, default_stem: str) -> Tuple[Dict[str, str], Dict[str, str], str, bool, bool]:
    natural_files: Dict[str, str] = {}
    python_files: Dict[str, str] = {}
    execute_yaml = ""

    has_explicit_natural_names = False
    has_explicit_python_names = False

    current_kind = None
    current_name = None
    buffer = []

    def flush():
        nonlocal buffer, has_explicit_natural_names, has_explicit_python_names, execute_yaml
        if current_kind == "NATURAL":
            if current_name:
                has_explicit_natural_names = True
                fname = current_name
            else:
                fname = f"{default_stem}.nsp"
            natural_files[fname] = "\n".join(buffer).strip()
        elif current_kind == "PYTHON":
            if current_name:
                has_explicit_python_names = True
                fname = current_name
            else:
                fname = f"{default_stem.lower().replace('-', '_')}.py"
            python_files[fname] = "\n".join(buffer).strip()
        elif current_kind == "EXECUTE":
            execute_yaml = "\n".join(buffer).strip()
        buffer = []

    for line in raw_text.splitlines():
        m = HEADER_RE.match(line.strip())
        if m:
            flush()
            current_kind = m.group(1).upper()
            current_name = m.group(2).strip() if m.group(2) else None
        else:
            buffer.append(line)
    flush()

    return natural_files, python_files, execute_yaml, has_explicit_natural_names, has_explicit_python_names


def serialize_fixture(
        natural_files: Dict[str, str],
        python_files: Dict[str, str],
        execute_yaml: str,
        has_explicit_natural_names: bool,
        has_explicit_python_names: bool,
) -> str:
    sections = []

    if not has_explicit_natural_names and len(natural_files) == 1:
        content = list(natural_files.values())[0]
        sections.append(f"=== NATURAL ===\n{content}")
    else:
        for fname, content in natural_files.items():
            sections.append(f"=== NATURAL: {fname} ===\n{content}")

    if not has_explicit_python_names and len(python_files) == 1:
        content = list(python_files.values())[0]
        sections.append(f"=== PYTHON ===\n{content}")
    else:
        for fname in sorted(python_files.keys()):
            sections.append(f"=== PYTHON: {fname} ===\n{python_files[fname]}")

    if execute_yaml:
        sections.append(f"=== EXECUTE ===\n{execute_yaml}")

    return "\n\n".join(sections).strip() + "\n"


@pytest.mark.parametrize("fixture_path", list(FIXTURE_DIR.glob("*.test")), ids=lambda p: p.stem)
def test_pipeline_and_execution(fixture_path: Path, request, tmp_path: Path):
    bless_enabled = request.config.getoption("--bless", default=False)
    verbose_enabled = request.config.getoption("--verbose-test", default=False)
    content = fixture_path.read_text(encoding="utf-8")

    natural_files, expected_py_files, execute_yaml, has_exp_nat, has_exp_py = parse_fixture(
        content, fixture_path.stem
    )

    if verbose_enabled:
        console.print(f"\n[bold magenta]═════════ Running Fixture: {fixture_path.name} ═════════[/bold magenta]")
        for fname, n_src in natural_files.items():
            console.print(Panel(Syntax(n_src, "text", line_numbers=True), title=f"[bold cyan]Input: {fname}[/bold cyan]"))

    # 1. Populate workspace in tmp_path
    for fname, n_src in natural_files.items():
        (tmp_path / fname).write_text(n_src, encoding="utf-8")

    # 2. Compile workspace
    builder = ProjectBuilder(tmp_path)
    builder.compile_workspace(show_diff=False, emit_main=False)

    py_dir = tmp_path / "build" / "python"
    actual_py_files: Dict[str, str] = {}
    for p in py_dir.glob("*.py"):
        actual_py_files[p.name] = p.read_text(encoding="utf-8").strip()

    # Determine files to verify
    module_stems = {
        Path(f).stem.lower().replace("-", "_")
        for f in natural_files
        if Path(f).suffix.lower() in (".nsp", ".nsn")
    }

    relevant_py_files: Dict[str, str] = {}
    for stem in module_stems:
        py_name = f"{stem}.py"
        if py_name in actual_py_files:
            relevant_py_files[py_name] = actual_py_files[py_name]

    if "target_orm.py" in expected_py_files:
        if "target_orm.py" in actual_py_files:
            relevant_py_files["target_orm.py"] = actual_py_files["target_orm.py"]

    if verbose_enabled:
        for py_name, py_src in relevant_py_files.items():
            console.print(Panel(Syntax(py_src, "python", line_numbers=True), title=f"[bold blue]Emitted: {py_name}[/bold blue]"))

    # 3. Check / Bless Python Source
    diffs = []
    for expected_name, expected_code in expected_py_files.items():
        actual_code = relevant_py_files.get(expected_name, "")
        if actual_code != expected_code:
            diff = "\n".join(
                difflib.unified_diff(
                    expected_code.splitlines(),
                    actual_code.splitlines(),
                    fromfile=f"expected/{expected_name}",
                    tofile=f"actual/{expected_name}",
                    lineterm="",
                )
            )
            diffs.append(diff)

    for actual_name in relevant_py_files:
        if actual_name not in expected_py_files:
            diffs.append(f"Missing expected snapshot for emitted file: {actual_name}")

    if diffs:
        if bless_enabled:
            new_content = serialize_fixture(
                natural_files,
                relevant_py_files,
                execute_yaml,
                has_exp_nat,
                has_exp_py or len(relevant_py_files) > 1,
                )
            fixture_path.write_text(new_content, encoding="utf-8")
        else:
            diff_report = "\n\n".join(diffs)
            assert False, f"Code generation mismatch in {fixture_path.name}:\n{diff_report}"

    # 4. Dynamic Execution & Assertions
    if not execute_yaml:
        return

    test_data = yaml.safe_load(execute_yaml)
    if isinstance(test_data, dict):
        entrypoint_candidate = test_data.get("entrypoint")
        test_cases = test_data.get("cases", [])
    elif isinstance(test_data, list):
        entrypoint_candidate = None
        test_cases = test_data
    else:
        return

    # Resolve entrypoint module
    fixture_stem = fixture_path.stem.lower().replace("-", "_")
    if entrypoint_candidate:
        entrypoint_stem = entrypoint_candidate.lower().replace("-", "_")
    elif fixture_stem in module_stems:
        entrypoint_stem = fixture_stem
    else:
        nsp_stems = [
            Path(f).stem.lower().replace("-", "_")
            for f in natural_files
            if f.lower().endswith(".nsp")
        ]
        entrypoint_stem = nsp_stems[0] if nsp_stems else sorted(module_stems)[0]

    # Prepend build output directory to sys.path
    py_dir_str = str(py_dir.resolve())
    if py_dir_str not in sys.path:
        sys.path.insert(0, py_dir_str)

    # Invalidate cached module imports for clean fixture isolation
    for stem in module_stems | {"target_orm"}:
        if stem in sys.modules:
            del sys.modules[stem]

    entrypoint_mod = importlib.import_module(entrypoint_stem)

    func_name = f"execute_{entrypoint_stem}"
    execute_func = getattr(entrypoint_mod, func_name, None)
    assert execute_func is not None, f"Expected entrypoint function '{func_name}' not found in {entrypoint_stem}.py"

    ctx_class_name = "".join(part.title() for part in entrypoint_stem.split("_")) + "Context"
    ctx_class = getattr(entrypoint_mod, ctx_class_name, None)
    assert ctx_class is not None, f"Expected context class '{ctx_class_name}' not found in {entrypoint_stem}.py"

    class MockQuery(list):
        def filter(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

    class MockSession:
        def query(self, *args, **kwargs):
            return MockQuery()

        def add(self, *args):
            pass

        def delete(self, *args):
            pass

        def flush(self):
            pass

        def commit(self):
            pass

        def rollback(self):
            pass

        def refresh(self, *args):
            pass

    session = MockSession()

    if verbose_enabled:
        console.print(f"[bold cyan]5. Executing Test Cases against '{entrypoint_stem}.py':[/bold cyan]")

    for i, case in enumerate(test_cases, 1):
        ctx = ctx_class()
        for field, val in case.get("input", {}).items():
            default_val = getattr(ctx, field, None)
            if isinstance(default_val, Decimal) and not isinstance(val, Decimal):
                val = Decimal(str(val))
            elif isinstance(default_val, int) and not isinstance(val, int):
                val = int(val)
            elif isinstance(default_val, bool) and not isinstance(val, bool):
                val = str(val).lower() in ("true", "1", "yes", "t")
            setattr(ctx, field, val)

        result_ctx = execute_func(ctx, session)

        for expected_field, expected_val in case.get("expected", {}).items():
            actual_val = getattr(result_ctx, expected_field)
            if verbose_enabled:
                console.print(
                    f"  • Case #{i} | Input: {case.get('input')} ➔ {expected_field} = [bold green]{actual_val!r}[/bold green] (expected: {expected_val!r})"
                )

            assert str(actual_val) == str(expected_val), (
                f"Case #{i} in {fixture_path.name} failed: "
                f"field '{expected_field}' expected {expected_val!r}, got {actual_val!r}"
            )
