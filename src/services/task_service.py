from sqlalchemy.orm import Session
from datetime import datetime, timezone
from ..models import Task, SyncQueue
from ..services.local_queue import sync_queue
from ..utils import now_iso, parse_iso

# -----------------------------------------------
# 🧩 Task Service Functions
# -----------------------------------------------
# These functions manage the lifecycle of tasks:
# - Creating, updating, and deleting tasks in the database
# - Handling both online and offline modes
# - Adding offline operations to a local sync queue
# -----------------------------------------------


def queue_operation(db: Session, task_id: str, operation: str, data: dict):
    """
    Store a sync operation (create/update/delete) in the database queue.

    This queue acts like a "to-do list" for sync tasks that need to be sent
    to a remote server when connectivity is available again.
    """
    queue_item = SyncQueue(
        task_id=task_id,
        operation=operation,
        data=data
    )
    db.add(queue_item)
    db.commit()
    db.refresh(queue_item)


def get_all_tasks(db: Session):
    """
    Get all tasks that are not deleted.

    This simply returns active tasks from the database.
    """
    return db.query(Task).filter(Task.is_deleted == False).all()


def get_task(db: Session, task_id: str):
    """
    Get a single task by ID.

    If the task doesn’t exist, returns None instead of crashing.
    """
    return db.query(Task).filter(Task.id == task_id).first()


def create_task(db: Session, title: str, description: str = None, offline: bool = False):
    """
    Create a new task.

    If `offline=True`, the task is marked as "pending" and added
    to the local sync queue instead of being synced immediately.
    This allows users to create tasks while offline — the sync will
    happen later when they're back online.
    """
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
        # Convert timestamps into ISO strings so they can be compared easily later
        payload = {
            "title": task.title,
            "description": task.description,
            "completed": task.completed,
            "updated_at": task.updated_at.isoformat()
        }

        # Add this create action to the local sync queue (stored in sync_queue.json)
        sync_queue.add(task.id, "create", payload)

    return task


def update_task(db: Session, task_id: str, updates: dict, offline: bool = False):
    """
    Update an existing task.

    - If the task doesn’t exist or has been deleted, do nothing.
    - If working offline, the change is queued locally instead of
      being sent to the server right away.
    """
    task = get_task(db, task_id)
    if not task or task.is_deleted:
        return None

    # Apply only the fields that are included in the update
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
        # Prepare a simplified version of the task for the local sync queue
        payload = {
            "title": task.title,
            "description": task.description,
            "completed": task.completed,
            "updated_at": task.updated_at.isoformat()
        }

        # Add this update to the local queue to sync later
        sync_queue.add(task.id, "update", payload)

    return task


def delete_task(db: Session, task_id: str, offline: bool = False):
    """
    Soft delete a task (mark it as deleted instead of permanently removing it).

    This is safer because it allows recovery and makes syncing easier.
    If the app is offline, the delete action is queued and synced later.
    """
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
        # For delete operations, we only care about when it happened
        payload = {
            "updated_at": task.updated_at.isoformat()
        }

        # Add this delete action to the local queue
        sync_queue.add(task.id, "delete", payload)

    return task
