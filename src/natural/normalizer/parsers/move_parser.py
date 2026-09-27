import re
from natural.ir.models import MoveStatement
from natural.normalizer.parsers.expression_parser import ExpressionParser

class MoveParser:
    def __init__(self):
        self.expr_parser = ExpressionParser()
        self.move_pattern = re.compile(r"^\s*MOVE\s+(?:EDITED\s+)?(.+?)\s+TO\s+(.+)$", re.IGNORECASE)
        self.em_pattern = re.compile(r"^(.*?)\s*\(\s*EM\s*=\s*([^)]+)\s*\)$", re.IGNORECASE)

    def parse(self, raw_statement: str) -> MoveStatement:
        clean_stmt = re.sub(r"/\*.*$", "", raw_statement).strip()
        match = self.move_pattern.match(clean_stmt)
        if not match:
            raise ValueError(f"Invalid MOVE syntax: {raw_statement}")

        source_part = match.group(1).strip()
        target_part = match.group(2).strip()

        source_mask, target_mask = None, None

        s_match = self.em_pattern.match(source_part)
        if s_match:
            source_part = s_match.group(1).strip()
            source_mask = s_match.group(2).strip()

        t_match = self.em_pattern.match(target_part)
        if t_match:
            target_part = t_match.group(1).strip()
            target_mask = t_match.group(2).strip()

        final_mask = target_mask or source_mask

        return MoveStatement(
            source=self.expr_parser.parse(source_part),
            target=self.expr_parser.parse(target_part),
            edit_mask=final_mask
        )
