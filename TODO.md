The core schema engine is **around 95% complete**. You now have a target-agnostic Schema IR (IR-S), bounds capture, 1NF relational normalization, the `KeyedArray` / proxy runtime layer, five export targets (SQLAlchemy, SQL DDL, Mongoose, Prisma, OpenAPI 3.0), and dedicated CLI tooling.

There are four specific operational and edge-case gaps remaining in the schema layer:

---

### 1. Query Filtering on Normalized 1NF Child Tables (The Primary Functional Gap)

Currently, `SchemaNormalizer` shreds tables into parent/child relations, and `AdabasArrayProxy` handles runtime in-memory reads and writes (`record.lang['1'] = 'ES'`).

However, if a Natural program executes a database search on an array:

```natural
FIND EMPLOYEES WITH LANG = 'FR'

```

* **Current JSON mode:** Emits `session.query(Employees).filter(Employees.lang == 'FR')` (or JSON containment).
* **Normalized 1NF mode:** Because `lang` on `Employees` is now an `@property` proxy descriptor rather than a mapped SQL column, executing `Employees.lang == 'FR'` inside SQLAlchemy's `.filter()` will fail.
* **What's needed:** In `src/natural/normalizer/lowering/handlers/database.py`, when `--normalize-arrays` is active and a query predicate targets a relation (like `LANG`), the compiler must emit a SQLAlchemy relationship subquery:
```python
session.query(Employees).filter(Employees._lang.any(EmployeesLang.value == 'FR'))

```



---

### 2. SQL Generated/Virtual Columns for Superdescriptors (`SP`) & Subdescriptors (`SB`)

You already parse and model superdescriptors (`SP`) as composite indexes in `SchemaIndex`.

However, in raw SQL DDL (`sql_ddl.py`), an Adabas superdescriptor can also be queried as a field itself. Modern relational databases (PostgreSQL 12+, MySQL 5.7+, SQLite 3.31+) support stored virtual columns:

```sql
-- Generated SQL DDL enhancement for Superdescriptors:
sec_key VARCHAR(14) GENERATED ALWAYS AS (SUBSTRING(name FROM 1 FOR 10) || SUBSTRING(dept FROM 1 FOR 4)) STORED;
CREATE INDEX ix_employees_sec_key ON employees (sec_key);

```

Adding this to `SqlDdlEmitter` allows SQL queries like `SELECT * FROM employees WHERE sec_key = '...'` to execute against the virtual column using the index.

---

### 3. Cross-DDM Referential Integrity (Inter-Table Foreign Keys)

Adabas files are isolated inverted-list files without native foreign key constraints across files. Relationships between different DDMs (e.g., `ORDERS.CUST-ID` referencing `CUSTOMERS.CUST-ID`) are purely logical.

* Currently, foreign keys are only generated for decomposed 1NF array tables (`employee_lang.employee_id -> employee.id`).
* **What could be added:** A simple heuristic or mapping file (`schema_relations.yaml`) that lets you declare inter-DDM relationships so that `SqlDdlEmitter`, `PrismaSchemaEmitter`, and `ORMEmitter` generate top-level foreign keys across entities:
```sql
ALTER TABLE orders ADD CONSTRAINT fk_orders_customer FOREIGN KEY (cust_id) REFERENCES customers(id);

```



---

### 4. Migration Script Generators (Alembic / Flyway)

Currently, `natural schema export` outputs full `CREATE TABLE` DDL. In production environments where DDMs change over time:

* An Alembic migration generator (Python) or Flyway/Liquibase migration script generator (`V1__initial.sql`, `V2__add_bonus.sql`) that diffs two `SchemaCatalog` snapshots and generates `ALTER TABLE` statements.
