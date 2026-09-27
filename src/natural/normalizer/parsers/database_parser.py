import re
from natural.ir.models import UpdateStatement, GetStatement
from natural.normalizer.parsers.expression_parser import ExpressionParser

class DatabaseOpParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.get_pattern = re.compile(r"^\s*GET\s+([A-Z0-9\-\_]+)\s+(.+)$", re.IGNORECASE)

    def parse(self, raw_statement: str):
        text = raw_statement.strip().upper()

        if text == "UPDATE":
            return UpdateStatement()

        if text.startswith("GET "):
            match = self.get_pattern.match(raw_statement.strip())
            if match:
                view_name = match.group(1).upper()
                # Use ExpressionParser to safely capture the *ISN or other argument
                args = [self.expr_parser.parse(match.group(2))]
                return GetStatement(view_name=view_name, arguments=args)

        raise ValueError(f"Invalid Database Op: {raw_statement}")
