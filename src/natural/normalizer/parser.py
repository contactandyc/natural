# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from pathlib import Path
from lark import Lark
from lark.exceptions import UnexpectedInput
from rich.console import Console
from rich.panel import Panel

from natural.ir.models import NaturalModule
from natural.normalizer.ast_visitor import NaturalToIRTransformer

console = Console()

def get_grammar_path() -> Path:
    # Points to src/natural/grammar/natural.lark
    return Path(__file__).resolve().parent.parent / "grammar" / "natural.lark"


class NaturalParser:
    def __init__(self):
        grammar_file = get_grammar_path()
        if not grammar_file.exists():
            raise FileNotFoundError(f"Grammar definition not found at: {grammar_file}")
        with open(grammar_file, "r", encoding="utf-8") as f:
            grammar_text = f.read()
        self._lark = Lark(grammar_text, parser="lalr")

    def parse(self, source_code: str, module_name: str = "MODULE") -> NaturalModule:
        """Parses Natural source text into a normalized NaturalModule IR."""
        try:
            tree = self._lark.parse(source_code)
            transformer = NaturalToIRTransformer(module_name=module_name)
            return transformer.transform(tree)
        except UnexpectedInput as e:
            # Catch the specific syntax error and emit a copy-pasteable prompt
            self._emit_copypaste_prompt(source_code, e, module_name)

            # Raise a clean ValueError so the CLI catches it without dumping a massive stack trace
            raise ValueError(f"Parsing failed in {module_name} at line {e.line}, column {e.column}.")

    def _emit_copypaste_prompt(self, source_code: str, error: UnexpectedInput, module_name: str):
        """Generates a rich, formatted prompt with full file context for an LLM."""
        context = error.get_context(source_code)

        # Read the current architectural state
        grammar_text = get_grammar_path().read_text(encoding="utf-8")

        visitor_path = Path(__file__).resolve().parent / "ast_visitor.py"
        visitor_text = visitor_path.read_text(encoding="utf-8") if visitor_path.exists() else ""

        models_path = Path(__file__).resolve().parent.parent / "ir" / "models.py"
        models_text = models_path.read_text(encoding="utf-8") if models_path.exists() else ""

        prompt = (
            f"I am building a deterministic compiler using Python and Lark to migrate a legacy Software AG Natural program.\n"
            f"The parser crashed while processing the module `{module_name}`.\n\n"
            f"**Error Location:** Line {error.line}, Column {error.column}\n\n"
            f"**Failing Context:**\n"
            f"```natural\n{context}```\n\n"
            f"Based on my current grammar, AST models, and visitor implementation below, "
            f"how should I update `natural.lark`, `models.py`, and `ast_visitor.py` to correctly parse this syntax?\n\n"
            f"<details>\n<summary>natural.lark</summary>\n\n```lark\n{grammar_text}\n```\n</details>\n\n"
            f"<details>\n<summary>models.py</summary>\n\n```python\n{models_text}\n```\n</details>\n\n"
            f"<details>\n<summary>ast_visitor.py</summary>\n\n```python\n{visitor_text}\n```\n</details>"
        )

        console.print("\n[bold red]💥 Parser Crash Detected![/bold red]")
        console.print("[dim]Copy and paste the prompt below into an LLM (ChatGPT/Claude/Gemini) for a quick fix:[/dim]")
        console.print(Panel(prompt, title="🤖 AI Remediation Prompt", border_style="cyan", expand=False))

    def parse_file(self, file_path: Path | str) -> NaturalModule:
        path = Path(file_path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return self.parse(content, module_name=path.stem)
