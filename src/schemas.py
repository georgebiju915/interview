from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# Defines what data is needed when creating a new task
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None

# Defines what data can be changed when updating a task
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None

# Defines how task data is returned to the client
class TaskOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    completed: bool
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    sync_status: str
    server_id: Optional[str]
    last_synced_at: Optional[datetime]

    class Config:
        from_attributes = True  # lets Pydantic read from ORM models directly
