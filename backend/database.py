from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker 
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import Engine
from sqlalchemy import event
import os

SQLALCHEMY_DATABASE_URL = "sqlite:///./medtracker.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}, 
    poolclass=StaticPool # mostly used in unit tests or ephemeral environments where you want the database to vanish after the test run.
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()