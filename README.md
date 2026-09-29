# Natural-to-Semantic-IR Compiler Framework

This is based on a many [chats with gemini](CHATS.md).

A deterministic compilation and code-generation framework designed to migrate legacy Software AG Natural applications into typed Python and SQLAlchemy architectures.

Instead of relying on fragile regex replacements or heuristic text rewriting, this compiler parses Natural source code into a syntactic Abstract Syntax Tree (IR0), lowers it into a validated Semantic Intermediate Representation (IR1), and emits idiomatic, type-annotated Python business logic alongside SQLAlchemy declarative models. It includes a topological DAG workspace builder, a comprehensive 39-suite golden-master test framework, and an automated baseline blessing workflow.

---

## Translation Example

### Legacy Natural Input (`SAMPLE.nsp`):

```natural
DEFINE DATA LOCAL
01 #OFFSET (I2) INIT<1>
01 MYVIEW VIEW OF EMPLOYEES
  02 NAME
  02 LANG (#OFFSET:#OFFSET + 5)
  02 LANG (1:1)
01 MYVIEW2 VIEW OF EMPLOYEES
  02 LANG (1:6)
END-DEFINE

READ (1) MYVIEW BY NAME STARTING FROM 'SMITH'
  WRITE 5T LANG (#OFFSET.#OFFSET:#OFFSET + 5) 35T '<== LANG (1:6) AFTER READ'
  LANG(1.1) := '***'
  #OFFSET := 2
  WRITE 5T LANG (1.1) 35T '<== LANG (1.1) AFTER TWO ASSIGNS' /
        5T LANG (#OFFSET.#OFFSET:#OFFSET + 4) 35T '<== LANG (2:6) AFTER TWO ASSIGNS'
  UPDATE
  GET MYVIEW2 *ISN
  WRITE 5T MYVIEW2.LANG (1:6) 35T '<== AFTER UPDATE AND GET' / 5T '-' (55)
  #OFFSET := 1
END-READ
END

```

### Emitted Python Target (`sample.py`):

```python
from target_orm import Employees

class SampleContext:
    def __init__(self):
        self.offset = 1

def execute_sample(ctx: SampleContext, session):
    for loop_idx, record in enumerate(session.query(Employees).filter((Employees.name >= 'SMITH')), 1):
        loop_counter = loop_idx
        print(" " * 4 + str(record.lang[(ctx.offset - 1)][(ctx.offset - 1):(ctx.offset + 5)]) + " " * (34 - len("    " + str(record.lang[(ctx.offset - 1)][(ctx.offset - 1):(ctx.offset + 5)]))) + "<== LANG (1:6) AFTER READ")
        record.lang[0][0] = '***'
        ctx.offset = 2
        print(" " * 4 + str(record.lang[0][0]) + " " * (34 - len("    " + str(record.lang[0][0]))) + "<== LANG (1.1) AFTER TWO ASSIGNS")
        print(" " * 4 + str(record.lang[(ctx.offset - 1)][(ctx.offset - 1):(ctx.offset + 4)]) + " " * (34 - len("    " + str(record.lang[(ctx.offset - 1)][(ctx.offset - 1):(ctx.offset + 4)]))) + "<== LANG (2:6) AFTER TWO ASSIGNS")
        session.flush()  # UPDATE committed for active loop
        myview2_record = session.get(Employees, record.id)
        print(" " * 4 + str(myview2_record.lang[(1 - 1):(1 - 1) + 6]) + " " * (34 - len("    " + str(myview2_record.lang[(1 - 1):(1 - 1) + 6]))) + "<== AFTER UPDATE AND GET")
        print(" " * 4 + "-------------------------------------------------------")
        ctx.offset = 1
    return ctx

```

---

## Core Compiler Capabilities

### 1. Database Access & Adabas Transactions

* **Queries & Cursors:** `FIND` (with compound boolean `WITH` criteria), `READ` (with `BY` descriptor, `STARTING FROM`, and `THRU` bounds).
* **Aggregations & Grouping:** `HISTOGRAM` queries mapped to SQLAlchemy `group_by` and `func.count()`, supporting occurrence tracking via `*NUMBER`.
* **Row-Level Filtering:** Inversion-lowered row predicates via `ACCEPT IF <cond>` and `REJECT IF <cond>`.
* **Superdescriptors:** Automatic decomposition of composite subdescriptors (e.g. `(NAME(1:10), DEPT(1:4))`) into composite SQL column slice filters.
* **Mutations & Life Cycle:** In-loop `UPDATE`, `STORE`, and `DELETE` lowered to transactional ORM calls (`session.flush()`, `session.add()`, `session.delete()`).
* **Active Record Lookups & Holds:** `GET SAME` (`session.refresh(record)`) and `GET <VIEW> *ISN` (`session.get(Entity, record.id)`).
* **Transaction Control:** `END TRANSACTION` (`session.commit()`) and `BACKOUT TRANSACTION` (`session.rollback()`).
* **Control Break Processing:** `AT BREAK (field)` and `BEFORE BREAK PROCESSING` boundary detectors tracking previous iteration state.

### 2. Schema, Arrays & Complex Types

* **Adabas Complex Fields:** Periodic groups (`PE`) and Multiple-value (`MU`) fields compiled into typed SQLAlchemy JSON columns with dynamic default initializers.
* **1D & 2D Array Subscripts:** 1-based subscript translation (`LANG(1.1)`) converted to 0-based Python indexing (`record.lang[0][0]`).
* **Multi-Dimensional Ranges:** Inclusive upper-bound range slicing (`LANG(start:end)`) converted to Python slice bounds (`[start - 1:end]`).
* **Dynamic Slices & Splicing:** Arbitrary runtime slice reads and slice assignments (`#VAR(start:len) := '...'`).
* **Dynamic Arrays:** Variable-dimension arrays `(A/*)`, dynamic memory lifecycle via `EXPAND ARRAY`, `REDUCE ARRAY`, `RESIZE ARRAY`, and occurrence checks via `*OCC(#ARR)`.
* **Memory Redefinition (`REDEFINE`):** Overlaid variables lowered into zero-copy, typed `@property` getters and setters with character-level slice splices.
* **Inline Views:** Full scoping of `VIEW OF <DDM>` blocks declared inside `DEFINE DATA`.

### 3. Program Invocation & Modular Architecture

* **By-Reference Parameter Passing:** `CALLNAT` subprogram invocations with isolated callee context instantiation, ordered parameter mapping (`DEFINE DATA PARAMETER`), and mutated lvalue writeback.
* **Program Chaining:** `FETCH` (terminal control transfer with early return) and `FETCH RETURN` (subroutine program chaining).
* **User-Defined Functions:** `DEFINE FUNCTION ... RETURNS (...)` lowered into typed top-level Python utility functions.
* **Internal Subroutines:** `DEFINE SUBROUTINE` blocks invoked via `PERFORM`.
* **Program Termination:** `STOP` and `TERMINATE` mapped to `sys.exit(0)`.

### 4. Arithmetic & Data Operations

* **Arithmetic Engines:** `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE` supporting compound multi-operands (`ADD a b c TO total`), explicit `GIVING` destinations, and `DIVIDE ... REMAINDER` assignments.
* **Precision & Rounding:** Decimal arithmetic quantization using `ROUND_HALF_UP` for `ROUNDED` statements.
* **String Manipulation:** `SEPARATE ... INTO ... WITH DELIMITER`, `COMPRESS ... INTO ... [LEAVING NO SPACE]`, `EXAMINE ... TRANSLATE INTO UPPER/LOWER CASE`, `EXAMINE ... GIVING NUMBER`, `EXAMINE ... REPLACE WITH`, and `MOVE ALL` character fills.
* **Edit Mask Formatting:** Date conversions (`YYYYMMDD` <-> ISO), extended financial formatting (`(EM=$ZZZ,ZZ9.99CR)`, `(EM=ZZZ,ZZ9.99DB)`, `(EM=ZZZ,ZZ9.99-)`, `(EM=ZZZ,ZZ9.99+)`), and robust string-to-numeric unmasking.
* **Memory Reset:** `RESET` restoring variables to typed default states (`""`, `0`, `Decimal('0')`, `False`).

### 5. Formatted I/O & Scoped Error Handling

* **Tabulation & Continuation:** `WRITE` and `PRINT` formatting supporting absolute column tab stops (`5T`, `35T`), line splits (`/`), string repetitions (`'-' (55)`), and runtime column width calculations.
* **Error Scopes (`ON ERROR`):** Global module-level and localized subroutine-level `ON ERROR ... END-ERROR` recovery blocks lowered to localized `try: ... except Exception:` handlers.

---

## Quickstart with `./build.sh`

The `./build.sh` script automates virtual environment management, dependency resolution, CLI linking, workspace building, and testing.

### Setup & Installation

Initializes the isolated Python virtual environment, installs dependencies in editable mode, and links the global `natural` CLI binary to `~/.local/bin/natural`.

```bash
./build.sh install
# or
./build.sh build

```

### Running Tests & Verification

Execute the complete regression test suite:

```bash
./build.sh test

```

Target specific fixtures by substring or pattern:

```bash
# Run single test
./build.sh test calendar_sample

# Run multiple specific tests
./build.sh test redefine at_break histogram

# Enable verbose logging (emits IR passes, emitted Python code, and execution steps)
./build.sh test calendar_sample -v

```

### Auto-Blessing Changes (`bless`)

When updating emitter logic or lowering rules, automatically re-bless fixture expectations instead of manually updating Python snapshots:

```bash
# Bless all fixtures whose generated code changed
./build.sh bless

# Bless only specific fixtures
./build.sh bless calendar_sample numeric_edit_mask

```

### Running Compiled Modules

Execute standalone programs through the driver without manually activating virtual environments:

```bash
# Build workspace with Git-style diff output
./build.sh run build workspaces/calendar-end-of-month --diff

# Execute compiled module directly
./build.sh run workspaces/calendar-end-of-month sample

# Pass CLI arguments to generated contexts
./build.sh run workspaces/freight-calc ratecalc --ship-class AIR --ship-weight 150.00

```

### Clean Environment

Deletes virtual environments, bytecode caches, build outputs, and the global symlink:

```bash
./build.sh clean

```

---

## Test Harness & Snapshot Architecture

Tests are self-contained `.test` files in `tests/fixtures/`. The test engine (`tests/test_fixtures.py`) dynamically creates isolated workspace environments, executes the compiler, validates generated code against snapshots, and executes the compiled classes in-memory against a mock SQLAlchemy database engine.

Fixtures support both single-module definitions and multi-file project workspaces:

```text
=== NATURAL: EMPLOYEES.ddm ===
1 AC NAME                                 A   20  N N
1 AB LANG                                 A    3  N (1:7)

=== NATURAL: SAMPLE.nsp ===
DEFINE DATA LOCAL
01 #OFFSET (I2) INIT<1>
...
END-DEFINE
...

=== PYTHON: sample.py ===
from target_orm import Employees
...

=== EXECUTE ===
- input:
    offset: 1
  records:
    - id: 1
      name: "SMITH"
      lang:
        - ["EN", "FR", "DE", "ES", "IT", "NL", "PT"]
  expected:
    offset: 1

```

---

## Compiler Architecture

```
                  ┌───────────────────────────────┐
                  │     Natural Source Code       │
                  │  (.nsp, .nsn, .nsa, .ddm)     │
                  └──────────────┬────────────────┘
                                 │
                 Preprocessor (Includes & Stripping)
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │    Pass 1: Island Parser      │
                  │     (pass1_island.lark)       │
                  └──────────────┬────────────────┘
                                 │ Block Boundaries & Clauses
                                 ▼
                  ┌───────────────────────────────┐
                  │ Pass 2: Statement Dispatcher  │
                  │    (pass2_dispatcher.py)      │
                  └──────────────┬────────────────┘
                                 │ Syntactic AST (IR0)
                                 ▼
                  ┌───────────────────────────────┐
                  │   Pass 3: Semantic Lowering   │
                  │         (lowering.py)         │
                  └──────────────┬────────────────┘
                                 │ Semantic DAG & Symbols (IR1)
                                 ▼
                  ┌───────────────────────────────┐
                  │     Pass 4: Code Emitters     │
                  │  python_emitter / orm_emitter │
                  └──────────────┬────────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       ┌───────────────────┐           ┌───────────────────┐
       │   Typed Python    │           │  SQLAlchemy ORM   │
       │  Business Logic   │           │   Target Models   │
       └───────────────────┘           └───────────────────┘

```

1. **Pass 1: Island Grammar (`pass1_island.lark`):** Isolates high-level language blocks (`FIND`, `READ`, `HISTOGRAM`, `IF`, `REPEAT`, `FOR`, `DECIDE`, `DEFINE DATA`, `DEFINE SUBROUTINE`, `DEFINE FUNCTION`, `ON ERROR`, `AT BREAK`, `AT START/END`) from statement payloads.
2. **Pass 2: Specialized Statement Dispatcher (`pass2_dispatcher.py`):** Routes block statements and clauses to specialized micro-parsers (`AssignParser`, `MathParser`, `StringOpParser`, `DatabaseOpParser`, `IOParser`, `WorkFileParser`, `DecideParser`, etc.) to produce the Syntactic AST (IR0).
3. **Pass 3: Semantic Lowering Pass (`lowering.py`):** Resolves symbols, parameters, and inline view definitions against external DDMs/NSAs. Transforms query blocks into unified `QueryIterationOp` structures, manages loop stacks and exit labels, handles composite superdescriptor slicing, lowers `GET` lookups, and decomposes arithmetic/array bounds.
4. **Pass 4: Target Emitters (`python_emitter.py`, `orm_emitter.py`):**
* `ORMEmitter`: Generates SQLAlchemy declarative models from DDM definitions, mapping `PE`/`MU` fields to JSON types.
* `PythonEmitter`: Performs dependency and type harvesting, generating typed Context data models, isolated subroutine/function blocks, query loops, runtime tabulation alignment, and standalone executable runner blocks.


5. **Project Builder (`builder.py`):** Discovers all module dependencies, constructs a topological DAG via `graphlib.TopologicalSorter`, and coordinates compilations across multi-module workspaces.

---

## Project Structure

```text
.
├── build.sh                                # Automated build, test, bless, and run driver
├── pyproject.toml                          # Project metadata and dependencies
├── src/
│   └── natural/
│       ├── cli.py                          # Typer CLI driver and file diffing
│       ├── codegen/
│       │   ├── orm_emitter.py              # DDM view to SQLAlchemy model generator
│       │   └── python_emitter.py           # IR1 to typed Python code generator
│       ├── grammar/
│       │   └── pass1_island.lark           # Lark island grammar for structural blocks
│       ├── ir/
│       │   ├── models.py                   # IR0 Syntactic AST definitions
│       │   ├── pass1_models.py             # Pass 1 structural block models
│       │   ├── semantic.py                 # IR1 Semantic DAG & symbol table models
│       │   └── serializer.py               # Clean YAML serializer with empty-node pruning
│       ├── normalizer/
│       │   ├── lowering.py                 # Semantic Lowering Pass (IR0 -> IR1)
│       │   ├── pass1_parser.py             # Island grammar parser and transformer
│       │   ├── pass2_dispatcher.py         # Specialized statement dispatcher
│       │   ├── preprocessor.py             # Include expander and comment stripper
│       │   ├── workspace.py                # DDM, NSA, and copycode dependency resolver
│       │   └── parsers/                    # Specialized statement micro-parsers
│       │       ├── assign_parser.py
│       │       ├── callnat_parser.py
│       │       ├── data_parser.py
│       │       ├── database_parser.py
│       │       ├── decide_parser.py
│       │       ├── escape_parser.py
│       │       ├── expression_parser.py
│       │       ├── find_parser.py
│       │       ├── for_parser.py
│       │       ├── if_parser.py
│       │       ├── io_parser.py
│       │       ├── loop_parser.py
│       │       ├── math_parser.py
│       │       ├── move_parser.py
│       │       ├── read_parser.py
│       │       ├── string_parser.py
│       │       └── workfile_parser.py
│       └── orchestrator/
│           └── builder.py                  # Topological DAG workspace builder
└── tests/
    ├── conftest.py                         # Pytest configuration (--bless, --verbose-test)
    ├── test_fixtures.py                    # Golden-master test engine
    └── fixtures/                           # 39 End-to-end integration test suites
        ├── accept_reject.test              # Row filtering via ACCEPT / REJECT
        ├── adabas_periodic_group.test      # DDM PE/MU periodic group indexing
        ├── array_lifecycle.test            # EXPAND / REDUCE / RESIZE ARRAY & *OCC
        ├── at_break.test                   # AT BREAK & BEFORE BREAK PROCESSING
        ├── calendar_sample.test            # Multi-view, 2D array ranges, GET *ISN
        ├── callnat_by_ref.test             # Positional by-reference argument mutation
        ├── callnat_multi.test              # Multi-program CALLNAT invocation
        ├── compound_math_rounded.test      # Multi-operand math and ROUNDED
        ├── compress.test                   # Delimited string joining
        ├── compress_leaving_no_space.test  # COMPRESS LEAVING NO SPACE
        ├── decide_for.test                 # Multi-condition DECIDE FOR branching
        ├── decide_on.test                  # Value-based switch branching
        ├── dynamic_substring.test          # Variable-bound substring assignment
        ├── examine.test                    # Pattern counting & substring replacement
        ├── examine_translate.test          # TRANSLATE INTO UPPER / LOWER CASE
        ├── exponentiation.test             # Power (**) and modulo (%) operators
        ├── fetch_control.test              # Program flow transfer via FETCH [RETURN]
        ├── find_compound.test              # Multi-field boolean WITH criteria
        ├── for_loop.test                   # Stepped numerical FOR loops
        ├── histogram.test                  # Aggregations, GROUP BY, and *NUMBER
        ├── if_nested.test                  # Compound logical condition branching
        ├── io_tabulation.test              # WRITE/PRINT with tab stops and split lines
        ├── math_ops.test                   # Arithmetic precision and subtraction
        ├── move_all_and_substring.test     # Character repetition & substring writes
        ├── move_by_name.test               # MOVE BY NAME structure assignment
        ├── move_edited.test                # Date edit mask parsing and formatting
        ├── move_unmask_decimal.test        # Accounting sign & currency unmasking
        ├── numeric_edit_mask.test          # Basic numeric edit masks
        ├── numeric_edit_mask_extended.test # CR/DB/trailing sign and currency edit masks
        ├── on_error.test                   # Module-level ON ERROR exception recovery
        ├── on_error_subroutine.test        # Localized subroutine ON ERROR isolation
        ├── redefine.test                   # Memory redefinition getter/setter properties
        ├── repeat_loop.test                # Post-test REPEAT ... UNTIL loops
        ├── reset.test                      # Type-specific variable default resetting
        ├── separate.test                   # String splitting into variable lists
        ├── subroutine.test                 # Internal subroutine PERFORM blocks
        ├── superdescriptor.test            # Composite descriptor slice decomposition
        ├── transaction.test                # END and BACKOUT TRANSACTION
        └── user_function.test              # DEFINE FUNCTION typed methods

```


---

# Chat - https://share.gemini.google/VvnggbCkY7UC - Semantic Lowering Modular Architecture Refactor

Refactored the monolithic `lowering.py` (~780 lines) into a decoupled, domain-driven package (`src/natural/normalizer/lowering/`) with isolated context management, dedicated expression lowering, and registry-based statement dispatch.

---

### Summary of Changes

- **State & Scope Encapsulation (`lowering/context.py`)**:
    - Extracted `LoweringContext` and `ActiveLoopContext` out of the lowering traversal logic.
    - Centralized symbol table construction, format parsing (`parse_format`), loop stack state, function symbol scopes, DDM/view definition lookups, and scoped field resolution (`get_fields_for_scope`, `resolve_ref`, `resolve_target_loop`).

- **Dedicated Expression Engine (`lowering/expressions.py`)**:
    - Isolated `ExpressionLowerer` to convert AST expressions to Semantic DAG expressions.
    - Handles system variables (`*OCC`, `*COUNTER`, `*ISN`, `*NUMBER`, `*DATX`, `*TIME`), array indexing, dynamic slicing, function invocations, and automatic decomposition of DDM superdescriptors into boolean slice conjunctions.

- **Domain-Specific Statement Handlers (`lowering/handlers/`)**:
    - Replaced the large conditional `if isinstance(stmt, ...)` ladder with a registry-based dispatch table (`DEFAULT_HANDLERS`) mapping statement AST classes directly to specialized handler functions:
        - **`handlers/memory.py`**: `ASSIGN`, `MOVE`, `MOVE BY NAME`, `COMPRESS`, `SEPARATE`, `EXAMINE`, `RESET`, `RESIZE ARRAY`.
        - **`handlers/database.py`**: `FIND`, `READ`, `HISTOGRAM`, `GET`, `GET SAME`, `UPDATE`, `DELETE`, `STORE`, `ACCEPT`, `REJECT`, `END TRANSACTION`, `BACKOUT TRANSACTION`, `AT START OF DATA`, `AT END OF DATA`, and `AT BREAK`.
        - **`handlers/control_flow.py`**: `IF`, `DECIDE ON/FOR`, `REPEAT`, `FOR`, `ESCAPE`, `STOP`, `TERMINATE`, and `ON ERROR`.
        - **`handlers/invocation.py`**: `PERFORM`, `CALLNAT`, and `FETCH` (including by-reference caller-callee bindings).
        - **`handlers/io.py`**: `WRITE`, `PRINT`, `READ WORK FILE`, `WRITE WORK FILE`, and `CLOSE WORK FILE`.

- **Orchestration & Public API Compatibility (`lowering/engine.py`, `lowering/__init__.py`)**:
    - Implemented `SemanticLoweringPass` in `engine.py` to drive the compilation pipeline, coordinate symbol building, lower subroutines/functions, and dispatch statements via the handler registry.
    - Re-exported `SemanticLoweringPass`, `LoweringContext`, `ActiveLoopContext`, and `ExpressionLowerer` from `natural.normalizer.lowering`, ensuring zero breaking changes for `cli.py`, `builder.py`, and test harnesses.
