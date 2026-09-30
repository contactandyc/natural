# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from natural.ir.semantic import (
    CloseWorkFileOp,
    ReadWorkFileOp,
    WriteOp,
    WriteWorkFileOp,
)
from natural.codegen.targets.python.context import EmitterContext
from natural.codegen.targets.python.expressions import PythonExpressionEmitter


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
            items = []
            for e in line_ops:
                if e.op == "tab":
                    items.append(f"tab({e.value})")
                else:
                    items.append(expr_emitter.emit_expr(e))
            ctx.emit_line(f"print(tabulate({', '.join(items)}))")


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
