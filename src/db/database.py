# Database setup for the API
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Use environment variable or default to local SQLite file
Database_url = os.getenv("Database_URL", "sqlite:///./task.db")

# Create database engine (check_same_thread=False is needed for SQLite)
engine = create_engine(Database_url, connect_args={'check_same_thread': False})

# Create session factory for database interactions
Sessionlocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all ORM models
Base = declarative_base()
