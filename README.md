# Natural-to-Semantic-IR Compiler Framework

This is based on a many [chats with gemini](CHATS.md).

---

A deterministic compiler and semantic lowering framework designed to migrate legacy Software AG Natural applications into typed modern programming languages (Python/SQLAlchemy, TypeScript/Node, and future targets).

Instead of relying on fragile regex replacements or text transpilation, this compiler follows an LLVM-style multi-pass pipeline: it parses Natural source code into a syntactic Abstract Syntax Tree (IR0) using Context-Free Grammars, lowers it into a strictly typed, target-agnostic Semantic Intermediate Representation (IR1) with bottom-up type synthesis and explicit `CastOp` nodes, and emits idiomatic, typed code and schemas through pluggable language backends paired with self-contained target runtime libraries.

Key features include:
- **Lark-Powered Context-Free Micro-Parsers**: Zero regex in statement parsing; all statement payloads and expressions share unified grammars.
- **Strict Semantic Type Synthesis & Explicit Cast Insertion**: Every IR1 expression node carries its synthesized `SemanticType`, with explicit `CastOp` operations (`WIDEN`, `NARROW`, `UNMASK`, `EDIT_MASK`, `PARSE_DATE`, `FORMAT_DATE`, `STRINGIFY`) decoupling backend emitters from type guesswork.
- **Pluggable Target Backend Architecture**: Standardized `TargetBackend` protocol separating IR1 semantic lowering from target language syntax generation.
- **Modular Target Runtimes (`natural_runtime`)**: Self-contained runtime libraries emitted alongside compiled code to absorb mainframe arithmetic precision, edit masks, dynamic arrays, string slicing, and column tabulation.
- **Topological DAG Workspace Builder**: Resolves cross-module dependencies (`CALLNAT`, `FETCH`, `USING`, copycodes, views) and builds modules in dependency order.
- **Comprehensive Golden-Master Test Framework**: Supports multi-test and multi-module `.test` files, in-memory execution via a chained mock database engine, behavioral evaluation (`evaluate`), and non-destructive snapshot blessing (`bless`).

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

## Compiler Pipeline

The compiler decouples frontend lexical parsing, intermediate semantic lowering, target code generation, and runtime emulation:

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
                  │      Pass 2: Statement Dispatcher       │
                  │         (CFG Lark Micro-Parsers)        │
                  └────────────────────┬────────────────────┘
                                       │ Syntactic AST (IR0)
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │        Pass 3: Semantic Lowering        │
                  │   Type Inference & Explicit CastOps     │
                  └────────────────────┬────────────────────┘
                                       │ Typed Semantic DAG (IR1)
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
       │ (Logic + ORM) │   │ (Package) │ │ Target (Plan) │   │ (Package) │
       └───────────────┘   └───────────┘ └───────────────┘   └───────────┘

```

1. **Pass 1: Island Grammar (`pass1_island.lark`):** Isolates high-level language blocks (`FIND`, `READ`, `HISTOGRAM`, `IF`, `REPEAT`, `FOR`, `DECIDE`, `DEFINE DATA`, `DEFINE SUBROUTINE`, `DEFINE FUNCTION`, `ON ERROR`, `AT BREAK`, `AT START/END`) from statement payloads.
2. **Pass 2: Statement Dispatcher (`pass2_dispatcher.py`):** Parses raw statement clauses using specialized Lark grammars sharing `SHARED_EXPR_GRAMMAR` (eliminating brittle regular expressions) to produce the Syntactic AST (IR0).
3. **Pass 3: Semantic Lowering (`lowering/`):** Resolves symbols, parameters, and inline view definitions against external DDMs/NSAs. Synthesizes `SemanticType` bottom-up on all expressions, normalizes implicit mainframe coercions into explicit `CastOp` nodes (`wrap_cast`), and generates a pure, target-agnostic Semantic DAG (IR1).
4. **Pass 4: Pluggable Target Backends (`codegen/target.py`):** Dispatches IR1 modules to language-specific emitters (`targets/python`, `targets/typescript`, etc.) implementing the `TargetBackend` protocol. Emitters translate explicit `CastOp` nodes directly without guessing types.
5. **Target Runtime Libraries (`targets/<lang>/runtime/`):** Self-contained support libraries emitted directly into workspace builds (`build/<target>/natural_runtime/`) that absorb mainframe-specific behaviors (sign unmasking, financial edit masks, substring splices, column tab alignment, dynamic array resizing) without polluting business logic.
6. **Project Builder (`orchestrator/builder.py`):** Discovers module dependencies, constructs a topological DAG via `graphlib.TopologicalSorter`, coordinates multi-module compilation, and cleans stale build artifacts.

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

### 2. Strict Type Inference & Explicit Coercion (`CastOp`)

* **Synthesized Semantic Types:** Every IR1 expression node computes and retains its inferred `SemanticType` (base type, precision, scale, length).
* **Explicit `CastOp` Insertion:** Implicit Natural type coercions are converted during lowering into explicit `CastOp` nodes carrying a designated `CastKind`:
* `WIDEN`: Lossless integer-to-decimal promotion (`Decimal(val)`).
* `NARROW`: Decimal/division-to-integer truncation (`int(val)`).
* `UNMASK`: Alphanumeric-to-numeric extraction parsing currency symbols, commas, trailing signs, `CR`/`DB` suffixes, and accounting parentheses.
* `EDIT_MASK`: Formatting numeric expressions into structured strings with padding, thousands commas, and sign indicators.
* `PARSE_DATE` / `FORMAT_DATE`: Bidirectional date transformations (`strptime`/`strftime`) driven by edit masks (`(EM=YYYYMMDD)`).
* `STRINGIFY`: Primitive-to-string canonical stringification (`str(val)`).
* `BOOL_COERCE`: Logical evaluation into target boolean types.


* **Function Return Coercion:** Return statements in `DEFINE FUNCTION ... RETURNS (...)` automatically wrap evaluated expressions into the declared return type.

### 3. Schema, Arrays & Complex Types

* **Adabas Complex Fields:** Periodic groups (`PE`) and Multiple-value (`MU`) fields compiled into typed JSON columns with dynamic default initializers.
* **1D & 2D Array Subscripts:** 1-based subscript translation (`LANG(1.1)`) converted to 0-based indexing (`record.lang[0][0]`).
* **Multi-Dimensional Ranges:** Inclusive upper-bound range slicing (`LANG(start:end)`) converted to index slice bounds (`[start - 1:end]`).
* **Dynamic Slices & Splicing:** Arbitrary runtime slice reads and slice assignments via `slice_assign(...)`.
* **Dynamic Arrays:** Variable-dimension arrays `(A/*)`, dynamic memory lifecycle via `expand_array`, `reduce_array`, `resize_array`, and occurrence checks via `*OCC(#ARR)`.
* **Memory Redefinition (`REDEFINE`):** Overlaid variables lowered into zero-copy, typed `@property` getters and setters with character-level slice splices.
* **Inline Views:** Full scoping of `VIEW OF <DDM>` blocks declared inside `DEFINE DATA`.

### 4. Program Invocation & Modular Architecture

* **By-Reference Parameter Passing:** `CALLNAT` subprogram invocations with isolated callee context instantiation, ordered parameter mapping (`DEFINE DATA PARAMETER`), and mutated lvalue writeback.
* **Program Chaining:** `FETCH` (terminal control transfer with early return) and `FETCH RETURN` (subroutine program chaining).
* **User-Defined Functions:** `DEFINE FUNCTION ... RETURNS (...)` lowered into typed top-level utility functions.
* **Internal Subroutines:** `DEFINE SUBROUTINE` blocks invoked via `PERFORM`.
* **Program Termination:** `STOP` and `TERMINATE` mapped to `sys.exit(0)`.

### 5. Arithmetic & Data Operations

* **Arithmetic Engines:** `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE` supporting compound multi-operands (`ADD a b c TO total`), explicit `GIVING` destinations, and `DIVIDE ... REMAINDER` assignments.
* **Precision & Rounding:** Decimal arithmetic quantization using `ROUND_HALF_UP` for `ROUNDED` statements.
* **String Manipulation:** `SEPARATE ... INTO ... WITH DELIMITER`, `COMPRESS ... INTO ... [LEAVING NO SPACE]`, `EXAMINE ... TRANSLATE INTO UPPER/LOWER CASE`, `EXAMINE ... GIVING NUMBER`, `EXAMINE ... REPLACE WITH`, and `MOVE ALL` character fills.
* **Memory Reset:** `RESET` restoring variables to typed default states (`""`, `0`, `Decimal('0')`, `False`).

### 6. Formatted I/O & Scoped Error Handling

* **Tabulation & Continuation:** `WRITE` and `PRINT` formatting supporting absolute column tab stops (`5T`, `35T`), line splits (`/`), string repetitions (`'-' (55)`), and runtime column width tabulation via `tabulate(tab(col), ...)`.
* **Error Scopes (`ON ERROR`):** Global module-level and localized subroutine-level `ON ERROR ... END-ERROR` recovery blocks lowered to localized `try: ... except Exception:` handlers.

---

## Multi-Target Backend Architecture

| Target Language | Status | Data Layer | Runtime Library | Execution Model |
| --- | --- | --- | --- | --- |
| **Python** | **Complete (Default)** | SQLAlchemy Declarative Base | `natural_runtime/` (unmask, tabulation, slicing, arrays) | In-memory via `MockSession` or standalone CLI (`--emit-main`) |
| **TypeScript** | *Under Development* | Prisma / Drizzle / Interface Schemas | `natural_runtime/` (`.ts` utilities via `Decimal.js`) | Node/TSX execution runner |
| **Go / Java / C#** | *Architecture-Ready* | Native SQL / GORM / EF Core | Target Runtime Package | Native compiled binaries / classes |

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

Execute the complete regression test suite:

```bash
./build.sh test

```

Target specific fixtures or sub-tests using pattern matching:

```bash
# Run a specific fixture file
./build.sh test type_coercion_casts

# Run a specific sub-test within a multi-test fixture
./build.sh test type_coercion_casts.widen_and_narrow

# Run multiple fixtures with verbose logging
./build.sh test redefine at_break type_coercion_casts -v

```

### Evaluating Semantic Parity (`evaluate`)

Verify functional runtime execution against `=== EXECUTE ===` test assertions without failing on syntactic code differences:

```bash
# Evaluate all fixtures for functional correctness
./build.sh evaluate

# Evaluate specific fixtures
./build.sh evaluate bonuscalc type_coercion_casts

```

### Auto-Blessing Snapshots (`bless`)

Automatically update fixture golden-master snapshots with updated compiler output once `./build.sh evaluate` confirms behavioral correctness:

```bash
# Bless all fixtures whose generated code changed
./build.sh bless

# Bless only specific fixtures
./build.sh bless calendar_sample numeric_edit_mask

```

### Building & Running Compiled Workspaces

```bash
# Build workspace targeting Python with Git-style diffs
./build.sh run build workspaces/calendar-end-of-month --diff

# Build workspace targeting another language
natural build workspaces/freight-calc --target=typescript

# Execute compiled module directly via driver
./build.sh run workspaces/calendar-end-of-month sample

# Pass CLI arguments to generated contexts
./build.sh run workspaces/freight-calc ratecalc --ship-class AIR --ship-weight 150.00

```

---

## Test Harness & Fixture Architecture

Tests are self-contained `.test` files in `tests/fixtures/`. The test engine (`tests/test_fixtures.py`) dynamically creates isolated workspaces, compiles source modules, validates generated code against snapshots, reflects SQLAlchemy schema types to coerce test record inputs, and executes compiled contexts in-memory against a mock database session.

### Multi-Test Fixtures

Fixtures support grouping multiple distinct test cases inside a single `.test` file using `=== TEST: <name> ===` boundaries:

```text
=== TEST: widen_and_narrow ===
=== NATURAL ===
DEFINE DATA PARAMETER
1 #INT_VAL  (I4)
1 #WIDENED  (P7.2)
END-DEFINE
#WIDENED := #INT_VAL

=== PYTHON ===
from decimal import Decimal

class WidenAndNarrowContext:
    def __init__(self):
        self.int_val = 0
        self.widened = Decimal('0')

def execute_widen_and_narrow(ctx: WidenAndNarrowContext, session):
    ctx.widened = Decimal(ctx.int_val)
    return ctx

=== EXECUTE ===
- input:
    int_val: 50
  expected:
    widened: "50"

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
│       │   ├── common/                     # Target-agnostic code formatting & naming utilities
│       │   │   ├── writer.py               # CodeWriter (scoped indentation buffer)
│       │   │   └── naming.py               # Keyword sanitization, PascalCase, snake_case
│       │   ├── target.py                   # TargetBackend abstract protocol & registry
│       │   └── targets/                    # Pluggable language backends
│       │       ├── python/                 # Python/SQLAlchemy backend
│       │       │   ├── target.py           # PythonTarget registration
│       │       │   ├── engine.py           # Module code generation orchestrator
│       │       │   ├── context.py          # EmitterContext & symbol resolution
│       │       │   ├── expressions.py      # PythonExpressionEmitter (emits exprs & CastOps)
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
│       │   ├── semantic.py                 # IR1 Semantic DAG, CastKind, Symbol & Type models
│       │   └── serializer.py               # Clean YAML serializer with empty-node pruning
│       ├── normalizer/
│       │   ├── lowering/                   # Modular Semantic Lowering Pass (IR0 -> IR1)
│       │   │   ├── context.py              # LoweringContext & ActiveLoopContext
│       │   │   ├── engine.py               # SemanticLoweringPass orchestrator
│       │   │   ├── expressions.py          # Bottom-up ExpressionLowerer & type synthesizers
│       │   │   └── handlers/               # Domain-specific lowering handlers (coerce_type)
│       │   ├── pass1_parser.py             # Island grammar parser and transformer
│       │   ├── pass2_dispatcher.py         # Pass 2 statement dispatcher
│       │   ├── preprocessor.py             # Include expander and comment stripper
│       │   ├── workspace.py                # DDM, NSA, and copycode dependency resolver
│       │   └── parsers/                    # CFG statement micro-parsers (Lark-based)
│       └── orchestrator/
│           └── builder.py                  # Topological DAG workspace builder
└── tests/
    ├── conftest.py                         # Pytest configuration (--bless, --evaluate, --verbose-test)
    ├── test_fixtures.py                    # Multi-test golden-master test and evaluation engine
    └── fixtures/                           # 42 End-to-end integration test suites
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
        ├── type_coercion_casts.test        # Multi-test: widen/narrow, unmask, stringify, edit masks
        └── user_function.test              # DEFINE FUNCTION typed methods

```
