# tests/test_schema_emitters.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from natural.normalizer.workspace import Workspace
from natural.normalizer.schema_builder import SchemaBuilder
from natural.codegen.schema.sql_ddl import SqlDdlEmitter
from natural.codegen.schema.mongo import MongoSchemaEmitter
from natural.codegen.schema.prisma import PrismaSchemaEmitter
from natural.codegen.schema.openapi import OpenApiSchemaEmitter
from natural.codegen.targets.python.orm import ORMEmitter
from natural.ir.schema import SchemaIndexType, SchemaNodeType


def test_index_modeling_and_descriptors(tmp_path: Path):
    ddm_content = """
1 AC DEPT                                 A    4  D N
1 AE SSN                                  A    9  U N
1 SP SEC-KEY                              A   14  S (NAME(1:10), DEPT(1:4))
1 AC NAME                                 A   10  N N
"""
    (tmp_path / "EMPLOYEES.ddm").write_text(ddm_content.strip(), encoding="utf-8")

    ws = Workspace(include_dirs=[tmp_path])
    ddm = ws.get_ddm("EMPLOYEES")
    assert ddm is not None

    builder = SchemaBuilder([ddm])
    doc = builder.build_document(ddm)

    # 1. Verify Index extraction in IR-S
    idx_by_name = {idx.source_name: idx for idx in doc.indexes}
    assert "DEPT" in idx_by_name
    assert idx_by_name["DEPT"].index_type == SchemaIndexType.STANDARD
    assert idx_by_name["DEPT"].is_unique is False

    assert "SSN" in idx_by_name
    assert idx_by_name["SSN"].index_type == SchemaIndexType.UNIQUE
    assert idx_by_name["SSN"].is_unique is True

    assert "SEC-KEY" in idx_by_name
    assert idx_by_name["SEC-KEY"].index_type == SchemaIndexType.SUPER
    assert len(idx_by_name["SEC-KEY"].parts) == 2
    assert idx_by_name["SEC-KEY"].parts[0].field_name == "name"
    assert idx_by_name["SEC-KEY"].parts[1].field_name == "dept"

    # 2. Verify SQLAlchemy __table_args__ generation
    orm = ORMEmitter([ddm]).generate()
    assert "__table_args__ = (" in orm
    assert "Index('ix_employees_dept', 'dept')" in orm
    assert "Index('ix_employees_ssn', 'ssn', unique=True)" in orm
    assert "Index('ix_employees_sec_key', 'name', 'dept')" in orm


def test_multidimensional_array_mu_in_pe(tmp_path: Path):
    ddm_content = """
1 CA PROJ-ID                              I    4  N N
1 PE PERIODS                                        (1:2)
2 BD YR                                   N  4.0
2 MU TASKS                                A    3  N (1:3)
"""
    (tmp_path / "PROJECTS.ddm").write_text(ddm_content.strip(), encoding="utf-8")

    ws = Workspace(include_dirs=[tmp_path])
    ddm = ws.get_ddm("PROJECTS")
    assert ddm is not None

    builder = SchemaBuilder([ddm])
    doc = builder.build_document(ddm)

    periods_node = doc.get_node("PERIODS")
    assert periods_node is not None
    assert periods_node.node_type == SchemaNodeType.ARRAY_OBJECT

    tasks_node = next(ch for ch in periods_node.children if ch.name == "tasks")
    assert tasks_node.node_type == SchemaNodeType.ARRAY_PRIMITIVE
    assert tasks_node.index_keys == ["1", "2", "3"]

    # Verify ORM generates nested keyed dictionary defaults
    orm = ORMEmitter([ddm]).generate()
    assert "'tasks': {'1': '', '2': '', '3': ''}" in orm


def test_pluggable_schema_emitters(tmp_path: Path):
    ddm_content = """
1 AC NAME                                 A   20  D N
1 AB LANG                                 A    3  N (1:3)
1 AE SALARY                               P  7.2  N N
"""
    (tmp_path / "STAFF.ddm").write_text(ddm_content.strip(), encoding="utf-8")

    ws = Workspace(include_dirs=[tmp_path])
    catalog = SchemaBuilder([ws.get_ddm("STAFF")]).build_catalog()

    # 1. SQL DDL
    sql_emitter = SqlDdlEmitter(catalog, dialect="postgres")
    sql_ddl = sql_emitter.generate()["staff.sql"]
    assert "CREATE TABLE staff (" in sql_ddl
    assert "id SERIAL PRIMARY KEY," in sql_ddl
    assert "name VARCHAR(20)," in sql_ddl
    assert "lang JSONB" in sql_ddl
    assert "salary NUMERIC(7, 2)" in sql_ddl
    assert "CREATE INDEX ix_staff_name ON staff (name);" in sql_ddl

    # 2. MongoDB Mongoose
    mongo_emitter = MongoSchemaEmitter(catalog)
    mongo_ts = mongo_emitter.generate()["staff.ts"]
    assert "const StaffSchema = new Schema({" in mongo_ts
    assert "name: { type: String }" in mongo_ts
    assert "lang: { type: Map, of: String }" in mongo_ts
    assert "salary: { type: Schema.Types.Decimal128 }" in mongo_ts
    assert "StaffSchema.index({ name: 1 });" in mongo_ts

    # 3. Prisma
    prisma_emitter = PrismaSchemaEmitter(catalog)
    prisma_schema = prisma_emitter.generate()
    assert "model Staff {" in prisma_schema
    assert "name String?" in prisma_schema
    assert "lang Json?" in prisma_schema
    assert "salary Decimal?" in prisma_schema
    assert "@@index([name])" in prisma_schema

    # 4. OpenAPI 3.0
    openapi_emitter = OpenApiSchemaEmitter(catalog)
    openapi_yaml = openapi_emitter.generate()
    assert "openapi: 3.0.3" in openapi_yaml
    assert "Staff:" in openapi_yaml
    assert "maxLength: 20" in openapi_yaml
