from sqlalchemy import Column, String, Numeric, Integer, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Tariff(Base):
    __tablename__ = 'tariff'

    class_ = Column('class', String(4), primary_key=True)
    zone = Column('zone', String(6))
    rate = Column('rate', Numeric(7, 2))
    weight_limit = Column('weight-limit', Numeric(7, 2))
    heavy_surcharge = Column('heavy-surcharge', Numeric(7, 2))
