from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .tasks import get_db
from ..database import Sessionlocal
from ..services.sync_service import process_sync_once, sync_pending_tasks
from ..services.local_queue import sync_queue

# Create an API router for sync-related endpoints
router = APIRouter(prefix="/api/sync", tags=["sync"])

# Re-initialize the router (this overrides the one above — probably unintentional)
router = APIRouter()

@router.post("/")
def trigger_sync(db: Session = Depends(get_db)):
    # This endpoint triggers the synchronization of all pending tasks
    # Calls a service function that handles syncing items waiting in the queue
    result = sync_pending_tasks(db)
    # Returns a summary of the sync process
    return {"message": "Sync complete", **result}

def get_db():
    # Dependency to get a database session
    db = Sessionlocal()
    try:
        yield db
    finally:
        # Ensures the database connection is closed after the request
        db.close()

@router.post("/")
def trigger_sync(db: Session = Depends(get_db)):
    """
    Trigger one sync batch.
    In a real application the client would call this when connectivity is restored,
    or the server process would run a background sync worker.
    """
    # Runs one batch of the sync process using the provided database session
    result = process_sync_once(db)
    # Returns detailed information about the sync results
    return {
        "success": True,
        "synced_items": result.get("synced_items"),
        "failed_items": result.get("failed_items"),
        "conflicts": result.get("conflicts"),
        "remaining_in_queue": result.get("remaining")
    }

@router.get("/status")
def status():
    # Endpoint to check the current synchronization status
    # Returns how many tasks are still pending and whether the system is online
    return {
        "pending_sync_count": sync_queue.size(),
        "is_online": True  # Placeholder: in a real case, perform an actual connectivity check
    }
