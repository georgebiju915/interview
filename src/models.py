from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON, func, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from src.database import Base

# Create a random unique ID
def gen_uuid():
    return str(uuid.uuid4())

# Task table — keeps info about each task
class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    sync_status = Column(String, default="pending", nullable=False)  # sync state
    server_id = Column(String, nullable=True)  # ID from remote server
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

# Sync queue table — tracks changes waiting to sync
class SyncQueue(Base):
    __tablename__ = "sync_queue"
    id = Column(String, primary_key=True, default=gen_uuid)
    task_id = Column(String, nullable=False)
    operation = Column(String, nullable=False)  # create/update/delete
    data = Column(JSON, nullable=False)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_error = Column(String, nullable=True)

# Optional link between tasks and sync queue
sync_items = relationship("SyncQueueItem", back_populates="task", cascade="all, delete-orphan")
