# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import List, Tuple
from natural.ir.semantic import (
    CloseWorkFileOp,
    ReadWorkFileOp,
    WriteOp,
    WriteWorkFileOp,
)
from natural.codegen.python_emitter.context import EmitterContext
from natural.codegen.python_emitter.expressions import PythonExpressionEmitter


def emit_write(
        op: WriteOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    lines_operands = []
    curr_line = []
    for operand in op.operands:
        if operand.op == "newline":
            lines_operands.append(curr_line)
            curr_line = []
        else:
            curr_line.append(operand)
    lines_operands.append(curr_line)

    for line_ops in lines_operands:
        if not line_ops:
            ctx.emit_line("print()")
            continue

        has_tab = any(e.op == "tab" for e in line_ops)
        if not has_tab:
            parts = [expr_emitter.emit_expr(e) for e in line_ops]
            ctx.emit_line(f"print({', '.join(parts)})")
        else:
            code_parts = []
            sim_parts: List[Tuple[str, str]] = []

            for e in line_ops:
                if e.op == "tab":
                    target_col = max(0, int(e.value) - 1)
                    if not sim_parts:
                        if target_col > 0:
                            code_parts.append(f'" " * {target_col}')
                            sim_parts.append(("literal", " " * target_col))
                    else:
                        if all(kind == "literal" for kind, _ in sim_parts):
                            sim_str = "".join(val for _, val in sim_parts)
                            code_parts.append(f'" " * ({target_col} - len("{sim_str}"))')
                            curr_len = len(sim_str)
                            diff = max(0, target_col - curr_len)
                            sim_parts.append(("literal", " " * diff))
                        else:
                            len_terms = []
                            for kind, val in sim_parts:
                                if kind == "literal":
                                    len_terms.append(f'"{val}"')
                                else:
                                    len_terms.append(val)
                            sim_expr = " + ".join(len_terms)
                            code_parts.append(f'" " * ({target_col} - len({sim_expr}))')
                            sim_parts.append(("expr", f'" " * max(0, {target_col} - len({sim_expr}))'))
                else:
                    if e.op == "literal" and isinstance(e.value, str):
                        code_parts.append(f'"{e.value}"')
                        sim_parts.append(("literal", e.value))
                    elif e.op == "literal":
                        val_str = str(e.value)
                        code_parts.append(repr(e.value))
                        sim_parts.append(("literal", val_str))
                    else:
                        expr_code = expr_emitter.emit_expr(e)
                        code_parts.append(f"str({expr_code})")
                        sim_parts.append(("expr", f"str({expr_code})"))

            line_code = " + ".join(code_parts)
            ctx.emit_line(f"print({line_code})")


def emit_write_work_file(
        op: WriteWorkFileOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    items_str = ", ".join(f"str({expr_emitter.emit_expr(e)})" for e in op.operands)
    ctx.emit_line(f'with open(f"workfile_{op.file_number}.dat", "a", encoding="utf-8") as wf:')
    with ctx.indent():
        ctx.emit_line(f'wf.write("\\t".join([{items_str}]) + "\\n")')


def emit_close_work_file(
        op: CloseWorkFileOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    ctx.emit_line(f"# CLOSE WORK FILE {op.file_number}")


def emit_read_work_file(
        op: ReadWorkFileOp,
        ctx: EmitterContext,
        expr_emitter: PythonExpressionEmitter,
        dispatcher,
) -> None:
    ctx.emit_line(f'if os.path.exists("workfile_{op.file_number}.dat"):')
    with ctx.indent():
        ctx.emit_line(f'with open("workfile_{op.file_number}.dat", "r", encoding="utf-8") as wf:')
        with ctx.indent():
            ctx.emit_line("for line in wf:")
            with ctx.indent():
                ctx.emit_line("parts = line.rstrip('\\n').split('\\t')")
                for idx, target_id in enumerate(op.target_ids):
                    target_var = ctx.resolve_ref(target_id)
                    ctx.emit_line(f"if len(parts) > {idx}:")
                    with ctx.indent():
                        ctx.emit_line(f"{target_var} = parts[{idx}]")
                if not op.body:
                    ctx.emit_line("pass")
                for sub_op in op.body:
                    dispatcher.emit_operation(sub_op)
