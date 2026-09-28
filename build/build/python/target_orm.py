from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def __getattr__(name):
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    cls_dict = {
        '__tablename__': name.lower(),
        'id': Column('id', Integer, primary_key=True, autoincrement=True),
        'name': Column('name', String(255), default=""),
    }
    return type(name, (Base,), cls_dict)
