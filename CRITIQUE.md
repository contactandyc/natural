# Architectural Critique & Strategic Roadmap

This is a remarkably well-architected and mature compiler framework. By adopting an LLVM-style multi-pass pipeline (Frontend Parser $\rightarrow$ AST (IR0) $\rightarrow$ Semantic Lowering $\rightarrow$ Semantic DAG (IR1) $\rightarrow$ Target Backend), you have avoided the notorious "regex-replace script" trap that causes most legacy modernization projects to fail. Your use of a target-agnostic IR1, a dedicated `natural_runtime` to absorb mainframe idiosyncrasies, and the golden-master mock database test harness are all elite engineering decisions.

### 🌟 Recent Engineering Triumphs

Since the last review, the framework has crossed major architectural thresholds:
- **Eradication of Regex Micro-Parsers:** Transitioning Pass 2 to compose unified Context-Free Grammars (`Lark` + `SHARED_EXPR_GRAMMAR`) guarantees deep syntactic safety for nested operations, arrays, dynamic slices, and complex string handling.
- **Pluggable Target Backends:** Relocating Python codegen under a `TargetBackend` protocol cleanly isolates semantic rules from language-specific syntax.
- **Target Runtime Libraries (`natural_runtime`):** Abstracting mainframe idiosyncrasies (financial edit masks, 1-based dynamic arrays, string substring splices, column tabulation) into a modular runtime prevents generated business logic from drowning in emulation boilerplate.
- **Semantic Test Runner:** The dual-track testing suite (`evaluate` vs `bless`) combined with in-memory dynamic execution via `MockSession` ensures mathematically proven behavioral parity with the mainframe.

To support your continued goals of **hardening correctness, scaling multi-language output, advanced schema translation, and migrating to an API + React frontend architecture**, here is the strategic roadmap for your next steps.

---

### 1. Hardening Compiler Correctness

**A. Strict Type Coercion in Semantic Lowering**
Natural is famously loose with types. A runtime crash will occur in strongly-typed languages (like Go, C#, or TypeScript) if a generated program attempts to move alphanumeric data into a decimal field without explicit casting. Currently, Python handles this via `unmask_decimal` at runtime, but this won't scale.

- **The Fix:** Implement formal **Type Inference** during the lowering from IR0 to IR1. If the compiler detects an assignment or arithmetic operation where the source and target `SemanticType` differ, it should explicitly inject a `CastOp` node into IR1. The backend emitter then simply translates `CastOp` to the target language's native casting syntax, removing all type guesswork during code generation.

**B. Control Flow Graph (CFG) & Def-Use Analysis**
Currently, variables safely fall back to initialized default values, but the compiler does not validate code reachability.
- **The Fix:** Implement a CFG analysis pass over IR1 to detect uninitialized variable usage and unreachable logic (e.g. statements after an unconditional `ESCAPE ROUTINE` or `STOP`). This will emit compile-time warnings and elevate the toolchain to modern static analysis standards.

---

### 2. Scaling to Multi-Language Outputs

Your `TargetBackend` protocol is a solid contract, but the current `PythonEmitter` constructs code via imperative string concatenation (`ctx.emit_line(...)`).

**A. Transition from String Concatenation to Templates or Target ASTs**
Writing manual string-concatenation logic for TypeScript, Go, and C# will become a maintenance nightmare (tracking indentation, imports, and language-specific operator precedence).
- **The Fix:** Decouple the logic of the compiler from the syntactic emission mechanism.
- *Option 1 (Target AST):* Map IR1 into a generic Abstract Syntax Tree for the target language (like Python's `ast` module or TypeScript's Compiler API), and use native unparsers to guarantee 100% syntactically valid code.
- *Option 2 (Templates):* Pass IR1 semantic objects into a templating engine like **Jinja2** (e.g., `for_loop.ts.j2` vs `for_loop.py.j2`).

**B. Expand Target Runtimes (TypeScript / Node)**
You must port `natural_runtime` exactly for any new target.
- *Crucial Note for TypeScript:* JavaScript/TypeScript native `number` types are 64-bit floating points, which will fail exact accounting math. Your TypeScript runtime must utilize a library like `decimal.js` or `big.js` to ensure the emitted arithmetic operations match Python's `Decimal` and the mainframe's precision exactly.

---

### 3. Translating Data Models into Schemas

Adabas is a NoSQL (hierarchical/document) database. Modern target systems are typically Relational (SQL) or Document stores. Right now, your `ORMEmitter` maps Adabas Periodic Groups (`PE`) and Multiple Values (`MU`) directly to SQLAlchemy `JSON` columns. While this works well for a 1:1 behavioral port, it prevents efficient relational querying (e.g., "Find all employees who speak Spanish").

**A. Introduce a Schema IR (IR-S)**
Don't emit ORM code directly from the AST's `DataAreaRef`. Parse DDMs into an independent data-structure graph (`Schema IR`). From `Schema IR`, you can write pluggable generators for:
- Prisma schemas (`schema.prisma`) or Drizzle ORM for TypeScript
- Raw SQL DDL (`CREATE TABLE...`)
- **OpenAPI 3.0 / Swagger specs (JSON/YAML)**

**B. Relational Normalization Pass**
Add a compiler configuration flag (`--normalize-arrays`). If true, the `Schema IR` pass should automatically detect `PE` and `MU` fields and normalize them into separate **1:Many relational child tables** with synthetic Foreign Keys linking back to the parent record. The Semantic Lowering pass would then automatically translate Natural array accesses (`LANG(1)`) into relational ORM joins rather than JSON array indexing.

---

### 4. The Paradigm Shift: Migrating to API Backend + React Frontend

This is the holy grail of legacy modernization. **Natural is a stateful, procedural, terminal-based language.** It halts execution on an `INPUT` statement, waits for the user, and resumes with memory intact. **React + REST APIs are stateless, declarative, and distributed.**

To make this leap, the compiler must perform **Program Slicing (UI Decoupling)**.

**A. DTO (Data Transfer Object) Extraction**
The compiler must explicitly identify API contract boundaries:
- **Requests:** Variables requested by an `INPUT` statement become the **Request Payload DTO**. The compiler emits a Pydantic model (Python) or a Zod Schema (TypeScript).
- **Responses:** Variables printed to the screen via `WRITE`/`PRINT` become the **Response Payload DTO**.
- *Codegen Fix:* Introduce a `ResponsePayload` object into your generated `Context`. Instead of printing to stdout, `WriteOp` should emit code that appends structured dictionaries to `ctx.response_payload`. The API route simply ends with `return ctx.response_payload`.

**B. Control Flow as a State Machine (The `INPUT` Boundary)**
If a Natural program contains an `INPUT` statement inside a loop, an HTTP API cannot halt and wait.
- The compiler must slice the AST into a State Machine.
- The generated API takes the `Context` (state), executes business logic up to the next `INPUT` boundary, and returns the mutated `Context` alongside a `next_ui_screen` view pointer. The React frontend renders the screen, the user submits, and the API resumes execution from that specific state pointer.

**C. Frontend View Generation**
Because IR1 retains exact physical layout coordinates (e.g., `5T`, `35T`), it can generate UI components structurally. Create a `ReactTarget` backend that looks *only* for `INPUT` and `WRITE` operations in IR1.
- It translates absolute tab stops (`35T`) into modern CSS Grid/Flexbox properties:
```tsx
// Auto-generated by the Compiler
export const EmployeeRow = ({ data }: { data: EmployeeResponse }) => (
   <div className="natural-grid-container">
       <span style={{ gridColumn: 5 }}>{data.name}</span>
       <span style={{ gridColumn: 35 }}>{data.dept}</span>
   </div>
);
