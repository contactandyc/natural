# Natural-to-Semantic-IR Compiler Framework

This is based on a chat with Gemini - https://share.gemini.google/YGNCpgsHdbme
as well as additional chats listed at the bottom.

---

A deterministic compilation framework designed to migrate legacy Software AG Natural business logic into modern, typed Python and SQLAlchemy architectures.

Instead of relying on fragile regex matching, this compiler parses Natural source code into a structured Abstract Syntax Tree (IR0), lowers it into a canonical Semantic Intermediate Representation (IR1), and emits idiomatic, typed Python code. It includes an automated test framework featuring snapshot regression checking, in-memory execution assertions, and an auto-blessing workflow.

---

## Translation Example

**Legacy Natural Input (`RATECALC.nsp`):**
```natural
/* Freight Calculation Sample
DEFINE DATA
PARAMETER USING TARIFF-P
LOCAL
  1 #BASE-CHARGE (P9.2)
  1 #SURCHARGE (P7.2)
END-DEFINE

FIND (1) TARIFF-VIEW WITH CLASS = #SHIP-CLASS
  #BASE-CHARGE := RATE * #SHIP-WEIGHT
  IF #SHIP-WEIGHT > WEIGHT-LIMIT
    #SURCHARGE := HEAVY-SURCHARGE
    ESCAPE BOTTOM
  END-IF
END-FIND
END

```

**Generated Python Output (`ratecalc.py`):**

```python
from decimal import Decimal
from target_orm import Tariff

class RatecalcContext:
    def __init__(self):
        self.ship_class = ""
        self.route_zone = ""
        self.ship_weight = Decimal('0')
        self.final_charge = Decimal('0')
        self.base_charge = Decimal('0')
        self.surcharge = Decimal('0')

def execute_ratecalc(ctx: RatecalcContext, session):
    for loop_idx, record in enumerate(session.query(Tariff).filter((Tariff.class_ == ctx.ship_class)).limit(1), 1):
        loop_counter = loop_idx
        ctx.base_charge = (record.rate * ctx.ship_weight)
        if (ctx.ship_weight > record.weight_limit):
            ctx.surcharge = record.heavy_surcharge
            break
    return ctx

```

---

## Quickstart with `./build.sh`

The `./build.sh` script automates virtual environment management, dependency resolution, CLI linking, and test execution. **You do not need to activate or manage a virtual environment manually.**

### Setup & Build

Initializes the isolated Python virtual environment, installs dependencies in editable mode, and symlinks the `natural` CLI binary to `~/.local/bin/natural`.

```bash
./build.sh build
# or
./build.sh install

```

### Running the Compiler

Execute CLI commands through the project environment without manually activating `venv`:

```bash
./build.sh run build path/to/workspace --diff
./build.sh run parse path/to/MODULE.nsp -I path/to/workspace --emit-python

```

### Clean Environment

Removes the `venv/` directory, build caches, packaging artifacts, and unlinks the global CLI symlink:

```bash
./build.sh clean

```

---

## Test & Snapshot Workflow

The project uses self-contained `.test` fixture files in `tests/fixtures/` that define:

1. `=== NATURAL ===`: Input source code
2. `=== PYTHON ===`: Expected emitted Python source code
3. `=== EXECUTE ===`: Parameterized test cases executed dynamically in-memory against a mock database session

### Running Tests

Execute the entire test suite:

```bash
./build.sh test

```

Target specific fixtures by name or pattern:

```bash
# Run only tests matching 'compress'
./build.sh test compress

# Run multiple specific tests
./build.sh test redefine math_ops

```

Inspect compiler stages (IR0, IR1, generated Python, runtime step logs) in the terminal:

```bash
./build.sh test compress -v

```

### Auto-Blessing Changes (`bless`)

When updating code generation formatting or compiler lowering rules, re-bless fixture expectations automatically instead of manually editing generated Python code.

The `bless` command compiles the Natural source, updates the `=== PYTHON ===` section on disk, and verifies that the `=== EXECUTE ===` business assertions continue to pass:

```bash
# Bless all fixtures whose generated Python changed
./build.sh bless

# Bless only specific fixtures
./build.sh bless redefine math_ops

```

> **Note:** The `=== EXECUTE ===` section is never modified by `--bless`. Test assertions serve as immutable ground truth.

---

## CLI Usage (Direct)

Once installed (or via `~/.local/bin/natural`), you can use the CLI directly:

### Build a Workspace

Parses all Natural source files (`.nsp`, `.nsa`, `.ddm`), resolves cross-module dependencies using a topological DAG, and emits IR0, IR1, and Python targets.

```bash
natural build path/to/workspace

```

Display colorized Git-style diffs before writing to disk:

```bash
natural build path/to/workspace --diff

```

### Inspect Single Modules

```bash
# Inspect the lowered IR1 Semantic YAML
natural parse path/to/RATECALC.nsp -I path/to/workspace

# Inspect emitted Python code
natural parse path/to/RATECALC.nsp -I path/to/workspace --emit-python

# Inspect emitted SQLAlchemy ORM models from a DDM
natural parse path/to/TARIFF.ddm --emit-orm

```

---

## Compiler Architecture

1. **Pass 1: Island Parser (`pass1_island.lark`):**
* Uses an island grammar to separate structural blocks (`FIND`, `READ`, `IF`, `REPEAT`, `FOR`, `DECIDE`, `DEFINE DATA`, `DEFINE SUBROUTINE`, `READ WORK FILE`) from arbitrary statement payloads.
* Tolerates custom macros and vendor dialects without breaking block hierarchy.


2. **Pass 2: Specialized Statement Dispatcher (`pass2_dispatcher.py`):**
* Dispatches block bodies and raw statements to dedicated micro-parsers (`MathParser`, `StringOpParser`, `DatabaseOpParser`, `WorkFileParser`, `DecideParser`, etc.).
* Generates a fully typed Syntactic AST (IR0).


3. **Pass 3: Semantic Lowering (`lowering.py`):**
* Resolves symbols, parameters, and variable redefinitions (`REDEFINE` maps to getter/setter properties).
* Normalizes Adabas query loops into `QueryIterationOp` instances with explicit criteria and limit clauses.
* Resolves loop exit labels (`ESCAPE BOTTOM (L1.)`) across an active loop stack.


4. **Pass 4: Target Emitters (`python_emitter.py`, `orm_emitter.py`):**
* Analyzes symbol usage dynamically to emit only required imports (`Decimal`, `date`, `datetime`, `timedelta`, `os`).
* Generates type-hinted context models, subroutine handlers, and batch processing logic.



---

## Project Structure

```text
.
├── build.sh                                # Automated build, test, bless, and run driver
├── pyproject.toml                          # Project configuration and dependencies
├── src/
│   └── natural/
│       ├── cli.py                          # Typer CLI orchestrator and diffing
│       ├── codegen/
│       │   ├── orm_emitter.py              # DDM view to SQLAlchemy model generator
│       │   └── python_emitter.py           # IR1 to Python business logic generator
│       ├── grammar/
│       │   └── pass1_island.lark           # Lark island grammar for structural blocks
│       ├── ir/
│       │   ├── models.py                   # IR0 Syntactic AST definitions
│       │   ├── pass1_models.py             # Pass 1 coarse block schemas
│       │   ├── semantic.py                 # IR1 Semantic DAG & symbol table models
│       │   └── serializer.py               # Clean YAML serializer with empty-node pruning
│       └── normalizer/
│           ├── lowering.py                 # Semantic Lowering Pass (IR0 -> IR1)
│           ├── pass1_parser.py             # Island grammar parser and AST builder
│           ├── pass2_dispatcher.py         # Pass 2 statement dispatcher
│           ├── workspace.py                # DDM, NSA, and copycode dependency resolver
│           └── parsers/                    # Micro-parsers (assign, decide, math, db, etc.)
└── tests/
    ├── conftest.py                         # Pytest custom flags (--bless, --verbose-test)
    ├── test_fixtures.py                    # Golden-master test engine
    └── fixtures/                           # End-to-end .test feature specifications
        ├── compress.test
        ├── decide_for.test
        ├── decide_on.test
        ├── examine.test
        ├── for_loop.test
        ├── if_nested.test
        ├── math_ops.test
        ├── move_edited.test
        ├── redefine.test
        ├── repeat_loop.test
        ├── reset.test
        └── subroutine.test

```


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
