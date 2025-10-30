import os
from datetime import datetime, timezone
from typing import List, Dict, Any

from ..services.local_queue import sync_queue
from ..utils import parse_iso, now_iso
from ..models import Task
from sqlalchemy.orm import Session

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
RETRY_MAX = int(os.getenv("RETRY_MAX", "3"))

def _iso_to_dt(iso_str: str):
    if not iso_str:
        return None
    dt = parse_iso(iso_str)
    # ensure tz-aware (dateutil gives tz-aware if timezone present)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def process_sync_once(db: Session) -> Dict[str, Any]:
    """
    Process up to BATCH_SIZE items from local queue and apply to DB with LWW conflict resolution.
    Returns a summary dict with synced_items, failed_items, and conflict log.
    """
    batch = sync_queue.get_batch(limit=BATCH_SIZE)
    if not batch:
        return {"synced_items": 0, "failed_items": 0, "conflicts": [], "remaining": sync_queue.size()}

    processed = []
    failed = []
    conflicts = []

    for item in batch:
        task_id = item.get("task_id")
        operation = item.get("operation")
        data = item.get("data", {})
        queued_at = item.get("queued_at")
        retry_count = item.get("retry_count", 0)

        client_updated_at = _iso_to_dt(data.get("updated_at")) or _iso_to_dt(queued_at)
        # fetch existing task from DB
        existing = db.query(Task).filter(Task.id == task_id).first()

        try:
            # Conflict detection LWW: if existing.updated_at > client_updated_at => server newer => skip
            if existing:
                existing_updated = existing.updated_at
                # convert to timezone-aware if needed
                if existing_updated and existing_updated.tzinfo is None:
                    # assume DB times are naive; treat as UTC
                    existing_updated = existing_updated.replace(tzinfo=timezone.utc)

                # if existing exists and is newer than client's operation => conflict resolved by server
                if existing_updated and client_updated_at and existing_updated > client_updated_at:
                    conflicts.append({
                        "task_id": task_id,
                        "operation": operation,
                        "reason": "server newer (LWW)",
                        "server_updated_at": existing_updated.isoformat(),
                        "client_updated_at": client_updated_at.isoformat() if client_updated_at else None,
                        "timestamp": now_iso()
                    })
                    # skip applying this item (local operation lost due to LWW)
                    processed.append(item)
                    continue

            # Apply operation
            if operation == "create":
                if not existing:
                    # create new DB row with client's data + preserved id
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
                    # existing exists, do an update only if client is newer (already checked above)
                    existing.title = data.get("title", existing.title)
                    existing.description = data.get("description", existing.description)
                    existing.completed = bool(data.get("completed", existing.completed))
                    existing.updated_at = client_updated_at or datetime.now(timezone.utc)
                    existing.sync_status = "synced"

            elif operation == "update":
                if existing:
                    existing.title = data.get("title", existing.title)
                    existing.description = data.get("description", existing.description)
                    existing.completed = bool(data.get("completed", existing.completed))
                    existing.updated_at = client_updated_at or datetime.now(timezone.utc)
                    existing.sync_status = "synced"
                else:
                    # if update received but task missing, create it (assume create)
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
                    existing.is_deleted = True
                    existing.updated_at = client_updated_at or datetime.now(timezone.utc)
                    existing.sync_status = "synced"
                else:
                    # nothing to delete; mark as processed
                    pass

            else:
                # unknown operation
                failed.append({"item": item, "error": "unknown operation"})
                continue

            processed.append(item)

        except Exception as e:
            # on error, mark item failed and maybe retry later
            item["retry_count"] = retry_count + 1
            failed.append({"item": item, "error": str(e)})

    # commit DB changes and then remove processed items from queue
    try:
        db.commit()
    except Exception as e:
        # if commit fails, don't remove items; just return error
        return {"synced_items": 0, "failed_items": len(batch), "conflicts": conflicts, "error": str(e), "remaining": sync_queue.size()}

    # remove processed items (whether they were conflicts or successful)
    sync_queue.remove_items(processed)

    # For failed items: increment retry_count and re-save (we left them in place in this implementation)
    for f in failed:
        itm = f["item"]
        # increment in queue by searching and updating the object; simpler to re-add with updated retry_count
        # here we just increase retry_count inline if the queue item object exists (we rely on object identity not available),
        # so we'll leave failed items in queue and they will be retried on next sync.
        pass

    # For items that exceeded RETRY_MAX, we could remove and mark tasks as 'error' in DB (left as extension)
    return {
        "synced_items": len(processed),
        "failed_items": len(failed),
        "conflicts": conflicts,
        "remaining": sync_queue.size()
    }
