import os
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from ..models import Task, SyncQueue
from ..services.local_queue import sync_queue
from ..utils import parse_iso, now_iso


BATCH_SIZE = int(os.getenv("SYNC_BATCH_SIZE", "50"))
RETRY_MAX = int(os.getenv("SYNC_RETRY_MAX", "3"))
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")


class SyncService:
    """
    Handles offline synchronization between local SQLite DB and remote server.
    Mirrors logic of the Node.js SyncService class.
    """

    def __init__(self, db: Session, task_service):
        self.db = db
        self.task_service = task_service
        self.api_url = API_BASE_URL

    # ---------------------------------------------------
    # 1️⃣ Main Sync Orchestration
    # ---------------------------------------------------
    def sync(self) -> Dict[str, Any]:
        """
        1. Collect all unsynced queue items
        2. Group by batch size
        3. Process each batch
        4. Handle errors
        5. Return sync summary
        """
        queue_items = self.db.query(SyncQueue).filter(SyncQueue.retry_count < RETRY_MAX).all()

        if not queue_items:
            return {"synced": 0, "failed": 0, "message": "No pending items"}

        total_synced, total_failed = 0, 0
        for i in range(0, len(queue_items), BATCH_SIZE):
            batch = queue_items[i : i + BATCH_SIZE]
            result = self._process_batch(batch)
            total_synced += result.get("synced", 0)
            total_failed += result.get("failed", 0)

        return {"synced": total_synced, "failed": total_failed, "timestamp": now_iso()}

    # ---------------------------------------------------
    # 2️⃣ Add item to sync queue
    # ---------------------------------------------------
    def add_to_sync_queue(self, task_id: str, operation: str, data: Dict[str, Any]) -> None:
        """
        Store a pending sync operation locally (create, update, or delete).
        """
        queue_item = SyncQueue(
            task_id=task_id,
            operation=operation,
            data=data,
            retry_count=0,
            last_error=None,
            queued_at=datetime.utcnow(),
        )
        self.db.add(queue_item)
        self.db.commit()

    # ---------------------------------------------------
    # 3️⃣ Process one batch
    # ---------------------------------------------------
    def _process_batch(self, items: List[SyncQueue]) -> Dict[str, Any]:
        """
        Try syncing a batch of queue items to the remote server.
        """
        synced, failed = 0, 0

        for item in items:
            try:
                payload = {
                    "task_id": item.task_id,
                    "operation": item.operation,
                    "data": item.data,
                }

                # Simulate sending to the remote API
                # (In production: POST /api/sync/batch or similar endpoint)
                response = requests.post(
                    f"{self.api_url}/tasks/sync",
                    json=payload,
                    timeout=5,
                )

                if response.status_code == 200:
                    server_data = response.json()
                    self._update_sync_status(item.task_id, "synced", server_data)
                    self.db.delete(item)
                    self.db.commit()
                    synced += 1
                else:
                    raise Exception(f"Server error: {response.status_code}")

            except Exception as e:
                self._handle_sync_error(item, e)
                failed += 1

        return {"synced": synced, "failed": failed}

    # ---------------------------------------------------
    # 4️⃣ Conflict Resolution (Last Write Wins)
    # ---------------------------------------------------
    def _resolve_conflict(self, local_task: Task, server_task: Dict[str, Any]) -> Task:
        """
        Keep whichever version was updated most recently (last-write-wins).
        """
        server_updated = self._iso_to_dt(server_task.get("updated_at"))
        if local_task.updated_at > server_updated:
            return local_task
        else:
            local_task.title = server_task.get("title", local_task.title)
            local_task.description = server_task.get("description", local_task.description)
            local_task.completed = server_task.get("completed", local_task.completed)
            local_task.updated_at = server_updated
            return local_task

    # ---------------------------------------------------
    # 5️⃣ Update Sync Status
    # ---------------------------------------------------
    def _update_sync_status(self, task_id: str, status: str, server_data: Optional[Dict[str, Any]] = None):
        """
        Update local DB task status after successful sync.
        """
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        task.sync_status = status
        task.last_synced_at = datetime.utcnow()
        if server_data:
            task.server_id = server_data.get("id", task.server_id)
            task.updated_at = self._iso_to_dt(server_data.get("updated_at")) or datetime.utcnow()
        self.db.commit()

    # ---------------------------------------------------
    # 6️⃣ Handle Sync Errors
    # ---------------------------------------------------
    def _handle_sync_error(self, item: SyncQueue, error: Exception):
        """
        Handle failed syncs: increment retry count, save error message, etc.
        """
        item.retry_count += 1
        item.last_error = str(error)
        item.last_attempt_at = datetime.utcnow()
        if item.retry_count >= RETRY_MAX:
            item.last_error = f"Permanent failure after {item.retry_count} retries: {error}"
        self.db.commit()

    # ---------------------------------------------------
    # 7️⃣ Check connectivity
    # ---------------------------------------------------
    def check_connectivity(self) -> bool:
        try:
            res = requests.get(f"{self.api_url}/health", timeout=3)
            return res.status_code == 200
        except Exception:
            return False

    # ---------------------------------------------------
    # 🔧 Utility
    # ---------------------------------------------------
    @staticmethod
    def _iso_to_dt(iso_str: Optional[str]):
        if not iso_str:
            return None
        try:
            dt = parse_iso(iso_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

def process_sync_once(db: Session):
    """
    Wrapper kept for backward compatibility.
    Calls the main sync logic from SyncService.
    """
    service = SyncService(db)
    return service.sync_pending_tasks()