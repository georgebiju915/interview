from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import Sessionlocal
from ..services.sync_service import process_sync_once
from ..services.local_queue import sync_queue

router = APIRouter(prefix="/api/sync", tags=["sync"])

def get_db():
    db = Sessionlocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/")
def trigger_sync(db: Session = Depends(get_db)):
    """
    Trigger one sync batch.
    In a real application the client would call this when connectivity is restored,
    or the server process would run a background sync worker.
    """
    result = process_sync_once(db)
    return {
        "success": True,
        "synced_items": result.get("synced_items"),
        "failed_items": result.get("failed_items"),
        "conflicts": result.get("conflicts"),
        "remaining_in_queue": result.get("remaining")
    }

@router.get("/status")
def status():
    return {
        "pending_sync_count": sync_queue.size(),
        "is_online": True  # Replace with a real network check if needed
    }
