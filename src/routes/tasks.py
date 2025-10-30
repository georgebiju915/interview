from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from typing import List

from ..database import Sessionlocal
from ..schemas import TaskCreate, TaskUpdate, TaskOut
from ..services import task_service

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# -----------------------------
# Dependency
# -----------------------------
def get_db():
    db = Sessionlocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# GET /api/tasks
# -----------------------------
@router.get("/", response_model=List[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    """
    Get all active (non-deleted) tasks.
    """
    try:
        tasks = task_service.get_all_tasks(db)
        return [t for t in tasks if not t.is_deleted]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch tasks: {str(e)}")


# -----------------------------
# GET /api/tasks/{task_id}
# -----------------------------
@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, db: Session = Depends(get_db), request: Request = None):
    """
    Get a single task by ID.
    """
    try:
        task = task_service.get_task(db, task_id)
        if not task or task.is_deleted:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch task: {str(e)}")


# -----------------------------
# POST /api/tasks
# -----------------------------
@router.post("/", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,  # ✅ must be FIRST — FastAPI reads JSON here
    db: Session = Depends(get_db),
    offline: bool = Query(False, description="Queue creation if offline"),  # ✅ optional query param
):
    """
    Create a new task.
    If `offline=true`, the creation is queued instead of immediately synced.
    """
    try:
        new_task = task_service.create_task(
            db=db,
            title=payload.title,
            description=payload.description,
            offline=offline,
        )
        return new_task
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")

# -----------------------------
# PUT /api/tasks/{task_id}
# -----------------------------
@router.put("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    offline: bool = Query(False, description="Queue update if offline"),
    db: Session = Depends(get_db),
):
    """
    Update an existing task.
    Returns 404 if task not found.
    """
    try:
        updated_task = task_service.update_task(
            db,
            task_id,
            updates=payload.dict(exclude_none=True),
            offline=offline,
        )

        if not updated_task:
            raise HTTPException(status_code=404, detail="Task not found")

        return updated_task

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update task: {str(e)}")


# -----------------------------
# DELETE /api/tasks/{task_id}
# -----------------------------
@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    offline: bool = Query(False, description="Queue deletion if offline"),
    db: Session = Depends(get_db),
):
    """
    Soft delete a task (marks `is_deleted=True`).
    Returns a consistent error format on failure.
    """
    try:
        deleted = task_service.delete_task(db, task_id, offline=offline)
        if not deleted:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "message": (
                "Task marked as deleted"
                if not offline
                else "Task deletion queued for sync"
            ),
            "task_id": task_id,
            "offline": offline,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {str(e)}")
