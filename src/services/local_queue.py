import json
import os
from datetime import datetime
from typing import List, Dict, Any
import threading

from ..utils import now_iso

class LocalQueue:
    """
    the class is used to maintain the local queue for the system whcen the system is offline
    and when the system is online the data in the queue will updatecto the database.
    """
    def __init__(self, file_path: str = "./sync_queue.json"):
        self.file_path = file_path
        self._lock = threading.Lock()
        self.queue: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.queue = data
            except Exception:
                self.queue = []

    def _save(self):
        with self._lock:
            tmp = self.file_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self.queue, f, indent=2, default=str)
            os.replace(tmp, self.file_path)

    def add(self, task_id: str, operation: str, data: dict):
        """
        Add an operation to the tail of the queue.
        `operation` is one of: 'create', 'update', 'delete'
        `data` is the operation payload (snapshot) and must include updated_at (ISO string) for LWW.
        """
        item = {
            "task_id": task_id,
            "operation": operation,
            "data": data,
            "retry_count": 0,
            "queued_at": now_iso()
        }
        with self._lock:
            self.queue.append(item)
            self._save()

    def get_batch(self, limit: int = 50):
        with self._lock:
            return list(self.queue[:limit])

    def remove_items(self, items):
        with self._lock:
            s = set()
            # create unique keys for removal to avoid issues with dict identity
            for it in items:
                s.add((it.get("task_id"), it.get("operation"), it.get("data", {}).get("updated_at"), it.get("queued_at")))
            newq = []
            for q in self.queue:
                key = (q.get("task_id"), q.get("operation"), q.get("data", {}).get("updated_at"), q.get("queued_at"))
                if key not in s:
                    newq.append(q)
            self.queue = newq
            self._save()

    def size(self):
        with self._lock:
            return len(self.queue)

    def increment_retry(self, item):
        with self._lock:
            # find the item by queue identity and increment retry_count
            for q in self.queue:
                if q is item:
                    q["retry_count"] = q.get("retry_count", 0) + 1
                    break
            self._save()

# Singleton instance; ensure you import sync_queue from this module
sync_queue = LocalQueue(file_path=os.getenv("QUEUE_FILE", "./sync_queue.json"))
