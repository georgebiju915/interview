from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON, Text, func
from datetime import datetime
from src.database import Base
import uuid


def gen_uuid():
    """Generate a random UUID as a string."""
    return str(uuid.uuid4())


# -----------------------------------------
# 🗂️ Task Table
# -----------------------------------------
class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )
    is_deleted = Column(Boolean, default=False, nullable=False)
    sync_status = Column(String, default="pending", nullable=False)
    server_id = Column(String, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)


# -----------------------------------------
# 🔁 Sync Queue Table
# -----------------------------------------
class SyncQueue(Base):
    __tablename__ = "sync_queue"

    id = Column(String, primary_key=True, default=gen_uuid)
    task_id = Column(String, nullable=False)
    operation = Column(String, nullable=False)  # create/update/delete
    data = Column(JSON, nullable=False)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_error = Column(String, nullable=True)
