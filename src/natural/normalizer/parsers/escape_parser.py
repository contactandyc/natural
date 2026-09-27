import re
from natural.ir.models import EscapeStatement

class EscapeParser:
    def __init__(self):
        # Matches: ESCAPE TOP, ESCAPE BOTTOM, ESCAPE ROUTINE
        # Also supports optional labels: ESCAPE BOTTOM (LABEL)
        self.pattern = re.compile(
            r"^\s*ESCAPE\s+(TOP|BOTTOM|ROUTINE)(?:\s+\(([^)]+)\))?\s*$",
            re.IGNORECASE
        )

    def parse(self, raw_statement: str) -> EscapeStatement:
        match = self.pattern.match(raw_statement)
        if not match:
            raise ValueError(f"Invalid ESCAPE syntax: {raw_statement}")

        return EscapeStatement(
            target=match.group(1).upper(),
            loop_label=match.group(2)
        )
