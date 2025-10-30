from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import Sessionlocal
from ..services.sync_service import process_sync_once
from ..services.local_queue import sync_queue

router = APIRouter(prefix="/api/sync", tags=["Sync"])


# --- Dependency ---
def get_db():
    """Provide a SQLAlchemy DB session for each request."""
    db = Sessionlocal()
    try:
        yield db
    finally:
        db.close()


# --- POST /api/sync ---
@router.post("/")
def trigger_sync(db: Session = Depends(get_db), request: Request = None):
    """
    Trigger a manual synchronization batch.
    Processes pending items from the local queue and applies changes to DB.
    """
    try:
        result = process_sync_once(db)
        return {
            "message": "Sync completed successfully",
            "synced_items": result.get("synced_items", 0),
            "failed_items": result.get("failed_items", 0),
            "conflicts": result.get("conflicts", []),
            "remaining_in_queue": result.get("remaining", 0),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


# --- GET /api/sync/status ---
@router.get("/status")
def get_sync_status():
    """
    Returns the current synchronization status.
    """
    try:
        return {
            "pending_sync_count": sync_queue.size(),
            "is_online": True,  # TODO: add actual connectivity check
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")


# --- POST /api/sync/batch ---
@router.post("/batch")
def batch_sync(db: Session = Depends(get_db)):
    """
    Perform a batch sync operation (used for server-side batch processing).
    """
    try:
        result = process_sync_once(db)
        return {
            "message": "Batch sync complete",
            "synced_items": result.get("synced_items", 0),
            "failed_items": result.get("failed_items", 0),
            "conflicts": result.get("conflicts", []),
            "remaining_in_queue": result.get("remaining", 0),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch sync failed: {str(e)}")


# --- GET /api/sync/health ---
@router.get("/health")
def health_check():
    """
    Simple health check endpoint for monitoring.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
