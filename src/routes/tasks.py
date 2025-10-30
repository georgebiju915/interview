from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from ..database import Sessionlocal
from ..schemas import TaskCreate, TaskUpdate, TaskOut
from ..services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

def get_db():
    db = Sessionlocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=List[TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return task_service.get_all_tasks(db)

@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = task_service.get_task(db, task_id)
    if not task or task.is_deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, offline: bool = Query(False), db: Session = Depends(get_db)):
    """
    Create a task. Query param `offline=true` will add operation to local queue.
    In a real client, the client would decide offline vs online; here we allow testing with this flag.
    """
    task = task_service.create_task(db, title=payload.title, description=payload.description, offline=offline)
    return task

@router.put("/{task_id}", response_model=TaskOut)
def update_task(task_id: str, payload: TaskUpdate, offline: bool = Query(False), db: Session = Depends(get_db)):
    updated = task_service.update_task(db, task_id, updates=payload.dict(exclude_none=True), offline=offline)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return updated

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, offline: bool = Query(False), db: Session = Depends(get_db)):
    deleted = task_service.delete_task(db, task_id, offline=offline)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return
