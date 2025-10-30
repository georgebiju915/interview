# data base for the Api
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
Database_url=os.getenv("Database_URL","sqlite:///./task.db")
engine = create_engine(Database_url,connect_args={'check_same_thread': False})
Sessionlocal = sessionmaker(autocommit=False,autoflush=False,bind=engine)
Base = declarative_base()