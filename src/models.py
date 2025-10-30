
from sqlalchemy import  Column, String, Boolean, DateTime, Integer, JSON, func, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from src.database import Base

# functionn for generating uuid  no argumnets
def gen_uuid():
    return str(uuid.uuid4())

# class for creating model task for storing the data about the task
class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, default=gen_uuid)  # client UUID
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    sync_status = Column(String, default="pending", nullable=False)  # pending/synced/error
    server_id = Column(String, nullable=True)  # id assigned by remote server
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

sync_items = relationship("SyncQueueItem", back_populates="task", cascade="all, delete-orphan")
