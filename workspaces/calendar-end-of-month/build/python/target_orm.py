from sqlalchemy.orm import declarative_base
Base = declarative_base()

# Dynamic fallback for undefined views
def __getattr__(name):
    return type(name, (Base,), {'__tablename__': name.lower()})
