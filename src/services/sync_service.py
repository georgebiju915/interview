import os
from datetime import datetime, timezone
from typing import List, Dict, Any

from ..services.local_queue import sync_queue
from ..utils import parse_iso, now_iso
from ..models import Task, SyncQueue
from sqlalchemy.orm import Session

# Settings that control how the sync process works
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))  # How many items we try to sync at once
RETRY_MAX = int(os.getenv("RETRY_MAX", "3"))  # How many times we retry a failed sync
MAX_RETRIES = 3  # A hard cap on retries


def sync_pending_tasks(db: Session):
    """
    Go through any queued sync tasks stored in the database (not the local file)
    and try to send them to the remote server.
    """
    # Get all pending sync items that haven’t reached their retry limit
    queue_items = db.query(SyncQueue).filter(SyncQueue.retry_count < MAX_RETRIES).all()
    synced_count, failed_count = 0, 0

    for item in queue_items:
        task_data = item.data
        try:
            # In a real-world scenario, this would make an API call to sync the data
            print(f"Syncing {item.operation} for task {item.task_id}")

            # Find the matching task in our local DB
            task = db.query(Task).filter(Task.id == item.task_id).first()
            if not task:
                continue  # Skip if the task doesn’t exist locally

            # If the local version is newer, don’t overwrite it
            if task.updated_at > datetime.utcnow():
                continue

            # Mark the task as successfully synced
            task.sync_status = "synced"
            task.last_synced_at = datetime.utcnow()

            # Remove this item from the queue since it’s done
            db.delete(item)
            db.commit()
            synced_count += 1

        except Exception as e:
            # If something goes wrong, log the error and increase retry count
            item.retry_count += 1
            item.last_error = str(e)
            db.commit()
            failed_count += 1

    # Return a quick summary of how many succeeded and failed
    return {"synced": synced_count, "failed": failed_count}


def _iso_to_dt(iso_str: str):
    """
    Turns an ISO 8601 timestamp (e.g., '2025-10-30T12:34:56Z')
    into a timezone-aware Python datetime object.
    """
    if not iso_str:
        return None
    dt = parse_iso(iso_str)
    # If the timestamp doesn’t include timezone info, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def process_sync_once(db: Session) -> Dict[str, Any]:
    """
    Process one batch of operations from the local offline queue (sync_queue.json).
    Uses a 'last write wins' rule to handle conflicts — meaning whichever change
    was made most recently (by timestamp) is kept.

    Returns a summary with:
      - How many items were synced
      - How many failed
      - Any detected conflicts
      - How many items are still waiting in the queue
    """
    # Get a small chunk of queued actions to process
    batch = sync_queue.get_batch(limit=BATCH_SIZE)
    if not batch:
        return {"synced_items": 0, "failed_items": 0, "conflicts": [], "remaining": sync_queue.size()}

    processed = []  # Everything that got handled (successfully or skipped)
    failed = []  # Things that failed and will need to retry later
    conflicts = []  # Items we skipped because of newer data on the server

    for item in batch:
        task_id = item.get("task_id")
        operation = item.get("operation")
        data = item.get("data", {})
        queued_at = item.get("queued_at")
        retry_count = item.get("retry_count", 0)

        # Figure out when this change was last made on the client
        client_updated_at = _iso_to_dt(data.get("updated_at")) or _iso_to_dt(queued_at)

        # Look for the same task in the database
        existing = db.query(Task).filter(Task.id == task_id).first()

        try:
            # --- Check for conflicts (Last Write Wins logic) ---
            if existing:
                existing_updated = existing.updated_at
                if existing_updated and existing_updated.tzinfo is None:
                    existing_updated = existing_updated.replace(tzinfo=timezone.utc)

                # If the server version is newer, skip this one and log the conflict
                if existing_updated and client_updated_at and existing_updated > client_updated_at:
                    conflicts.append({
                        "task_id": task_id,
                        "operation": operation,
                        "reason": "server has newer data (LWW)",
                        "server_updated_at": existing_updated.isoformat(),
                        "client_updated_at": client_updated_at.isoformat() if client_updated_at else None,
                        "timestamp": now_iso()
                    })
                    processed.append(item)
                    continue

            # --- Apply the operation to the local database ---
            if operation == "create":
                if not existing:
                    # The task doesn’t exist, so create it
                    new_task = Task(
                        id=task_id,
                        title=data.get("title", "") or "Untitled",
                        description=data.get("description"),
                        completed=bool(data.get("completed", False)),
                        created_at=client_updated_at or datetime.now(timezone.utc),
                        updated_at=client_updated_at or datetime.now(timezone.utc),
                        is_deleted=False,
                        sync_status="synced",
                    )
                    db.add(new_task)
                else:
                    # The task already exists — just update it if needed
                    existing.title = data.get("title", existing.title)
                    existing.description = data.get("description", existing.description)
                    existing.completed = bool(data.get("completed", existing.completed))
                    existing.updated_at = client_updated_at or datetime.now(timezone.utc)
                    existing.sync_status = "synced"

            elif operation == "update":
                if existing:
                    # Update the task in place
                    existing.title = data.get("title", existing.title)
                    existing.description = data.get("description", existing.description)
                    existing.completed = bool(data.get("completed", existing.completed))
                    existing.updated_at = client_updated_at or datetime.now(timezone.utc)
                    existing.sync_status = "synced"
                else:
                    # If we get an update but the task doesn’t exist, just create it
                    new_task = Task(
                        id=task_id,
                        title=data.get("title", "") or "Untitled",
                        description=data.get("description"),
                        completed=bool(data.get("completed", False)),
                        created_at=client_updated_at or datetime.now(timezone.utc),
                        updated_at=client_updated_at or datetime.now(timezone.utc),
                        is_deleted=False,
                        sync_status="synced",
                    )
                    db.add(new_task)

            elif operation == "delete":
                if existing:
                    # Soft-delete the task instead of removing it completely
                    existing.is_deleted = True
                    existing.updated_at = client_updated_at or datetime.now(timezone.utc)
                    existing.sync_status = "synced"
                else:
                    # If it’s already gone, there’s nothing to delete
                    pass

            else:
                # If we got an unknown operation, skip it
                failed.append({"item": item, "error": "unknown operation"})
                continue

            # Mark as processed successfully
            processed.append(item)

        except Exception as e:
            # If anything breaks, record the failure and bump the retry count
            item["retry_count"] = retry_count + 1
            failed.append({"item": item, "error": str(e)})

    # Try to save all changes to the database
    try:
        db.commit()
    except Exception as e:
        # If commit fails, keep everything in the queue for next time
        return {
            "synced_items": 0,
            "failed_items": len(batch),
            "conflicts": conflicts,
            "error": str(e),
            "remaining": sync_queue.size()
        }

    # Remove everything that was successfully handled or skipped from the queue
    sync_queue.remove_items(processed)

    # Failed items stay in the queue — they’ll be retried next time
    # (In the future, we might add smarter retry handling here.)

    return {
        "synced_items": len(processed),
        "failed_items": len(failed),
        "conflicts": conflicts,
        "remaining": sync_queue.size()
    }
