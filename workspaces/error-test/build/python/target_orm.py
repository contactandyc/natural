from sqlalchemy import Column, String, Numeric, Integer, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Emp(Base):
    __tablename__ = 'emp'

    name = Column('name', String(20), primary_key=True)
    salary = Column('salary', Numeric(7, 2))
