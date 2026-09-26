# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
#
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from lark import Transformer, Token
from natural.ir.models import (
    AssignStatement,
    CallnatStatement,
    ConditionalStatement,
    DataAreaRef,
    DataField,
    DecideBranch,
    DecideStatement,
    EscapeStatement,
    Expression,
    FieldFormat,
    FindStatement,
    NaturalModule,
    ReadStatement,
    ScopeType,
    Statement,
    LoopStatement,
    MoveStatement,
    InputStatement,
    PrintStatement,
    InputModifier,
)


class NaturalToIRTransformer(Transformer):
    def __init__(self, module_name: str = "MODULE"):
        super().__init__()
        self.module_name = module_name
        self._current_redefine_target: str | None = None

    def IDENTIFIER(self, token: Token) -> str:
        return str(token)

    def CNAME(self, token: Token) -> str:
        return str(token)

    def VAR_NAME(self, token: Token) -> str:
        return str(token)

    def NUMBER(self, token: Token) -> float | int:
        val = str(token)
        return float(val) if "." in val else int(val)

    def ESCAPED_STRING(self, token: Token) -> str:
        return str(token)[1:-1]

    def SINGLE_QUOTED_STRING(self, token: Token) -> str:
        return str(token)[1:-1]

    def DATE_LITERAL(self, token: Token) -> str:
        return str(token)[2:-1]

    def LEVEL(self, token: Token) -> int:
        return int(str(token))

    def num_lit(self, children: list) -> Expression:
        return Expression(kind="literal", value=children[0])

    def str_lit(self, children: list) -> Expression:
        return Expression(kind="literal", value=children[0])

    def single_str_lit(self, children: list) -> Expression:
        return Expression(kind="literal", value=children[0])

    def date_lit(self, children: list) -> Expression:
        return Expression(kind="literal", value=children[0])

    def var_ref(self, children: list) -> Expression:
        return Expression(kind="ref", value=children[0])

    def binary_expr(self, children: list) -> Expression:
        return Expression(
            kind="binary_op",
            left=children[0],
            operator=str(children[1]),
            right=children[2],
        )

    def assign_stmt(self, children: list) -> AssignStatement:
        return AssignStatement(target=str(children[0]), value=children[2])

    def if_stmt(self, children: list) -> ConditionalStatement:
        cond = children[0]
        then_b: list[Statement] = []
        else_b: list[Statement] = []
        target = then_b

        for item in children[1:]:
            if isinstance(item, Token) and str(item) == "ELSE":
                target = else_b
            elif isinstance(item, Statement):
                target.append(item)

        return ConditionalStatement(
            condition=cond, then_branch=then_b, else_branch=else_b
        )

    def decide_branch(self, children: list) -> DecideBranch:
        val = children[0]
        stmts = [c for c in children[1:] if isinstance(c, Statement)]
        return DecideBranch(value=val, statements=stmts)

    def decide_stmt(self, children: list) -> DecideStatement:
        operand = children[0]
        branches = [c for c in children[1:] if isinstance(c, DecideBranch)]
        none_stmts = [
            c for c in children[1:] if isinstance(c, Statement) and not isinstance(c, DecideBranch)
        ]
        return DecideStatement(
            operand=operand, branches=branches, none_branch=none_stmts
        )

    def no_rec_clause(self, children: list) -> list[Statement]:
        return [c for c in children if isinstance(c, Statement)]

    def find_stmt(self, children: list) -> FindStatement:
        idx = 0
        if isinstance(children[0], (int, float)):
            idx += 1

        ddm = str(children[idx])
        descriptor = str(children[idx + 1])
        operand = children[idx + 3]

        on_empty: list[Statement] = []
        body_stmts: list[Statement] = []

        for item in children:
            if item is None:
                continue
            if isinstance(item, list):
                on_empty.extend(item)
            elif isinstance(item, Statement):
                body_stmts.append(item)

        return FindStatement(
            view_name=ddm,
            descriptor=descriptor,
            operand=operand,
            body=body_stmts,
            on_empty=on_empty,
        )

    def read_stmt(self, children: list) -> ReadStatement:
        has_limit = isinstance(children[0], (int, float))
        offset = 1 if has_limit else 0

        ddm = str(children[offset])
        by_desc = None
        curr = offset + 1

        if len(children) > curr and isinstance(children[curr], str):
            by_desc = str(children[curr])
            curr += 1

        body_stmts = [c for c in children if isinstance(c, Statement)]
        return ReadStatement(view_name=ddm, by_descriptor=by_desc, body=body_stmts)

    def callnat_stmt(self, children: list) -> CallnatStatement:
        subprogram = str(children[0])
        params = [c for c in children[1:] if isinstance(c, Expression)]
        return CallnatStatement(subprogram_name=subprogram, parameters=params)

    def gda_ref(self, children: list) -> DataAreaRef:
        return DataAreaRef(name=str(children[0]), scope=ScopeType.GLOBAL)

    def pda_ref(self, children: list) -> DataAreaRef:
        return DataAreaRef(name=str(children[0]), scope=ScopeType.PARAMETER)

    def lda_ref(self, children: list) -> DataAreaRef:
        return DataAreaRef(name=str(children[0]), scope=ScopeType.LOCAL)

    def inline_field(self, children: list) -> DataField:
        lvl = int(children[0])
        name = str(children[1])
        raw_fmt = str(children[2]) if len(children) > 2 and children[2] is not None else "A"
        kind_char = raw_fmt[0]
        kind_map = {
            "A": "alphanumeric",
            "P": "packed_decimal",
            "N": "numeric",
            "I": "integer",
            "B": "binary",
            "L": "boolean",
            "D": "date",
        }
        kind = kind_map.get(kind_char, "unknown")

        parent = None
        if lvl > 1 and self._current_redefine_target:
            parent = self._current_redefine_target
        elif lvl == 1:
            self._current_redefine_target = None

        return DataField(
            level=lvl,
            name=name,
            format=FieldFormat(kind=kind, raw_spec=raw_fmt),
            parent_name=parent,
        )

    def escape_stmt(self, children: list) -> EscapeStatement:
        target_dir = str(children[0])
        label = str(children[1]) if len(children) > 1 and children[1] is not None else None
        return EscapeStatement(target=target_dir, loop_label=label)

    def local_inline(self, children: list) -> DataAreaRef:
        fields = [c for c in children if isinstance(c, DataField)]
        return DataAreaRef(
            name="INLINE_LOCAL", scope=ScopeType.LOCAL, inline_fields=fields
        )

    def parameter_inline(self, children: list) -> DataAreaRef:
        fields = [c for c in children if isinstance(c, DataField)]
        return DataAreaRef(
            name="INLINE_PARAMETER", scope=ScopeType.PARAMETER, inline_fields=fields
        )

    def global_inline(self, children: list) -> DataAreaRef:
        fields = [c for c in children if isinstance(c, DataField)]
        return DataAreaRef(
            name="INLINE_GLOBAL", scope=ScopeType.GLOBAL, inline_fields=fields
        )

    def define_data(self, children: list) -> list[DataAreaRef]:
        return [c for c in children if isinstance(c, DataAreaRef)]

    def include_stmt(self, children: list) -> str:
        return str(children[0])

    def end_stmt(self, children: list):
        return None

    def subroutine(self, children: list) -> tuple[str, list[Statement]]:
        name = str(children[0])
        stmts = [c for c in children[1:] if isinstance(c, Statement)]
        return name, stmts

    def redefine_group(self, children: list):
        self._current_redefine_target = str(children[1])
        return None

    def input_mod_assign(self, children: list) -> InputModifier:
        key = str(children[0])
        val = children[2] if len(children) >= 3 else children[1]
        if not isinstance(val, Expression):
            val = Expression(kind="literal", value=str(val))
        return InputModifier(key=key, value=val)

    def input_modifier(self, children: list) -> list[InputModifier]:
        return [c for c in children if isinstance(c, InputModifier)]

    def input_stmt(self, children: list) -> InputStatement:
        fields = []
        modifiers = []
        for c in children:
            if isinstance(c, Expression):
                fields.append(c)
            elif isinstance(c, list):
                modifiers.extend(c)
        return InputStatement(fields=fields, modifiers=modifiers)

    def move_stmt(self, children: list) -> MoveStatement:
        exprs = [c for c in children if isinstance(c, Expression)]
        edit_mask = None
        for c in children:
            if isinstance(c, Token) and "EM=" in str(c):
                m = re.search(r"EM=([A-Za-z0-9/.\-]+)", str(c))
                if m:
                    edit_mask = m.group(1)
        return MoveStatement(source=exprs[0], target=exprs[1], edit_mask=edit_mask)

    def repeat_stmt(self, children: list) -> LoopStatement:
        cond = children[0] if isinstance(children[0], Expression) else None
        stmts = [c for c in children if isinstance(c, Statement)]
        return LoopStatement(condition=cond, body=stmts)

    def add_stmt(self, children: list) -> AssignStatement:
        exprs = [c for c in children if isinstance(c, Expression)]
        val, target = exprs[0], exprs[1]
        target_ref = Expression(kind="ref", value=str(target.value))
        return AssignStatement(
            target=str(target.value),
            value=Expression(kind="binary_op", operator="+", left=target_ref, right=val),
        )

    def subtract_stmt(self, children: list) -> AssignStatement:
        exprs = [c for c in children if isinstance(c, Expression)]
        val, target = exprs[0], exprs[1]
        target_ref = Expression(kind="ref", value=str(target.value))
        return AssignStatement(
            target=str(target.value),
            value=Expression(kind="binary_op", operator="-", left=target_ref, right=val),
        )

    def multiply_stmt(self, children: list) -> AssignStatement:
        exprs = [c for c in children if isinstance(c, Expression)]
        target, val = exprs[0], exprs[1]
        target_ref = Expression(kind="ref", value=str(target.value))
        return AssignStatement(
            target=str(target.value),
            value=Expression(kind="binary_op", operator="*", left=target_ref, right=val),
        )

    def divide_stmt(self, children: list) -> AssignStatement:
        exprs = [c for c in children if isinstance(c, Expression)]
        val, target = exprs[0], exprs[1]
        target_ref = Expression(kind="ref", value=str(target.value))
        return AssignStatement(
            target=str(target.value),
            value=Expression(kind="binary_op", operator="/", left=target_ref, right=val),
        )

    def print_stmt(self, children: list) -> PrintStatement:
        fields = []
        for c in children:
            if isinstance(c, Expression):
                fields.append(c)
            elif isinstance(c, str):
                fields.append(Expression(kind="literal", value=c))
        return PrintStatement(fields=fields)

    def module(self, children: list) -> NaturalModule:
        includes: list = []
        data_areas: list[DataAreaRef] = []
        subroutines: dict[str, list[Statement]] = {}
        body: list[Statement] = []

        for item in children:
            if isinstance(item, str):
                includes.append(item)
            elif isinstance(item, DataAreaRef):
                data_areas.append(item)
            elif isinstance(item, list) and all(isinstance(x, DataAreaRef) for x in item):
                data_areas.extend(item)
            elif isinstance(item, tuple) and len(item) == 2:
                subroutines[item[0]] = item[1]
            elif isinstance(item, Statement):
                body.append(item)

        return NaturalModule(
            name=self.module_name,
            includes=includes,
            data_areas=data_areas,
            subroutines=subroutines,
            body=body,
        )
