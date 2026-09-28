# tests/test_fixtures.py
from pathlib import Path
import difflib
import yaml
import pytest
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from decimal import Decimal

from natural.normalizer.pass1_parser import Pass1Parser
from natural.normalizer.pass2_dispatcher import Pass2Dispatcher
from natural.normalizer.lowering import SemanticLoweringPass
from natural.normalizer.workspace import Workspace
from natural.ir.serializer import serialize_to_yaml
from natural.codegen.python_emitter import PythonEmitter

FIXTURE_DIR = Path(__file__).parent / "fixtures"
console = Console()


def parse_fixture(raw_text: str):
    sections = {}
    current_key = None
    buffer = []

    for line in raw_text.splitlines():
        if line.startswith("=== ") and line.endswith(" ==="):
            if current_key:
                sections[current_key] = "\n".join(buffer).strip()
            current_key = line.strip("= ").strip().upper()
            buffer = []
        else:
            buffer.append(line)
    if current_key:
        sections[current_key] = "\n".join(buffer).strip()

    return (
        sections.get("NATURAL", ""),
        sections.get("PYTHON", ""),
        sections.get("EXECUTE", ""),
    )


@pytest.mark.parametrize("fixture_path", list(FIXTURE_DIR.glob("*.test")), ids=lambda p: p.stem)
def test_pipeline_and_execution(fixture_path: Path, request):
    bless_enabled = request.config.getoption("--bless", default=False)
    verbose_enabled = request.config.getoption("--verbose-test", default=False)
    content = fixture_path.read_text(encoding="utf-8")
    natural_src, expected_py, execute_yaml = parse_fixture(content)

    if verbose_enabled:
        console.print(f"\n[bold magenta]═════════ Running Fixture: {fixture_path.name} ═════════[/bold magenta]")
        console.print(Panel(Syntax(natural_src, "text", line_numbers=True), title="[bold cyan]1. Natural Input[/bold cyan]"))

    # 1. Compile Natural to Python
    workspace = Workspace(include_dirs=[])
    p1 = Pass1Parser(workspace)
    p2 = Pass2Dispatcher()

    pass1_ast = p1.parse(natural_src, module_name=fixture_path.stem)
    ir0 = p2.lower_module(pass1_ast)
    if verbose_enabled:
        console.print(Panel(Syntax(serialize_to_yaml(ir0), "yaml", line_numbers=True), title="[bold green]2. IR-0 (AST)[/bold green]"))

    ir1 = SemanticLoweringPass(ir0, workspace=workspace).lower()
    if verbose_enabled:
        console.print(Panel(Syntax(serialize_to_yaml(ir1), "yaml", line_numbers=True), title="[bold yellow]3. IR-1 (Semantic)[/bold yellow]"))

    actual_py = PythonEmitter(ir1).generate(emit_main=False).strip()
    if verbose_enabled:
        console.print(Panel(Syntax(actual_py, "python", line_numbers=True), title="[bold blue]4. Emitted Python[/bold blue]"))

    # 2. Check / Bless Python Source
    if bless_enabled and actual_py != expected_py:
        exec_part = f"\n\n=== EXECUTE ===\n{execute_yaml}\n" if execute_yaml else "\n"
        new_content = f"=== NATURAL ===\n{natural_src}\n\n=== PYTHON ===\n{actual_py}{exec_part}"
        fixture_path.write_text(new_content, encoding="utf-8")
        expected_py = actual_py
    else:
        if actual_py != expected_py:
            diff = "\n".join(difflib.unified_diff(
                expected_py.splitlines(),
                actual_py.splitlines(),
                fromfile="expected",
                tofile="actual",
                lineterm=""
            ))
            assert False, f"Code generation mismatch in {fixture_path.name}:\n{diff}"

    # 3. Dynamic Execution & Assertions
    if not execute_yaml:
        return

    test_cases = yaml.safe_load(execute_yaml)
    if not isinstance(test_cases, list):
        return

    mod_scope = {}
    exec(actual_py, mod_scope)

    module_stem = fixture_path.stem.lower().replace("-", "_")
    func_name = f"execute_{module_stem}"
    execute_func = mod_scope.get(func_name)
    assert execute_func is not None, f"Expected entrypoint function '{func_name}' not generated"

    ctx_class_name = "".join(part.title() for part in module_stem.split("_")) + "Context"
    ctx_class = mod_scope.get(ctx_class_name)
    assert ctx_class is not None, f"Expected context class '{ctx_class_name}' not found"

    class MockSession:
        def query(self, *args, **kwargs): return []
        def add(self, *args): pass
        def delete(self, *args): pass
        def flush(self): pass

    session = MockSession()

    if verbose_enabled:
        console.print("[bold cyan]5. Executing Test Cases:[/bold cyan]")

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
                console.print(f"  • Case #{i} | Input: {case.get('input')} ➔ {expected_field} = [bold green]{actual_val!r}[/bold green] (expected: {expected_val!r})")

            assert str(actual_val) == str(expected_val), (
                f"Case #{i} in {fixture_path.name} failed: "
                f"field '{expected_field}' expected {expected_val!r}, got {actual_val!r}"
            )
