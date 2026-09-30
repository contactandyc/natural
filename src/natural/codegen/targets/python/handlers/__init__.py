# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from typing import Callable, Dict, Type
from natural.ir.semantic import (
    AssignOp,
    AtBreakOp,
    AtEndOfDataOp,
    AtStartOfDataOp,
    BranchOp,
    BreakOp,
    CallProgramOp,
    CallSubroutineOp,
    CloseWorkFileOp,
    CompressOp,
    ContinueOp,
    EntityDeleteOp,
    EntityGetOp,
    EntityRefreshOp,
    EntityStoreOp,
    EntityUpdateOp,
    ExamineOp,
    FetchOp,
    ForLoopOp,
    LoopOp,
    MoveAllOp,
    QueryIterationOp,
    ReadWorkFileOp,
    ResetOp,
    ResizeArrayOp,
    ReturnOp,
    SemanticStatement,
    SeparateOp,
    TerminateOp,
    TransactionOp,
    WriteOp,
    WriteWorkFileOp,
)
from natural.codegen.targets.python.handlers.control_flow import (
    emit_branch,
    emit_break,
    emit_continue,
    emit_for_loop,
    emit_loop,
    emit_return,
    emit_terminate,
)
from natural.codegen.targets.python.handlers.database import (
    emit_at_break,
    emit_at_end,
    emit_at_start,
    emit_entity_delete,
    emit_entity_get,
    emit_entity_refresh,
    emit_entity_store,
    emit_entity_update,
    emit_query_iteration,
    emit_transaction,
)
from natural.codegen.targets.python.handlers.invocation import (
    emit_call_program,
    emit_call_subroutine,
    emit_fetch,
)
from natural.codegen.targets.python.handlers.io import (
    emit_close_work_file,
    emit_read_work_file,
    emit_write,
    emit_write_work_file,
)
from natural.codegen.targets.python.handlers.memory import (
    emit_assign,
    emit_compress,
    emit_examine,
    emit_move_all,
    emit_reset,
    emit_resize_array,
    emit_separate,
)

DEFAULT_OPERATION_HANDLERS: Dict[Type[SemanticStatement], Callable] = {
    # Memory
    AssignOp: emit_assign,
    MoveAllOp: emit_move_all,
    CompressOp: emit_compress,
    SeparateOp: emit_separate,
    ExamineOp: emit_examine,
    ResetOp: emit_reset,
    ResizeArrayOp: emit_resize_array,
    # Database
    QueryIterationOp: emit_query_iteration,
    EntityGetOp: emit_entity_get,
    EntityRefreshOp: emit_entity_refresh,
    EntityUpdateOp: emit_entity_update,
    EntityStoreOp: emit_entity_store,
    EntityDeleteOp: emit_entity_delete,
    TransactionOp: emit_transaction,
    AtStartOfDataOp: emit_at_start,
    AtEndOfDataOp: emit_at_end,
    AtBreakOp: emit_at_break,
    # Control flow
    BranchOp: emit_branch,
    LoopOp: emit_loop,
    ForLoopOp: emit_for_loop,
    BreakOp: emit_break,
    ContinueOp: emit_continue,
    ReturnOp: emit_return,
    TerminateOp: emit_terminate,
    # Invocations
    CallSubroutineOp: emit_call_subroutine,
    CallProgramOp: emit_call_program,
    FetchOp: emit_fetch,
    # IO
    WriteOp: emit_write,
    WriteWorkFileOp: emit_write_work_file,
    CloseWorkFileOp: emit_close_work_file,
    ReadWorkFileOp: emit_read_work_file,
}

__all__ = ["DEFAULT_OPERATION_HANDLERS"]
