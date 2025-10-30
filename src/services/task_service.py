from sqlalchemy.orm import Session
from datetime import datetime, timezone
from ..models import Task
from ..services.local_queue import sync_queue
from ..utils import now_iso, parse_iso

def get_all_tasks(db: Session):
    return db.query(Task).filter(Task.is_deleted == False).all()

def get_task(db: Session, task_id: str):
    return db.query(Task).filter(Task.id == task_id).first()

def create_task(db: Session, title: str, description: str = None, offline: bool = False):
    now = datetime.now(timezone.utc)
    task = Task(
        title=title,
        description=description,
        completed=False,
        created_at=now,
        updated_at=now,
        is_deleted=False,
        sync_status="pending" if offline else "synced"
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    if offline:
        # Ensure updated_at is ISO string for LWW comparison
        payload = {
            "title": task.title,
            "description": task.description,
            "completed": task.completed,
            "updated_at": task.updated_at.isoformat()
        }
        sync_queue.add(task.id, "create", payload)

    return task

def update_task(db: Session, task_id: str, updates: dict, offline: bool = False):
    task = get_task(db, task_id)
    if not task or task.is_deleted:
        return None

    if "title" in updates and updates["title"] is not None:
        task.title = updates["title"]
    if "description" in updates:
        task.description = updates["description"]
    if "completed" in updates:
        task.completed = updates["completed"]

    now = datetime.now(timezone.utc)
    task.updated_at = now
    task.sync_status = "pending" if offline else "synced"

    db.commit()
    db.refresh(task)

    if offline:
        payload = {
            "title": task.title,
            "description": task.description,
            "completed": task.completed,
            "updated_at": task.updated_at.isoformat()
        }
        sync_queue.add(task.id, "update", payload)

    return task

def delete_task(db: Session, task_id: str, offline: bool = False):
    task = get_task(db, task_id)
    if not task:
        return None

    now = datetime.now(timezone.utc)
    task.is_deleted = True
    task.updated_at = now
    task.sync_status = "pending" if offline else "synced"

    db.commit()
    db.refresh(task)

    if offline:
        payload = {
            "updated_at": task.updated_at.isoformat()
        }
        sync_queue.add(task.id, "delete", payload)

    return task
