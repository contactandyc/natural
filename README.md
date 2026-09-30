# Natural-to-Semantic-IR Compiler Framework

This is based on a many [chats with gemini](CHATS.md).

---

A deterministic compilation and code-generation framework designed to migrate legacy Software AG Natural applications into typed modern programming languages (Python/SQLAlchemy, TypeScript/Node, and future targets).

Instead of relying on fragile regex replacements or heuristic text rewriting, this compiler follows an LLVM-style architecture: it parses Natural source code into a syntactic Abstract Syntax Tree (IR0), lowers it into a target-agnostic Semantic Intermediate Representation (IR1), and emits idiomatic, typed business logic and schema definitions through pluggable language backends paired with self-contained target runtime libraries.

It includes a topological DAG workspace builder, a multi-target backend protocol, a comprehensive 41-suite golden-master test framework, and a dual-track testing engine supporting semantic behavioral evaluation (`evaluate`) alongside syntactic snapshot blessing (`bless`).

---

## Translation Example

### Legacy Natural Input (`BONUSCALC.nsp`):

```natural
DEFINE DATA LOCAL
01 EMPLOYEES VIEW OF EMPLOYEES
  02 NAME
  02 DEPT
  02 SALARY
  02 BONUS
01 #BONUS-RATE (P3.2) INIT <0.10>
01 #MIN-SALARY (P7.2) INIT <50000.00>
END-DEFINE

READ (5) EMPLOYEES BY NAME STARTING FROM 'A'
  REJECT IF SALARY < #MIN-SALARY
  IF DEPT = 'SALES'
    #BONUS-RATE := 0.15
  ELSE
    #BONUS-RATE := 0.10
  END-IF
  BONUS := SALARY * #BONUS-RATE
  WRITE 5T NAME 25T DEPT 35T SALARY 45T BONUS
  UPDATE
END-READ
END TRANSACTION
END

```

### Emitted Python Target (`bonuscalc.py`):

```python
from decimal import Decimal
from natural_runtime import tab, tabulate
from target_orm import Employees

class BonuscalcContext:
    def __init__(self):
        self.bonus_rate = Decimal('0.10')
        self.min_salary = Decimal('50000.00')

def execute_bonuscalc(ctx: BonuscalcContext, session):
    for loop_idx, record in enumerate(session.query(Employees).filter((Employees.name >= 'A')).limit(5), 1):
        loop_counter = loop_idx
        if (record.salary < ctx.min_salary):
            continue
        if (record.dept == 'SALES'):
            ctx.bonus_rate = Decimal('0.15')
        else:
            ctx.bonus_rate = Decimal('0.10')
        record.bonus = (record.salary * ctx.bonus_rate)
        print(tabulate(tab(5), record.name, tab(25), record.dept, tab(35), record.salary, tab(45), record.bonus))
        session.flush()  # UPDATE committed for active loop
    session.commit()
    return ctx

```

---

## Compiler Architecture

The compiler strictly decouples source language frontend parsing, intermediate semantic normalization, target code generation, and target runtime execution:

```
                  ┌─────────────────────────────────────────┐
                  │           Natural Source Code           │
                  │        (.nsp, .nsn, .nsa, .ddm)         │
                  └────────────────────┬────────────────────┘
                                       │
                       Preprocessor (Includes & Comments)
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │          Pass 1: Island Parser          │
                  │           (pass1_island.lark)           │
                  └────────────────────┬────────────────────┘
                                       │ Block Boundaries & Raw Clauses
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │       Pass 2: Statement Dispatcher      │
                  │          (pass2_dispatcher.py)          │
                  └────────────────────┬────────────────────┘
                                       │ Syntactic AST (IR0)
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │        Pass 3: Semantic Lowering        │
                  │   (lowering/ context, exprs, handlers)  │
                  └────────────────────┬────────────────────┘
                                       │ Target-Agnostic Semantic DAG (IR1)
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │         Pass 4: Target Backend          │
                  │         (codegen/target.py API)         │
                  └──────────┬───────────────────┬──────────┘
                             │                   │
               ┌─────────────┴─────┐       ┌─────┴─────────────┐
               ▼                   ▼       ▼                   ▼
       ┌───────────────┐   ┌───────────┐ ┌───────────────┐   ┌───────────┐
       │ Python Target │   │  Runtime  │ │  TypeScript   │   │  Runtime  │
       │ (Logic + ORM) │   │ (Package) │ │ Target (Plan) │   │ (Package) │
       └───────────────┘   └───────────┘ └───────────────┘   └───────────┘

```

1. **Pass 1: Island Grammar (`pass1_island.lark`):** Isolates high-level language blocks (`FIND`, `READ`, `HISTOGRAM`, `IF`, `REPEAT`, `FOR`, `DECIDE`, `DEFINE DATA`, `DEFINE SUBROUTINE`, `DEFINE FUNCTION`, `ON ERROR`, `AT BREAK`, `AT START/END`) from statement payloads.
2. **Pass 2: Specialized Statement Dispatcher (`pass2_dispatcher.py`):** Routes block statements and clauses to specialized micro-parsers (`assign_parser`, `math_parser`, `string_parser`, `database_parser`, `io_parser`, `workfile_parser`, `decide_parser`, etc.) to produce the Syntactic AST (IR0).
3. **Pass 3: Semantic Lowering (`lowering/`):** Resolves symbols, parameters, and inline view definitions against external DDMs/NSAs. Uses an isolated `ExpressionLowerer` and registry-based statement handlers (`handlers/database`, `handlers/memory`, `handlers/control_flow`, `handlers/invocation`, `handlers/io`) to emit a pure, target-agnostic Semantic DAG (IR1).
4. **Pass 4: Pluggable Target Backends (`codegen/target.py`):** A unified `TargetBackend` protocol routes IR1 modules to language-specific emitters (`targets/python`, `targets/typescript`, etc.).
5. **Target Runtime Libraries (`targets/<lang>/runtime/`):** Self-contained support libraries emitted directly into workspace builds (`build/<target>/natural_runtime/`) that absorb complex mainframe semantics (accounting edit masks, sign unmasking, substring splices, column tab alignment, dynamic array resizing) without polluting emitted business logic.
6. **Project Builder (`orchestrator/builder.py`):** Discovers all module dependencies, constructs a topological DAG via `graphlib.TopologicalSorter`, coordinates multi-module compilation for selected targets, and manages clean build artifacts.

---

## Multi-Target Backend Architecture

### Design Principles

1. **Target-Agnostic IR1:** The semantic intermediate representation contains zero language-specific keywords, library names, or syntax strings (e.g. system variables resolve to abstract semantic tokens like `op="sys_date"`, `op="counter"`, or `op="array_length"`).
2. **Target Backend Contract:** Every backend implements `TargetBackend`:
* `emit_module(module, emit_main)`: Emits executable business logic.
* `emit_schema(ddms)`: Emits data models / ORM entities from DDM definitions.
* `emit_runtime()`: Emits the target's self-contained support runtime.


3. **Shared Codegen Infrastructure:** Shared utilities in `codegen/common/` (`CodeWriter`, Python/JS keyword escaping, PascalCase/snake_case helpers) eliminate boilerplate across emitters.

### Target Support Matrix

| Target Language | Status | Data Layer | Runtime Library | Execution Model |
| --- | --- | --- | --- | --- |
| **Python** | **Complete (Default)** | SQLAlchemy Declarative Base | `natural_runtime/` (unmask, tabulation, slicing, arrays) | In-memory via `MockSession` or standalone CLI (`--emit-main`) |
| **TypeScript** | *Under Development* | Prisma / Drizzle / Interface Schemas | `natural_runtime/` (`.ts` utilities via `Decimal.js`) | Node/TSX execution runner |
| **Go / Java / C#** | *Architecture-Ready* | Native SQL / GORM / EF Core | Target Runtime Package | Native compiled binaries / classes |

---

## Core Compiler Capabilities

### 1. Database Access & Adabas Transactions

* **Queries & Cursors:** `FIND` (with compound boolean `WITH` criteria), `READ` (with `BY` descriptor, `STARTING FROM`, and `THRU` bounds).
* **Aggregations & Grouping:** `HISTOGRAM` queries mapped to aggregate grouping and count functions, supporting occurrence tracking via `*NUMBER`.
* **Row-Level Filtering:** Inversion-lowered row predicates via `ACCEPT IF <cond>` and `REJECT IF <cond>`.
* **Superdescriptors:** Automatic decomposition of composite subdescriptors (e.g. `(NAME(1:10), DEPT(1:4))`) into composite SQL column slice filters.
* **Mutations & Lifecycle:** In-loop `UPDATE`, `STORE`, and `DELETE` lowered to transactional ORM calls (`session.flush()`, `session.add()`, `session.delete()`).
* **Active Record Lookups & Holds:** `GET SAME` (`session.refresh(record)`) and `GET <VIEW> *ISN` (`session.get(Entity, record.id)`).
* **Transaction Control:** `END TRANSACTION` (`session.commit()`) and `BACKOUT TRANSACTION` (`session.rollback()`).
* **Control Break Processing:** `AT BREAK (field)` and `BEFORE BREAK PROCESSING` boundary detectors tracking previous iteration state.

### 2. Schema, Arrays & Complex Types

* **Adabas Complex Fields:** Periodic groups (`PE`) and Multiple-value (`MU`) fields compiled into typed JSON columns with dynamic default initializers.
* **1D & 2D Array Subscripts:** 1-based subscript translation (`LANG(1.1)`) converted to 0-based indexing (`record.lang[0][0]`).
* **Multi-Dimensional Ranges:** Inclusive upper-bound range slicing (`LANG(start:end)`) converted to index slice bounds (`[start - 1:end]`).
* **Dynamic Slices & Splicing:** Arbitrary runtime slice reads and slice assignments via `slice_assign(...)`.
* **Dynamic Arrays:** Variable-dimension arrays `(A/*)`, dynamic memory lifecycle via `expand_array`, `reduce_array`, `resize_array`, and occurrence checks via `*OCC(#ARR)`.
* **Memory Redefinition (`REDEFINE`):** Overlaid variables lowered into zero-copy, typed `@property` getters and setters with character-level slice splices.
* **Inline Views:** Full scoping of `VIEW OF <DDM>` blocks declared inside `DEFINE DATA`.

### 3. Program Invocation & Modular Architecture

* **By-Reference Parameter Passing:** `CALLNAT` subprogram invocations with isolated callee context instantiation, ordered parameter mapping (`DEFINE DATA PARAMETER`), and mutated lvalue writeback.
* **Program Chaining:** `FETCH` (terminal control transfer with early return) and `FETCH RETURN` (subroutine program chaining).
* **User-Defined Functions:** `DEFINE FUNCTION ... RETURNS (...)` lowered into typed top-level utility functions.
* **Internal Subroutines:** `DEFINE SUBROUTINE` blocks invoked via `PERFORM`.
* **Program Termination:** `STOP` and `TERMINATE` mapped to `sys.exit(0)`.

### 4. Arithmetic & Data Operations

* **Arithmetic Engines:** `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE` supporting compound multi-operands (`ADD a b c TO total`), explicit `GIVING` destinations, and `DIVIDE ... REMAINDER` assignments.
* **Precision & Rounding:** Decimal arithmetic quantization using `ROUND_HALF_UP` for `ROUNDED` statements.
* **String Manipulation:** `SEPARATE ... INTO ... WITH DELIMITER`, `COMPRESS ... INTO ... [LEAVING NO SPACE]`, `EXAMINE ... TRANSLATE INTO UPPER/LOWER CASE`, `EXAMINE ... GIVING NUMBER`, `EXAMINE ... REPLACE WITH`, and `MOVE ALL` character fills.
* **Edit Mask Formatting & Unmasking:** Date conversions (`YYYYMMDD` $\leftrightarrow$ ISO), extended financial formatting (`(EM=$ZZZ,ZZ9.99CR)`, `(EM=ZZZ,ZZ9.99DB)`, `(EM=ZZZ,ZZ9.99-)`, `(EM=ZZZ,ZZ9.99+)`), and accounting sign/currency unmasking via `unmask_decimal` and `unmask_integer`.
* **Memory Reset:** `RESET` restoring variables to typed default states (`""`, `0`, `Decimal('0')`, `False`).

### 5. Formatted I/O & Scoped Error Handling

* **Tabulation & Continuation:** `WRITE` and `PRINT` formatting supporting absolute column tab stops (`5T`, `35T`), line splits (`/`), string repetitions (`'-' (55)`), and runtime column width tabulation via `tabulate(tab(col), ...)`.
* **Error Scopes (`ON ERROR`):** Global module-level and localized subroutine-level `ON ERROR ... END-ERROR` recovery blocks lowered to localized `try: ... except Exception:` handlers.

---

## Quickstart with `./build.sh`

The `./build.sh` script automates virtual environment management, dependency resolution, CLI linking, workspace building, testing, evaluation, and snapshot blessing.

### Setup & Installation

Initializes the isolated Python virtual environment, installs dependencies in editable mode, and links the global `natural` CLI binary to `~/.local/bin/natural`.

```bash
./build.sh install
# or
./build.sh build

```

### Running Tests & Verification

Execute the complete regression test suite (asserts character-for-character snapshot matching and executes test cases):

```bash
./build.sh test

```

Target specific fixtures by substring or pattern:

```bash
# Run single test
./build.sh test calendar_sample

# Run multiple specific tests
./build.sh test redefine at_break histogram

# Enable verbose logging (emits IR passes, emitted code, and execution steps)
./build.sh test calendar_sample -v

```

### Evaluating Semantic Parity (`evaluate`)

When refactoring emitter logic or runtime libraries, verify functional behavior against `=== EXECUTE ===` test cases without failing on syntactic snapshot diffs:

```bash
# Evaluate all fixtures for functional correctness
./build.sh evaluate

# Evaluate specific fixtures
./build.sh evaluate bonuscalc io_tabulation

```

### Auto-Blessing Snapshots (`bless`)

Once `./build.sh evaluate` confirms behavioral correctness, automatically update fixture golden-master snapshots with the new emitted output:

```bash
# Bless all fixtures whose generated code changed
./build.sh bless

# Bless only specific fixtures
./build.sh bless calendar_sample numeric_edit_mask

```

### Building & Running Compiled Workspaces

Execute standalone programs through the driver or compile workspaces with targeted languages:

```bash
# Build workspace targeting Python (default) with Git-style diffs
./build.sh run build workspaces/calendar-end-of-month --diff

# Build workspace targeting another language (e.g. typescript)
natural build workspaces/freight-calc --target=typescript

# Execute compiled module directly via driver
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

Tests are self-contained `.test` files in `tests/fixtures/`. The test engine (`tests/test_fixtures.py`) dynamically creates isolated workspace environments, executes the compiler, validates generated code against snapshots, reflects SQLAlchemy schema types to coerce test record inputs, and executes the compiled classes in-memory against a mock database engine.

Fixtures support multi-module workspaces, multiple emitted target languages, and functional execution assertions:

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
from natural_runtime import tab, tabulate
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

## Project Structure

```text
.
├── build.sh                                # Build, test, evaluate, bless, and run driver
├── pyproject.toml                          # Project metadata and dependencies
├── src/
│   └── natural/
│       ├── cli.py                          # Typer CLI driver (parse, build, run)
│       ├── codegen/
│       │   ├── common/                     # Shared target-agnostic codegen utilities
│       │   │   ├── writer.py               # CodeWriter (scoped indentation buffer)
│       │   │   └── naming.py               # Keyword sanitization, PascalCase, snake_case
│       │   ├── target.py                   # TargetBackend abstract protocol & registry
│       │   └── targets/                    # Pluggable language backends
│       │       ├── python/                 # Python/SQLAlchemy backend
│       │       │   ├── target.py           # PythonTarget registration
│       │       │   ├── engine.py           # Module code generation orchestrator
│       │       │   ├── context.py          # EmitterContext & symbol resolution
│       │       │   ├── expressions.py      # PythonExpressionEmitter
│       │       │   ├── harvester.py        # Import and dependency scanner
│       │       │   ├── formatters.py       # Edit mask formatting engines
│       │       │   ├── orm.py              # SQLAlchemy model emitter & fallback base
│       │       │   ├── handlers/           # IR1 statement handlers
│       │       │   │   ├── memory.py       # ASSIGN, COMPRESS, EXAMINE, RESET, RESIZE
│       │       │   │   ├── database.py     # Queries, cursors, CRUD, transactions
│       │       │   │   ├── control_flow.py # IF, DECIDE, loops, branches, ON ERROR
│       │       │   │   ├── invocation.py   # CALLNAT, FETCH, PERFORM
│       │       │   │   └── io.py           # WRITE, PRINT, work files
│       │       │   └── runtime/            # Self-contained Python runtime library
│       │       │       ├── __init__.py     # Public runtime exports
│       │       │       ├── unmask.py       # unmask_decimal, unmask_integer
│       │       │       ├── tabulation.py   # tab, tabulate
│       │       │       ├── slicing.py      # slice_assign
│       │       │       └── arrays.py       # expand_array, reduce_array, resize_array
│       │       └── typescript/             # TypeScript backend (in development)
│       ├── grammar/
│       │   └── pass1_island.lark           # Lark island grammar for structural blocks
│       ├── ir/
│       │   ├── models.py                   # IR0 Syntactic AST definitions
│       │   ├── pass1_models.py             # Pass 1 structural block models
│       │   ├── semantic.py                 # IR1 Semantic DAG & symbol table models
│       │   └── serializer.py               # Clean YAML serializer with empty-node pruning
│       ├── normalizer/
│       │   ├── lowering/                   # Modular Semantic Lowering Pass (IR0 -> IR1)
│       │   │   ├── context.py              # LoweringContext & ActiveLoopContext
│       │   │   ├── engine.py               # SemanticLoweringPass orchestrator
│       │   │   ├── expressions.py          # Target-agnostic ExpressionLowerer
│       │   │   └── handlers/               # Domain-specific lowering handlers
│       │   ├── pass1_parser.py             # Island grammar parser and transformer
│       │   ├── pass2_dispatcher.py         # Specialized statement dispatcher
│       │   ├── preprocessor.py             # Include expander and comment stripper
│       │   ├── workspace.py                # DDM, NSA, and copycode dependency resolver
│       │   └── parsers/                    # Specialized statement micro-parsers
│       └── orchestrator/
│           └── builder.py                  # Topological DAG workspace builder
└── tests/
    ├── conftest.py                         # Pytest configuration (--bless, --evaluate, --verbose-test)
    ├── test_fixtures.py                    # Golden-master test and evaluation engine
    └── fixtures/                           # 41 End-to-end integration test suites
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
        ├── original_bug_report.test        # Regression coverage for array slice continuations
        ├── readme.test                     # Readme translation example verification
        ├── redefine.test                   # Memory redefinition getter/setter properties
        ├── repeat_loop.test                # Post-test REPEAT ... UNTIL loops
        ├── reset.test                      # Type-specific variable default resetting
        ├── separate.test                   # String splitting into variable lists
        ├── subroutine.test                 # Internal subroutine PERFORM blocks
        ├── superdescriptor.test            # Composite descriptor slice decomposition
        ├── transaction.test                # END and BACKOUT TRANSACTION
        └── user_function.test              # DEFINE FUNCTION typed methods

```
