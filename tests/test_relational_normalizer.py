# tests/test_relational_normalizer.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

from decimal import Decimal
from pathlib import Path
from natural.normalizer.workspace import Workspace
from natural.normalizer.schema_builder import SchemaBuilder
from natural.normalizer.schema_normalizer import SchemaNormalizer
from natural.codegen.schema.sql_ddl import SqlDdlEmitter
from natural.codegen.targets.python.orm import ORMEmitter
from natural.codegen.targets.python.runtime.arrays import AdabasArrayProxy, AdabasObjectArrayProxy


def test_schema_normalizer_decomposition(tmp_path: Path):
    ddm_content = """
1 AC NAME                                 A   20  N N
1 AB LANG                                 A    3  N (1:3)
1 PE PERIODS                                        (1:2)
2 BD YR                                   N  4.0
2 MU TASKS                                A    3  N (1:3)
"""
    (tmp_path / "STAFF.ddm").write_text(ddm_content.strip(), encoding="utf-8")

    ws = Workspace(include_dirs=[tmp_path])
    ddm = ws.get_ddm("STAFF")
    assert ddm is not None

    catalog = SchemaBuilder([ddm]).build_catalog()
    normalizer = SchemaNormalizer()
    norm_catalog = normalizer.normalize(catalog)

    # 1. Assert Parent Document decomposition
    parent = norm_catalog.get_document("STAFF")
    assert parent is not None
    assert len(parent.nodes) == 1
    assert parent.nodes[0].name == "name"

    # Relations on parent
    rel_names = {r.proxy_property: r for r in parent.relations}
    assert "lang" in rel_names
    assert "periods" in rel_names
    assert rel_names["lang"].is_object_array is False
    assert rel_names["periods"].is_object_array is True

    # 2. Assert Child Document for MU: staff_lang
    lang_doc = norm_catalog.get_document("STAFF_LANG")
    assert lang_doc is not None
    lang_nodes = {n.name: n for n in lang_doc.nodes}
    assert "staff_id" in lang_nodes
    assert lang_nodes["staff_id"].is_foreign_key is True
    assert lang_nodes["staff_id"].references_table == "staff"
    assert "natural_index" in lang_nodes
    assert "value" in lang_nodes
    assert len(lang_doc.indexes) == 1
    assert lang_doc.indexes[0].is_unique is True

    # 3. Assert Child Document for PE: staff_periods
    pe_doc = norm_catalog.get_document("STAFF_PERIODS")
    assert pe_doc is not None
    pe_nodes = {n.name: n for n in pe_doc.nodes}
    assert "staff_id" in pe_nodes
    assert "yr" in pe_nodes

    # 4. Assert Grandchild Document for nested MU in PE: staff_periods_tasks
    task_doc = norm_catalog.get_document("STAFF_PERIODS_TASKS")
    assert task_doc is not None
    task_nodes = {n.name: n for n in task_doc.nodes}
    assert "staff_periods_id" in task_nodes
    assert task_nodes["staff_periods_id"].references_table == "staff_periods"
    assert "value" in task_nodes


def test_normalized_sql_ddl_and_orm_emission(tmp_path: Path):
    ddm_content = """
1 AC NAME                                 A   20  N N
1 AB LANG                                 A    3  N (1:3)
"""
    (tmp_path / "STAFF.ddm").write_text(ddm_content.strip(), encoding="utf-8")

    ws = Workspace(include_dirs=[tmp_path])
    catalog = SchemaBuilder([ws.get_ddm("STAFF")]).build_catalog()
    norm_catalog = SchemaNormalizer().normalize(catalog)

    # 1. SQL DDL
    sql_ddl = SqlDdlEmitter(norm_catalog, dialect="postgres").generate()["staff_lang.sql"]
    assert "CREATE TABLE staff_lang (" in sql_ddl
    assert "staff_id INTEGER REFERENCES staff(id) ON DELETE CASCADE," in sql_ddl
    assert "natural_index INTEGER," in sql_ddl
    assert "value VARCHAR(3)" in sql_ddl
    assert "CREATE UNIQUE INDEX uq_staff_lang_idx ON staff_lang (staff_id, natural_index);" in sql_ddl

    # 2. SQLAlchemy ORM
    orm_code = ORMEmitter(norm_catalog).generate()
    assert "_lang = relationship('StaffLang', cascade='all, delete-orphan', lazy='joined')" in orm_code
    assert "@property" in orm_code
    assert "def lang(self):" in orm_code
    assert "return AdabasArrayProxy(self._lang, StaffLang, value_attr='value')" in orm_code
    assert "staff_id = Column('staff_id', Integer, ForeignKey('staff.id'))" in orm_code


def test_adabas_array_proxy_runtime():
    class DummyLangRow:
        def __init__(self, natural_index: int = 1, value: str = ""):
            self.natural_index = natural_index
            self.value = value

    rows = [
        DummyLangRow(natural_index=1, value="EN"),
        DummyLangRow(natural_index=2, value="DE"),
    ]

    proxy = AdabasArrayProxy(rows, DummyLangRow, value_attr="value")

    # Read by string index & int index
    assert proxy["1"] == "EN"
    assert proxy[1] == "EN"
    assert proxy["2"] == "DE"

    # Write by index (updates existing row)
    proxy["2"] = "ES"
    assert rows[1].value == "ES"

    # Write to new index (appends new row)
    proxy["3"] = "FR"
    assert len(rows) == 3
    assert rows[2].natural_index == 3
    assert rows[2].value == "FR"
    assert proxy["3"] == "FR"

    # Slicing
    assert proxy[0:2] == ["EN", "ES"]
    assert proxy["1":"2"] == ["EN", "ES"]


def test_adabas_object_array_proxy_runtime():
    class DummyPeriodRow:
        def __init__(self, natural_index: int = 1, yr: Decimal = Decimal("0"), amt: Decimal = Decimal("0")):
            self.natural_index = natural_index
            self.yr = yr
            self.amt = amt

    rows = []
    proxy = AdabasObjectArrayProxy(rows, DummyPeriodRow)

    # Automatically instantiates row on access
    item1 = proxy["1"]
    item1.yr = Decimal("2026")
    item1["amt"] = Decimal("500.00")

    assert len(rows) == 1
    assert rows[0].natural_index == 1
    assert rows[0].yr == Decimal("2026")
    assert rows[0].amt == Decimal("500.00")
    assert proxy["1"].yr == Decimal("2026")
    assert proxy[1]["amt"] == Decimal("500.00")
