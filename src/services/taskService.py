from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
from ..models import Task, SyncQueue
from ..services.local_queue import sync_queue


# ============================================================
# 🧩 Task Service Implementation (Python version of JS logic)
# ============================================================

def create_task(db: Session, title: str, description: str = None, offline: bool = False):
    try:
        new_task = Task(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            completed=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            sync_status="pending" if offline else "synced",
            is_deleted=False
        )

        db.add(new_task)
        db.commit()
        db.refresh(new_task)

        # If offline, add to sync queue
        if offline:
            queue_item = SyncQueue(
                id=str(uuid.uuid4()),
                task_id=new_task.id,
                operation="create",
                data={"title": title, "description": description},
                created_at=datetime.utcnow(),
            )
            db.add(queue_item)
            db.commit()

        return new_task

    except Exception as e:
        db.rollback()
        raise Exception(f"Error in create_task: {e}")


def update_task(db: Session, task_id: str, updates: dict, offline: bool = False):
    """
    Update an existing task.
    JS Equivalent:
      1. Check if task exists
      2. Update fields
      3. Update updated_at
      4. Set sync_status='pending'
      5. Add to sync queue
    """
    task = db.query(Task).filter(Task.id == task_id, Task.is_deleted == False).first()
    if not task:
        return None

    if "title" in updates and updates["title"] is not None:
        task.title = updates["title"]
    if "description" in updates:
        task.description = updates["description"]
    if "completed" in updates:
        task.completed = updates["completed"]

    task.updated_at = datetime.now(timezone.utc)
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
    """
    Soft delete a task.
    JS Equivalent:
      1. Check if task exists
      2. Set is_deleted=True
      3. Update updated_at
      4. Set sync_status='pending'
      5. Add to sync queue
    """
    task = db.query(Task).filter(Task.id == task_id, Task.is_deleted == False).first()
    if not task:
        return False

    task.is_deleted = True
    task.updated_at = datetime.now(timezone.utc)
    task.sync_status = "pending" if offline else "synced"

    db.commit()
    db.refresh(task)

    if offline:
        payload = {"updated_at": task.updated_at.isoformat()}
        sync_queue.add(task.id, "delete", payload)

    return True


def get_task(db: Session, task_id: str):
    """
    Get a single task.
    JS Equivalent:
      1. Query task by id
      2. Return None if not found or deleted
    """
    task = db.query(Task).filter(Task.id == task_id, Task.is_deleted == False).first()
    return task


def get_all_tasks(db: Session):
    """
    Get all non-deleted tasks.
    JS Equivalent:
      1. Query all where is_deleted=False
      2. Return array of tasks
    """
    return db.query(Task).filter(Task.is_deleted == False).all()


def get_tasks_needing_sync(db: Session):
    """
    Get all tasks that need syncing.
    JS Equivalent:
      1. Query where sync_status='pending' or 'error'
    """
    return db.query(Task).filter(Task.sync_status.in_(["pending", "error"])).all()
