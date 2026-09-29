# Chats

The initial chat - https://share.gemini.google/YGNCpgsHdbme

To support converting the following example: https://github.com/SoftwareAG/adabas-natural-code-samples/blob/main/Calculate%20End-Of-Month%20(EOM)/program.txt
- some of the initial chat was extended
- https://share.gemini.google/f7vnV9hkBHZw

Refactoring repo to allow for better parsing: https://share.gemini.google/P6Ci5PImjszJ

---

### Summary of changes in https://share.gemini.google/4e8f319CwE5Y

This diff introduces **test automation infrastructure (`test`/`bless` runner)**, **new language syntax support in the compiler frontend**, **expanded AST/IR nodes**, **robust semantic lowering**, and **re-generated outputs for the freight-calc workspace**.

---

### 1. Build and Test Automation (`build.sh`, `tests/conftest.py`, `tests/test_fixtures.py`)

* **Dual Test/Bless Command:** Added `bless` as a first-class subcommand in `build.sh` alongside `test`, automatically passing `--bless` to update fixture baselines.
* **Smart Argument Filtering:** Added flexible pattern parsing to `build.sh` so tests can be targeted by bare name (e.g., `./build.sh test compress`), file path, or regex combined into a boolean pytest expression (`-k "term1 or term2"`). Added `-v` / `--verbose` flag mapping to `-s --verbose-test`.
* **Pytest Custom Options (`tests/conftest.py`):** Configured `--bless` and `--verbose-test` options via `pytest_addoption`.
* **Golden-Master Test Framework (`tests/test_fixtures.py`):**
* Parses multi-section `.test` fixtures (`=== NATURAL ===`, `=== PYTHON ===`, `=== EXECUTE ===`).
* Validates parsing, lowering to IR0/IR1, and Python code generation against disk snapshots.
* Dynamically executes generated Python classes in-memory with test inputs and asserts outputs against expected values.
* Added rich terminal panels when running in verbose mode.



---

### 2. New Test Fixtures (`tests/fixtures/*.test`)

Added 8 end-to-end test fixtures covering:

* `compress.test`: Multi-operand string joining with delimiters.
* `decide_for.test`: Multi-condition branching (`DECIDE FOR FIRST CONDITION`).
* `decide_on.test`: Value-based switch branching (`DECIDE ON FIRST VALUE OF`).
* `examine.test`: Substring counting and replacement (`GIVING NUMBER`, `REPLACE WITH`).
* `for_loop.test`: Stepped numerical loops (`FOR ... := ... TO ... STEP ...`).
* `if_nested.test`: Compound logical condition evaluation (`AND`/`OR`).
* `math_ops.test`: Decimal arithmetic precision checks.
* `move_edited.test`: Date string formatting/parsing via edit masks.
* `redefine.test`: Overlaid memory slicing via `@property` getters and setters.
* `repeat_loop.test`: Bounded loops with `UNTIL` exit conditions.
* `reset.test`: Typed memory clearing to default initial values.
* `subroutine.test`: `DEFINE SUBROUTINE` block extraction and `PERFORM` calls.

---

### 3. Grammar & Parser Upgrades (`pass1_island.lark`, `pass1_parser.py`, `pass2_dispatcher.py`)

* **Grammar Expansions:**
* Added block syntax rules for `for_block`, `decide_for_block`, `subroutine_block`, and `read_work_block`.
* Added optional block label prefixes (`[label]`) to loops and queries (`L1.`).
* Updated `repeat_block` to support bottom-placed `UNTIL raw_clause` loop terminators.
* Converted `ELSE` to an explicit lexer terminal (`ELSE.2`) to retain it during AST transformation.
* Added `BOOLEAN_LITERAL` (`TRUE`/`FALSE`) and logical operators (`LOGICAL_OR`, `LOGICAL_AND`) to expression grammar.
* Switched decimal literal numbers to parse into Python `Decimal` rather than `float`.


* **New Micro-Parsers:**
* `ForParser`: Parses `:= ... TO ... STEP ...` clauses.
* `StringOpParser`: Parses `COMPRESS`, `EXAMINE`, and `RESET`.
* `DatabaseOpParser`: Expanded with `STORE`, `DELETE`, `UPDATE`, and `GET`.
* `WorkFileParser`: Parses `READ WORK FILE`, `WRITE WORK FILE`, and `CLOSE WORK FILE`.


* **Dispatcher Routing:**
* Routes subroutines into `NaturalModule.subroutines` dictionary rather than `data_areas`.
* Dispatches work files, CRUD ops, and string commands.



---

### 4. AST & Semantic Models (`ir/models.py`, `ir/pass1_models.py`, `ir/semantic.py`, `ir/__init__.py`)

* **IR-0 (Syntactic AST):**
* Added statement models: `ForStatement`, `PerformStatement`, `CompressStatement`, `ExamineStatement`, `ResetStatement`, `DeleteStatement`, `StoreStatement`, `ReadWorkFileStatement`, `WriteWorkFileStatement`, and `CloseWorkFileStatement`.
* Added Pass 1 block models: `ForBlock`, `ReadWorkBlock`, `SubroutineBlock`.


* **IR-1 (Semantic DAG):**
* Added semantic operation models: `ForLoopOp`, `CallSubroutineOp`, `CompressOp`, `ExamineOp`, `ResetOp`, `EntityStoreOp`, `EntityDeleteOp`, `EntityUpdateOp`, `ReadWorkFileOp`, `WriteWorkFileOp`, `CloseWorkFileOp`, and `SubroutineBlockOp`.
* Added `label` support across loop and query iteration operations.



---

### 5. Semantic Lowering Pass (`lowering.py`)

* **Active Loop Context Stack:** Replaced simple string IDs on `self.loop_stack` with `ActiveLoopContext(loop_id, label, entity)` to resolve targets for labelled `ESCAPE BOTTOM (label)` and contextual `UPDATE (label)`.
* **System Variable Lowering:** Lowered `*COUNTER` to iteration counters, `*ISN` to entity IDs, and date/time system variables (`*DATX`, `*TIME`).
* **Logical Operator Mapping:** Added support for `"AND"` and `"OR"` binary operators.

---

### 6. Code Generation (`python_emitter.py`)

* **Dynamic Import Harvesting (`_collect_required_imports`):** Automatically detects if `Decimal`, `date`, `datetime`, `timedelta`, or `os` are referenced, eliminating hardcoded, unused imports.
* **PascalCase Class Naming:** Added `_to_pascal_case()` to ensure module IDs like `mod.decide_on` compile to idiomatic names (`DecideOnContext`).
* **Iteration Counters:** Augmented query iterations with `enumerate(..., 1)` to supply 1-based `loop_counter`.
* **Mock Session Capabilities:** Added `add`, `delete`, and `flush` methods to the standalone runner's `MockSession`.

---

### 7. Clean YAML Serializer & Workspace Regens (`serializer.py`, `workspaces/freight-calc/...`)

* **YAML Pruning:** Added recursive empty collection pruning in `serialize_to_yaml()` to strip empty lists and empty dicts from emitted IR files.
* **Freight Calc Rebuild:** Updated generated `ratecalc.yaml` (IR0/IR1) to omit empty collections, and updated `ratecalc.py` to match the new emitter structure.


--- 

---

### Status Overview Across the 5 Target Categories

| Category | Status | Completion | Summary |
| --- | --- | --- | --- |
| **1. Database Access & Adabas Transactions** | In Progress | ~35% | Basic `FIND`, `READ`, `GET *ISN`, `UPDATE`, `STORE`, and `DELETE` work; transactions and loop hooks remain unhandled. |
| **2. Arithmetic & Data Movement Operations** | **Completed** | **95%** | `SEPARATE`, `EXAMINE TRANSLATE`, `MOVE ALL`, substring slice writes, compound math, and `ROUNDED` arithmetic are fully functional and tested. |
| **3. Program Invocation, Execution & Functions** | Pending | ~20% | `PERFORM` (subroutines) and `CALLNAT` (subprograms) work; `FETCH`, `CALL`, `STOP`, `TERMINATE`, and user functions are unbuilt. |
| **4. Data Types, Redefinitions & Adabas Features** | In Progress | ~40% | Scalar `REDEFINE` (property getters/setters) and basic date edit masks work; periodic groups (`PE`), multiple fields (`MU`), dynamic arrays, and numeric masks are pending. |
| **5. Compiler Architecture & CLI Ergonomics** | **Completed** | **95%** | Unified `ProjectBuilder`, clean CLI command forwarding (`build.sh run`), `ON ERROR` exception wrappers, and all sample workspaces compile cleanly. |

---

### Changes for https://share.gemini.google/j6xMU7MBqGwy

#### Category 2: Arithmetic & Data Movement Operations

* **`SEPARATE`:** Added `SeparateStatement` and `SeparateOp`, parsing source strings, delimiters, and target lists. Lowers directly to Python's `str.split(delimiter, maxsplit)` with target variable unpacking. Tested via `tests/fixtures/separate.test`.
* **`EXAMINE TRANSLATE`:** Added case translation parsing (`TRANSLATE INTO UPPER/LOWER CASE`) in `StringOpParser`, lowering to Python `.upper()` and `.lower()`. Tested via `tests/fixtures/examine_translate.test`.
* **`MOVE ALL`:** Added string/memory block filling via `MoveAllOp`. Computes target variable length from symbol metadata and lowers to character repetition: `ctx.field = str(char) * length`. Tested via `tests/fixtures/move_all_and_substring.test`.
* **Substring Indexing & Slice Assignments:**
* Unified `ExpressionParser` bracket grammar (`VAR_NAME "(" RAW_BRACKET ")"`) to resolve ambiguities between slices `(1:4)`, scalar indices `(1)`, and composite indices `(1.1)`.
* Added support for substring write targets (`#VAR(start:len) := '...'`), lowering to 0-based offset slice splices: `ctx.var[:s] + val + ctx.var[e:]`.


* **Compound Arithmetic & `ROUNDED`:**
* Expanded `MathParser` to accept multi-operand statements (`ADD a b c TO total`).
* Implemented `ROUNDED` execution semantics, lowering decimal math to Python's `Decimal.quantize(..., rounding=ROUND_HALF_UP)` and integer math to `int(round(...))` or `int(a / b)`. Tested via `tests/fixtures/compound_math_rounded.test`.



#### Category 5: Compiler Architecture & CLI Ergonomics

* **Unified Build Orchestration (`ProjectBuilder`):** Eliminated divergent compilation logic between `natural/cli.py` and `natural/orchestrator/builder.py`. `cli.py build` now delegates directly to `ProjectBuilder.compile_workspace()`.
* **CLI Forwarding & Parameter Normalization:**
* Simplified `./build.sh` so commands run directly without redundant subcommands (e.g. `./build.sh run <workspace> <module>` instead of `./build.sh run run ...`).
* Updated `emit_main_block` in `PythonEmitter` to accept both POSIX dashed flags (`--ship-class`) and Pythonic snake_case flags (`--ship_class`).


* **ORM Fallback Model Generation:** Fixed dynamic model fallbacks in `target_orm.py` to prevent SQLAlchemy mapper crashes on internal attributes like `__path__` by rejecting dunder lookups and providing default primary keys.
* **Error Handling (`ON ERROR`):**
* Added `on_error_block` to `pass1_island.lark`, `OnErrorBlockStatement` to IR0, and `OnErrorOp` to IR1.
* Lowered modules with error handlers into enclosing `try: ... except Exception as natural_err:` structures. Lowered `ESCAPE ROUTINE` inside handlers to immediate context returns (`return ctx`). Tested via `tests/fixtures/on_error.test`.


* **Workspace Validation:**
* `workspaces/error-test/PAYCALC.nsp`: Resolves unqualified DDM fields (`SALARY`, `NAME`) via active query loop scopes.
* `workspaces/calendar-end-of-month/`: Resolved line continuations (`/`), complex `WRITE` tabs (`5T`, `35T`), and date redefinitions across `EOM1.nsp`, `EOM2.nsp`, and `SAMPLE.nsp`.



---

### What Needs To Be Done

#### Category 1: Database Access & Adabas Transactions

* **Transaction Demarcation:**
* Add AST/IR nodes for `END TRANSACTION` and `BACKOUT TRANSACTION`.
* Lower to `session.commit()` and `session.rollback()`.


* **Loop Control Hooks:**
* Parse `AT START OF DATA`, `AT END OF DATA`, and `AT BREAK (field)` blocks inside query iteration loops.
* Lower to loop boundary checks (e.g., executing on `loop_idx == 1`, tracking previous field values for break triggers, or post-loop execution).


* **Search Criteria & Multi-Field Descriptors:**
* Extend `find_parser.py` beyond single equality (`WITH field = val`) to support boolean descriptor queries: `WITH CLASS = #A AND ZONE = #B`, ranges (`THRU`), and superdescriptors.


* **Read Variants:**
* Add parsing and execution for `HISTOGRAM` (reading field descriptors/counts without fetching full database records) and `GET SAME` (re-reading the active ISN with record hold).



#### Category 3: Program Invocation, Modular Execution & Functions

* **Program Invocations (`FETCH`, `CALL`):**
* `FETCH` and `FETCH RETURN`: Support transferring control to standalone executable programs (`.nsp`), passing state via a shared context or global data area.
* `CALL`: Support external non-Natural foreign calls (e.g., invoking legacy C or external shared libraries).


* **User-Defined Functions:**
* Parse `DEFINE FUNCTION ... RETURNS ...` blocks.
* Lower functions to standalone Python utility methods with typed returns and inline caller invocation in `ExpressionParser`.


* **Program Termination:**
* Map `STOP` (abrupt halt of execution) and `TERMINATE` (session shutdown) to `sys.exit()` or top-level workflow returns.



#### Category 4: Data Types, Redefinitions & Adabas Features

* **Periodic Groups (`PE`) & Multiple-Value Fields (`MU`):**
* Support array indices on Adabas view fields (`LANG(1:6)` or dynamic offsets `LANG(#OFFSET:#OFFSET + 5)`).
* Map nested periodic groups to SQLAlchemy relationship tables or JSON/Array column collections in `ORMEmitter`.


* **Dynamic Variables & Memory Allocation:**
* Support dynamic alphanumeric types: `(A) DYNAMIC`.
* Implement array allocation statements: `EXPAND ARRAY`, `REDUCE ARRAY`, and `RESIZE ARRAY`.


* **Numeric & Currency Edit Masks:**
* Extend `PythonEmitter._convert_edit_mask()` beyond date patterns (`YYYYMMDD`) to parse numeric formatting strings: `(EM=ZZZ,ZZ9.99-)`, leading zero suppressions, and currency indicators.


---
# Chat https://share.gemini.google/Cg6ZzRT29xob

This commit transitions the compiler from a single-file prototype into an end-to-end multi-module compiler with expanded Adabas transaction handling, compound query lowering, correct loop semantics, and a multi-file integration test harness.

---

---

### Core Areas of Change

#### 1. Database Access & Adabas Transactions

* **Transaction Control Primitives:** Added AST/IR nodes and codegen for `END TRANSACTION` (`session.commit()`) and `BACKOUT TRANSACTION` (`session.rollback()`).
* **Active Record Refresh:** Added `GET SAME` support, lowering to `session.refresh(record)`.
* **Compound Search & Descriptor Ranges:**
* Replaced the single-equality `FIND` parser with full boolean expression parsing (`WITH (CLASS = #A AND ZONE = #B) OR ...`).
* Added `THRU` range filtering to `READ` clauses (`STARTING FROM ... THRU ...`), lowering to composite SQL `>=` and `<=` range criteria.


* **Loop Demarcation Hooks:** Added island grammar blocks and lowering for `AT START OF DATA` (`if loop_idx == 1:`) and `AT END OF DATA` (`if loop_counter > 0:`).

#### 2. Program Invocation & Lifecycle Control

* **Inter-Module `CALLNAT` Compilation:** Restored the `CallProgramOp` pipeline from AST lowering to codegen. Calls emit imports (`from subprog import execute_subprog`) and invoke child subprograms with the shared context.
* **Program Termination:** Added `STOP` and `TERMINATE` statement handling, lowering directly to `sys.exit(0)`.
* **Post-Test Loop Semantics:** Corrected `REPEAT ... UNTIL` lowering. The compiler now detects bottom-placed `UNTIL` clauses (`UNTIL_POST`) and emits `while True:` blocks with terminal `if <cond>: break` checks rather than pre-test `while not (<cond>):` loops.

#### 3. Data Representation, Arrays & Formatting

* **Multi-Dimensional & Array Indexing:** Added support for 1-based array subscripts (`array_indices` and `target_indices`), converting 1-based Natural indices (`LANG(1.1)`) to 0-based Python subscripts (`record.lang[(1 - 1)][(1 - 1)]`).
* **Numeric & Currency Edit Masks:** Extended `MOVE EDITED` in `PythonEmitter` to parse numeric format strings (e.g., `(EM=ZZZ,ZZ9.99-)`), generating formatted string interpolation with thousands commas, decimal quantization, and trailing negative signs.
* **Dynamic Arrays:** Updated `data_parser.py` and AST lowering to accept `(A) DYNAMIC` variables, and added `RESIZE ARRAY` lowering to `[None] * int(size)`.
* **Delimited Strings:** Fixed default `COMPRESS` behavior to join with a single space delimiter (`' '`) rather than an empty string when no delimiter clause is specified.

#### 4. Test Harness & Build Architecture

* **Multi-File Workspace Fixtures:** Overhauled `tests/test_fixtures.py` to support multi-module workspaces within individual `.test` files using tagged headers (`=== NATURAL: <file> ===`, `=== PYTHON: <file> ===`). Each test dynamically builds in a temporary directory via `ProjectBuilder`.
* **Topological DAG Build Graph:** Prevented false cyclic dependencies in `ProjectBuilder` by filtering out internal inline scopes (`INLINE_LOCAL`, `INLINE_PARAMETER`, `INLINE_GLOBAL`).
* **Chained Mock Database Engine:** Implemented `MockQuery` (supporting chained `.filter()` and `.limit()` calls) and extended `MockSession` (`commit`, `rollback`, `refresh`) so compiled SQLAlchemy queries run in-memory without database dependencies.

---

### Component-by-Component Diff Summary

| File / Component | Primary Changes |
| --- | --- |
| `src/natural/grammar/pass1_island.lark` | Added `at_start_block` and `at_end_block`; updated `raw_statement` lookahead boundaries. |
| `src/natural/ir/pass1_models.py` | Added `AtStartBlock`, `AtEndBlock`, and `is_post_test` flag on `RepeatBlock`. |
| `src/natural/ir/models.py` | Added AST statement models (`EndTransaction`, `BackoutTransaction`, `GetSame`, `Stop`, `Terminate`, `AtStartOfData`, `AtEndOfData`, `ResizeArray`); added `criteria` to `FindStatement` and `array_indices` to `Expression`. |
| `src/natural/ir/semantic.py` | Added semantic IR1 operations (`TransactionOp`, `EntityRefreshOp`, `TerminateOp`, `AtStartOfDataOp`, `AtEndOfDataOp`, `ResizeArrayOp`, `CallProgramOp`); added `target_indices` to `AssignOp`. |
| `src/natural/ir/__init__.py` | Exported all new AST statements and Pass 1 models. |
| `src/natural/normalizer/pass1_parser.py` | Transformed start/end blocks; detected bottom-placed `UNTIL` clauses for post-test loops. |
| `src/natural/normalizer/pass2_dispatcher.py` | Routed lifecycle, transaction, array resizing, and loop control blocks to their statement parsers. |
| `src/natural/normalizer/parsers/find_parser.py` | Refactored `FIND` parsing to delegate complex `WITH` search criteria to `ExpressionParser`. |
| `src/natural/normalizer/parsers/database_parser.py` | Parsed `GET SAME`, `END TRANSACTION`, and `BACKOUT TRANSACTION`. |
| `src/natural/normalizer/parsers/data_parser.py` | Added support for `DYNAMIC` memory allocation in field format parsing. |
| `src/natural/normalizer/lowering.py` | Lowered all newly introduced statements into IR1 semantic operations; handled array subscripts and range predicates. |
| `src/natural/codegen/python_emitter.py` | Implemented codegen for transactions, program calls, array subscripts, post-test loops, and numeric edit masks. Fixed `datetime` import leakage. |
| `src/natural/orchestrator/builder.py` | Filtered out inline scopes from workspace dependency graph generation. |
| `build/build/python/target_orm.py` | Added fallback dynamic declarative base with generic `__getattr__` column fallbacks. |
| `tests/test_fixtures.py` | Overhauled fixture runner for multi-file `.test` workspaces and chained `MockQuery` execution. |
| `tests/fixtures/*.test` | Added `find_compound.test`, `callnat_multi.test`, `transaction.test`, `numeric_edit_mask.test`; updated `repeat_loop.test`. |


---

# Chat https://share.gemini.google/G3zPMAvQWhMV

The changes across the diff implement Phase 1 (Database Access & Adabas Transactions), establishing support for control breaks (`AT BREAK`), occurrence aggregations (`HISTOGRAM`), row-level filtering (`ACCEPT`/`REJECT`), and multi-column superdescriptors.

---

### 1. Grammar & Pass 1 Island Parser

* **Grammar Extensions (`src/natural/grammar/pass1_island.lark`):**
* Added block definitions for `histogram_block`, `at_break_block`, and `before_break_block`.
* Enforced mandatory `raw_clause` syntax on `at_break_block` (`_AT_BREAK raw_clause statement* _END_BREAK`), preventing the LALR parser from reducing epsilon and consuming the break field as a statement payload.
* Updated `raw_statement` negative lookahead to exclude `HISTOGRAM`, `BREAK`, `AT BREAK`, and `BEFORE BREAK`.


* **Pass 1 AST & Visitor (`src/natural/ir/pass1_models.py`, `src/natural/normalizer/pass1_parser.py`):**
* Added `HistogramBlock`, `AtBreakBlock`, and `BeforeBreakBlock` node schemas.
* Added corresponding visitor transformation methods in `IslandTransformer` while excluding the new blocks from generic loop body captures.



---

### 2. Micro-Parsers & Workspace Schema Resolution

* **Expression Parser (`src/natural/normalizer/parsers/expression_parser.py`):**
* Elevated the terminal precedence of `SYSTEM_VAR.2` over `VAR_NAME`, ensuring system variables with leading asterisks (such as `*NUMBER`) resolve correctly instead of falling back to unresolved variable references (`*number_UNRESOLVED`).
* Added `tuple_expr: "(" expr ("," expr)+ ")"` to parse multi-variable tuples.


* **Database & Read Parsers (`src/natural/normalizer/parsers/database_parser.py`, `src/natural/normalizer/parsers/read_parser.py`):**
* Implemented `parse_accept` and `parse_reject` to parse row predicates (`ACCEPT IF <crit>` and `REJECT IF <crit>`).
* Implemented `parse_histogram` to parse descriptor counting clauses (`HISTOGRAM (limit) VIEW FOR DESCRIPTOR [STARTING FROM ...] [THRU ...]`).


* **DDM Superdescriptors (`src/natural/normalizer/workspace.py`):**
* Enhanced DDM regex matching to parse remainder definitions, extracting constituent composite fields from parentheses (e.g., `(NAME(1:10), DEPT(1:4))`) into `DataField.sub_fields`.



---

### 3. IR Models & Semantic Lowering

* **IR0 & IR1 Nodes (`src/natural/ir/models.py`, `src/natural/ir/semantic.py`, `src/natural/ir/__init__.py`):**
* Defined AST statement nodes `HistogramStatement`, `AtBreakStatement`, `AcceptStatement`, and `RejectStatement`.
* Defined semantic IR1 nodes `AtBreakOp` and augmented `QueryIterationOp` with `descriptor` and `cardinality="histogram"`. Added `target_indices` to `AssignOp`.


* **Statement Dispatching (`src/natural/normalizer/pass2_dispatcher.py`):**
* Routed `HistogramBlock`, `AtBreakBlock`, and `BeforeBreakBlock` into their respective statement models.
* Routed `ACCEPT` and `REJECT` raw statements into `database_parser`.


* **Semantic Normalization (`src/natural/normalizer/lowering.py`):**
* **System Variables:** Promoted asterisk-prefixed ref expressions to `sys_var`. Lowered `*NUMBER` to `record.number` when evaluated inside active histogram queries (`is_histogram=True`).
* **Superdescriptor Slicing:** When lowering equality comparisons on composite fields, the lowering pass looks up subfields in the active DDM and decomposes the query into compound conjunctions (`AND`) matching exact substring slices (`ctx.key[(start - 1):(start - 1) + len]`).
* **Filter Inversion:** Lowered `AcceptStatement` to `BranchOp(condition=not(criteria), then_branch=[ContinueOp])` and `RejectStatement` to `BranchOp(condition=criteria, then_branch=[ContinueOp])`.
* **Iteration Loops:** Lowered `HistogramStatement` into `QueryIterationOp(cardinality="histogram", ...)`.



---

### 4. Code Generation & Emitters

* **Query & Break Operations (`src/natural/codegen/python_emitter.py`):**
* **`AT BREAK`:** Emitted pre-loop state initialization (`_prev_<field> = None`), break change triggers (`if _prev_<field> is not None and <field> != _prev_<field>:`), and post-iteration cache updates (`_prev_<field> = <field>`).
* **`HISTOGRAM`:** Lowered histogram queries into SQLAlchemy aggregate queries:
```python
session.query(Model.col.label('col'), func.count(Model.col).label('number')).group_by(Model.col).limit(...)

```


* **Expressions:** Added code emission for `tuple` and `not` operators, and resolved `record.*` references directly.


* **Import Precision:**
* Added automatic `from sqlalchemy import func` harvesting when histogram operations are present.
* Excluded `sym.scope == "entity_field"` from `_collect_required_imports`, preventing entity schema columns (such as `SALARY (P7.2)`) from leaking unused `from decimal import Decimal` imports into modules that only handle integer or alphanumeric state.



---

### 5. Test Harness & Integration Fixtures

* **Mock Database Session (`tests/test_fixtures.py`):**
* Extended `MockQuery` to chain `.group_by(*args)` and `.all()`.
* Updated `MockSession` to accept test case fixture records and construct mock entity objects for dynamic in-memory execution assertions.


* **Feature Test Fixtures (`tests/fixtures/*.test`):**
* `at_break.test`: Validates `BEFORE BREAK PROCESSING` and `AT BREAK (DEPT)` execution against consecutive records.
* `accept_reject.test`: Validates filter rejection (`REJECT IF SALARY < 1000`) and acceptance (`ACCEPT IF STATUS = 'ACTIVE'`).
* `histogram.test`: Validates descriptor grouping and `*NUMBER` occurrences.
* `superdescriptor.test`: Validates decomposition of `SEC-KEY = #KEY` into multiple SQL column slices.



---

### Verification and Execution Steps

Run the test suite to execute in-memory compilation and dynamic validation against the Phase 1 target features:

```bash
# 1. Run the 4 Phase 1 feature fixtures
./build.sh test at_break accept_reject histogram superdescriptor

# 2. Run the complete regression suite across all 25 fixtures
./build.sh test

# 3. Verify workspace build compatibility
./build.sh run build workspaces/freight-calc --diff

```


---

# Chat - https://share.gemini.google/PNTS3MoUGtHd

Make "MOVE BY NAME" work

---

# Chat - https://share.gemini.google/cTMefFE2SGw0

### Summary of Changes

* **Exponentiation & Modulo Operators (`expression_parser.py`, `lowering.py`, `python_emitter.py`)**:
* Added grammar rules and token precedence for exponentiation (`**`, `^`) above standard multiplication.
* Added `%` and `MOD` token recognition to `MULT_OP`, lowering to Python `%` via the `"modulo"` semantic operation.
* Added tests in `tests/fixtures/exponentiation.test`.


* **Arithmetic `GIVING` & `DIVIDE ... REMAINDER` (`math_parser.py`)**:
* Updated `MathParser` regex and logic to handle explicit destination targets via `GIVING <var>`.
* Added `REMAINDER <var>` extraction for `DIVIDE` statements, emitting a preceding modulo assignment (`%`) before the quotient assignment to protect mutated dividends.


* **`COMPRESS ... LEAVING NO SPACE` (`string_parser.py`, `models.py`, `semantic.py`, `lowering.py`, `python_emitter.py`)**:
* Added `LEAVING NO [SPACE]` flag parsing in `StringOpParser`.
* Propagated `leaving_no_space: bool` through `CompressStatement` (IR0) and `CompressOp` (IR1).
* Lowered code generation to join with `''` instead of the default `' '`.
* Added tests in `tests/fixtures/compress_leaving_no_space.test`.


* **Robust String-to-Numeric Unmasking (`python_emitter.py`)**:
* Overhauled string-to-decimal and string-to-integer conversion logic.
* Correctly strips non-numeric decorative characters (`$`, `,`, spaces, `+`).
* Identifies and preserves negative values from trailing signs (`-`), accounting suffixes (`CR`, `DB`), and parenthesized numbers (`(val)`).
* Automatically flags `needs_decimal` import harvesting when string-to-decimal conversions occur.
* Added tests in `tests/fixtures/move_unmask_decimal.test`.

---

# Chat - https://share.gemini.google/ezqi9QyKhKn6

### Summary of Changes

* **Positional By-Reference `CALLNAT` Parameter Synchronization:**
* **Signature Introspection (`workspace.py`):** Added `get_subprogram_parameters()` to parse target `.nsn`/`.nsp` modules and resolve ordered parameter definitions from `DEFINE DATA PARAMETER`.
* **Semantic Lowering (`lowering.py`):** Updated `CallProgramOp` to construct `CallArgBinding` entries, positionally mapping caller expressions to callee parameters while identifying mutable lvalues for writeback.
* **Code Generation (`python_emitter.py`):** Emitted isolated callee context instantiation (`_<prog>_ctx = <Prog>Context()`), inbound parameter assignments, callee execution, and outbound synchronization of mutated arguments back to the caller context.


* **Program Chaining & Flow Transfer (`FETCH` / `FETCH RETURN`):**
* **AST & IR Models (`models.py`, `semantic.py`):** Added `FetchStatement` to IR0 and `FetchOp` to IR1, capturing program targets, return flags, and argument bindings.
* **Parsing & Dispatch (`pass2_dispatcher.py`):** Added regex parsing for `FETCH` and `FETCH RETURN` statements with positional arguments.
* **Emission & Execution Control (`python_emitter.py`):** Generated callee context invocation for both forms, immediately emitting an early `return ctx` on terminal `FETCH` to halt caller control flow.


* **User-Defined Functions (`DEFINE FUNCTION`):**
* **Grammar & Dispatch (`pass1_island.lark`, `pass1_parser.py`, `pass2_dispatcher.py`):** Added grammar rules and AST structures for `DEFINE FUNCTION ... RETURNS (...)` blocks.
* **Semantic Lowering (`lowering.py`):** Lowered functions into `FunctionBlockOp` with typed signatures and parameters. Mapped assignments to the function name into typed `ReturnOp(expr=...)`.
* **Emission & Invocations (`python_emitter.py`, `expression_parser.py`):** Emitted top-level typed Python functions (`def fn_<name>(...) -> <Type>:`) and lowered `func_call` AST nodes into inline Python invocations.


* **Parser & Pipeline Hardening:**
* **Identifier Character Sets (`expression_parser.py`):** Allowed `#` within the body of variable and function identifiers (e.g., `FN#CALC_TAX`).
* **Parenthesis-Aware Argument Splitting (`expression_parser.py`):** Added `_split_args()` to safely parse comma-separated arguments containing nested parentheses or quoted strings.
* **Recursive AST Dependency Scanning (`builder.py`):** Recursively walked all nested statement blocks, subroutines, and functions to register `CALLNAT`, `FETCH`, and view dependencies for topological sorting.
* **Recursive Metadata Harvesting (`python_emitter.py`):** Traversed full operation trees to guarantee imports for nested program calls, ORM views, and functions.


* **Test Suite Updates:**
* Added `tests/fixtures/callnat_by_ref.test`, `tests/fixtures/fetch_control.test`, and `tests/fixtures/user_function.test`.
* Re-baselined `tests/fixtures/callnat_multi.test` to reflect the isolated context parameter passing model.


---
# Chat - https://share.gemini.google/FoTS8JABI6f0

All requirements outlined in **Phase 4: Advanced Schema, Arrays & Adabas Complex Types** are fully implemented, verified, and passing across the test suite.

| Feature | Specified Requirement | Implementation Component | Status |
| --- | --- | --- | --- |
| **4.1 PE / MU Schema** | Parse array occurrences in DDM definitions (`(1:6)`, `PE (1:5)`). | `workspace.py` (`pe_pattern`, `range_pattern`, `DataField.is_periodic`, `is_multiple`). | **Complete** |
| **4.1 ORM Emission** | Map MU & PE to SQLAlchemy `JSON` columns with typed lambda defaults (`[""]`, `[0]`, `[Decimal('0')]`). | `orm_emitter.py` (`Column('col', JSON, default=lambda: ...)`). | **Complete** |
| **4.1 Subscript Lowering** | Lower Natural 1-based indexing (`LANG(1)`, `LANG(#OFFSET)`) to Python 0-based subscripts (`[0]`, `[(ctx.offset - 1)]`). | `expression_parser.py` (`array_indices`), `lowering.py`, `python_emitter.py`. | **Complete** |
| **4.1 Test Fixture** | Verify read, write, and dynamic subscripting in Adabas queries. | `tests/fixtures/adabas_periodic_group.test` passing in-memory execution. | **Complete** |
| **4.2 Dynamic Slices** | Parse arbitrary dynamic bounds `#STR(#START:#LEN)` in brackets without static token assumptions. | `expression_parser.py` (`var_with_bracket` delegating both sides of `:` to `ExpressionParser`). | **Complete** |
| **4.2 Semantic IR** | Dynamic `SemanticSubstring.start` and `length` trees. | `semantic.py` (`SemanticSubstring`), `lowering.py`. | **Complete** |
| **4.2 Slice Codegen** | Emit dynamic slice bounds `[s:s + l]` and slice mutations `target[:s] + val + target[s + l:]`. | `python_emitter.py` (`emit_expr`, `AssignOp` target substring branch). | **Complete** |
| **4.2 Test Fixture** | Assert dynamic reads and slice writes. | `tests/fixtures/dynamic_substring.test` passing in-memory execution. | **Complete** |
| **4.3 Array Statements** | Route `EXPAND ARRAY`, `REDUCE ARRAY`, and `RESIZE ARRAY` with action verbs. | `pass2_dispatcher.py`, `models.py`, `semantic.py` (`ResizeArrayOp.action`). | **Complete** |
| **4.3 Stateful Lifecycle** | Preserve items on `EXPAND` (`extend([None] * diff)`), truncate on `REDUCE` (`del arr[sz:]`). | `python_emitter.py` (`emit_operation` on `ResizeArrayOp`). | **Complete** |
| **4.3 Array Occurrence** | Evaluate `*OCC(#ARR)` dynamically. | `expression_parser.py` (`SYSTEM_VAR.2`), `lowering.py` (maps `*OCC` to `len(ctx.arr)`). | **Complete** |
| **4.3 Test Fixture** | Verify state retention across expansions and truncation on reduction. | `tests/fixtures/array_lifecycle.test` passing in-memory execution. | **Complete** |

---

### Key Architectural Fixes Delivered

1. **Comment Preprocessor Lookahead (`preprocessor.py`)**:
* Natural dynamic array syntax `(A10/*)` contains `/*`, which previously collided with the C-style block comment stripper and corrupted field definitions. The negative lookahead `r"/\*(?!\s*\)).*?(?:\*/|$)"` correctly preserves array bounds.


2. **Subscript Literal Optimization (`python_emitter.py`)**:
* Constant 1-based literals optimize directly to static Python indices (`record.lang[0]`) rather than generating verbose arithmetic (`record.lang[(1 - 1)]`), while keeping dynamic expressions enclosed in offset subtraction (`record.lang[(ctx.offset - 1)]`).


3. **Context Array Initialization (`python_emitter.py`)**:
* Symbols flagged with `is_array = True` now initialize to `[]` inside `__init__` rather than scalar defaults (`""` or `0`), preventing runtime crashes when calling `.extend()` or `len()`.


4. **Sub-Parser Reentrancy (`expression_parser.py`)**:
* Bracket parsing now uses a module-level cached `ExpressionParser` instance instead of instantiating new Lark grammars on every slice evaluation.



---

# Chat - https://share.gemini.google/ojUYz7SrV87D

### Summary of Completed Work

#### 1. Formatted Output & Column Tabulation (Feature 5.1)

* **Parser Tokenization (`src/natural/normalizer/parsers/io_parser.py`)**:
* Added `WRITE_TAB.5: /\d+[Tt]/` and `NEWLINE_SPLIT: "/"` terminals, elevating terminal priority above `NUMBER.2` to eliminate token collisions on entries like `5T`.
* Updated `IOTransformer` to convert tabs and slash continuations into typed `Expression(kind="tab", value=col)` and `Expression(kind="newline", value="/")` nodes, while delegating bracket expressions to `ExpressionParser` for array subscript support.


* **IR Schema (`src/natural/ir/models.py`, `src/natural/ir/semantic.py`)**:
* Added `tab` and `newline` kinds to syntactic `Expression`.
* Introduced `WriteOp(operands, is_write)` into IR1 semantic operations.

---

---

# Chat - https://share.gemini.google/e3X7VFgdYL99 - Calendar End-of-Month & 2D Slices

### Summary of Changes

- **Inline View Resolution (`lowering.py`, `workspace.py`)**:
    - Implemented `_find_view_definition` in `SemanticLoweringPass` to inspect inline `VIEW OF <DDM>` blocks declared in `DEFINE DATA`.
    - Mapped inline views directly to their backing DDM models (`MYVIEW` -> `Employees`), resolving unqualified view field references without leaking `_UNRESOLVED` fallbacks.

- **Primary Key Lookups (`GET <VIEW> *ISN`)**:
    - Added `EntityGetOp` to IR1 models and exported it via `natural.ir`.
    - Lowered `GetStatement` to `session.get(<Model>, record.id)`.
    - Scoped entity references in `PythonEmitter` so secondary views accessed via `GET` resolve to their respective record handles (`myview2_record.<col>`) rather than colliding with the active query loop iterator.

- **2D Adabas Array Slicing & Subscripts (`expression_parser.py`, `python_emitter.py`)**:
    - Enhanced `ExpressionTransformer.var_with_bracket` to detect dot-separated 2D array coordinates (`occurrence.element` or `occurrence.start:end`).
    - Separated scalar substring write semantics from array bounds slicing.
    - Aligned array ranges with Natural 1-based inclusive upper bounds, lowering `(start:end)` to Python `[start - 1:end]` instead of relative length offset addition (`[s:s + len]`).

- **Dynamic Tabulation Width Calculations (`python_emitter.py`)**:
    - Replaced compile-time string evaluation in `WriteOp` emission with dynamic runtime length subtraction (`34 - len("    " + str(...))`), preventing syntax-literal length leakage into emitted code.

- **Declaration Initializers (`INIT <val>`)**:
    - Propagated `DataField.init_val` through `Symbol.init_val` in `lowering.py`.
    - Generated typed initialization expressions in `Context.__init__` for integers, decimals, booleans, and dates (`*DATX`, `D'...'`).

- **Testing & Tooling**:
    - Added `tests/fixtures/calendar_sample.test` covering end-to-end multi-file compilation, 2D array indexing, and database sync.
    - Added `.get()` implementation to `MockSession` in `tests/test_fixtures.py` and `emit_main_block`.
    - Re-generated build targets across `workspaces/calendar-end-of-month`.


* **Semantic Lowering (`src/natural/normalizer/lowering.py`)**:
* Lowered `WriteStatement` and `PrintStatement` into `WriteOp`, converting tabulation targets and newline indicators into semantic expressions.


* **Code Generation (`src/natural/codegen/python_emitter.py`)**:
* Emitted partitioned `print()` statements split across newline boundaries.
* Added dynamic column tracking that calculates character widths and emits padding arithmetic:
```python
print(" " * 4 + "A" + " " * (34 - len("    A")) + "B")
print(" " * 4 + "C")

```




* **Test Fixture (`tests/fixtures/io_tabulation.test`)**:
* Added end-to-end golden master test verifying tab alignment and execution against in-memory contexts.



---

#### 2. Scoped Subroutine Error Handling (Feature 5.2)

* **AST Dispatching (`src/natural/ir/models.py`, `src/natural/normalizer/pass2_dispatcher.py`)**:
* Added `on_error: Optional[OnErrorBlockStatement]` to `SubroutineDefinition`.
* Updated `Pass2Dispatcher.lower_module()` to intercept `OnErrorBlock` nested within `SubroutineBlock`, routing it directly to `SubroutineDefinition.on_error` instead of leaking into the subroutine statement list or top-level module scope.


* **Semantic Lowering (`src/natural/ir/semantic.py`, `src/natural/normalizer/lowering.py`)**:
* Added `on_error: Optional[OnErrorOp]` to `SubroutineBlockOp`.
* Lowered subroutine error statements into isolated `OnErrorOp` nodes during module normalization.


* **Code Generation & Project Builder (`src/natural/codegen/python_emitter.py`, `src/natural/orchestrator/builder.py`)**:
* Wrapped generated `sub_<name>()` bodies in localized `try: ... except Exception as natural_err:` handlers when `on_error` is present, returning the mutated context without wrapping the caller `execute_<module>()` entry point.
* Extended `_collect_required_imports()`, `walk_ops_for_metadata()`, and DAG dependency scanning to traverse subroutine `on_error` statement trees.


* **Test Fixture (`tests/fixtures/on_error_subroutine.test`)**:
* Added test fixture validating that exceptions inside subroutines trigger localized recovery handlers while caller execution continues sequentially.



---

#### 3. Verification & Regressions

* The entire test suite passed with zero regressions: **38 passed in 14.06s**.

---

---

# Chat - Python Emitter Modular Architecture Refactor - https://share.gemini.google/Y1bJ4n1Pylra

Decomposed the monolithic `src/natural/codegen/python_emitter.py` (~650 lines) into a modular, domain-driven package (`src/natural/codegen/python_emitter/`) isolating indentation and context state, dependency harvesting, expression translation, specialized formatting engines, and statement emission handlers.

---

### Summary of Changes

* **Buffer & Context Encapsulation (`python_emitter/context.py`)**:
* Introduced `CodeWriter` to manage line buffers and scoped block indentation via a clean context manager (`with ctx.indent():`).
* Implemented `EmitterContext` to hold symbol tables, loop-view context stacks, PascalCase/snake_case naming helpers, type hint conversions, and contextual reference resolution (`resolve_ref`) distinguishing between loop cursors, context fields, and ORM entity models.


* **Dependency & Import Harvesting (`python_emitter/harvester.py`)**:
* Isolated `ImportHarvester` to perform pre-emission traversals over the IR1 operation tree.
* Detects required standard library imports (`decimal.Decimal`, `decimal.ROUND_HALF_UP`, `datetime.date`, `datetime.datetime`, `datetime.timedelta`, `os`, `sys`), third-party tools (`sqlalchemy.func`), and external dependencies (ORM entity classes and child subprograms/contexts).


* **Expression Translation Engine (`python_emitter/expressions.py`)**:
* Isolated `PythonExpressionEmitter` to lower `SemanticExpression` trees into valid Python syntax.
* Encapsulates 1-based to 0-based array subscript arithmetic (`LANG(1.1)` -> `record.lang[0][0]`), dynamic string and array slicing, operator translations, built-in functions, and date offset arithmetic via `timedelta`.


* **Formatting Subsystems (`python_emitter/formatters.py`)**:
* Extracted date edit mask conversion (`convert_edit_mask`) for `strftime`/`strptime`.
* Extracted financial and numeric mask formatting (`format_numeric_edit_mask`), handling currency prefixes (`$`), zero suppression (`ZZZ,ZZ9.99`), thousands commas, and accounting sign tokens (`CR`, `DB`, trailing/leading `-` and `+`).


* **Domain-Specific Operation Handlers (`python_emitter/handlers/`)**:
* Replaced the monolithic `if isinstance(op, ...)` chain with an $O(1)$ dispatch registry (`DEFAULT_OPERATION_HANDLERS`) mapping IR1 semantic operations directly to targeted emitter functions:
* **`handlers/memory.py`**: `AssignOp` (including substring assignments, slice mutations, and numeric unmasking), `MoveAllOp`, `CompressOp`, `SeparateOp`, `ExamineOp`, `ResetOp`, `ResizeArrayOp`.
* **`handlers/database.py`**: `QueryIterationOp` (cursor queries and `func.count` histogram queries), `EntityGetOp`, `EntityRefreshOp`, `EntityUpdateOp`, `EntityStoreOp`, `EntityDeleteOp`, `TransactionOp`, `AtStartOfDataOp`, `AtEndOfDataOp`, and `AtBreakOp`.
* **`handlers/control_flow.py`**: `BranchOp`, `LoopOp` (pre-test and post-test bounded loops), `ForLoopOp`, `BreakOp`, `ContinueOp`, `ReturnOp`, and `TerminateOp`.
* **`handlers/invocation.py`**: `CallSubroutineOp`, `CallProgramOp`, and `FetchOp` (with caller-callee argument binding and by-reference writeback).
* **`handlers/io.py`**: `WriteOp` (with dynamic runtime column width tab calculations), `ReadWorkFileOp`, `WriteWorkFileOp`, and `CloseWorkFileOp`.




* **Assembly Orchestrator & Public API (`python_emitter/engine.py`, `python_emitter/__init__.py`)**:
* Structured `PythonEmitter` to coordinate the generation of file headers, user-defined functions, typed context classes with `@property` memory redefinitions, isolated subroutine methods, entrypoint execution functions, and the optional standalone `__main__` runner block.
* Re-exported `PythonEmitter`, `EmitterContext`, `CodeWriter`, `PythonExpressionEmitter`, and `ImportHarvester` from `natural.codegen.python_emitter` for 100% backward compatibility with `builder.py`, `cli.py`, and test fixtures.


---

# Chat - Shared Codegen Utilities & ORM Emitter Decoupling - https://share.gemini.google/VBSlKCDuocr8

Extracted shared code generation primitives into `src/natural/codegen/common/`, preserving a clean separation of concerns between schema generation (`ORMEmitter`) and module logic generation (`PythonEmitter`) while eliminating duplicated line-buffering and naming logic.

---

### Summary of Changes

* **Shared Code Writer (`codegen/common/writer.py`)**:
* Implemented `CodeWriter` with scoped indentation management (`with writer.indent():`), offset-based line emission, and full buffer materialization (`get_code()`).
* Replaces manual whitespace multiplication (`"    " * indent_level`) across both emitters.


* **Unified Python Identifier Sanitization (`codegen/common/naming.py`)**:
* Centralized Python keyword escaping (`clean_name`) to prevent keyword collisions (e.g., mapping `CLASS` $\to$ `class_`).
* Added shared function identifier normalization (`clean_func_name`) and class PascalCase formatting (`to_pascal_case`).


* **ORMEmitter Modernization (`codegen/orm_emitter.py`)**:
* Refactored `ORMEmitter` to compose `CodeWriter` and use shared naming utilities.
* Retained dedicated singleton lifecycle (collating workspace DDMs into `target_orm.py`) completely independent of IR1 behavioral logic.


* **PythonEmitter Context Integration (`codegen/python_emitter/context.py`)**:
* Replaced internal writer logic in `EmitterContext` with `CodeWriter` and delegated naming transformations to `codegen.common`.
* Ensures naming consistency between generated ORM models and runtime query references without coupling their compilation pipelines.