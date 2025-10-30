import json
import os
from datetime import datetime
from typing import List, Dict, Any
import threading

from ..utils import now_iso

class LocalQueue:
    """
    This class handles a local queue that stores operations (like creating, updating,
    or deleting tasks) when the system is offline.

    The idea is simple:
    - When the system can’t reach the main database (offline mode), all changes are saved here.
    - When the system goes back online, the queued operations are sent to the database
      to bring everything back in sync.
    """
    def __init__(self, file_path: str = "./sync_queue.json"):
        # File path where the queue data will be stored locally in JSON format
        self.file_path = file_path
        # A lock to make sure multiple threads don’t access or modify the queue at the same time
        self._lock = threading.Lock()
        # The actual queue – a list of operations waiting to be synced
        self.queue: List[Dict[str, Any]] = []
        # Load any previously saved queue data from the file
        self._load()

    def _load(self):
        # Reads existing queue data from the file if it exists
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    data = json.load(f)
                    # Only load if the data is a valid list
                    if isinstance(data, list):
                        self.queue = data
            except Exception:
                # If there’s an issue reading or parsing the file (e.g., corruption),
                # start with an empty queue
                self.queue = []

    def _save(self):
        # Saves the queue to the file safely (thread-safe and atomic write)
        with self._lock:
            tmp = self.file_path + ".tmp"  # Write to a temporary file first to avoid corruption
            with open(tmp, "w") as f:
                json.dump(self.queue, f, indent=2, default=str)
            # Once writing succeeds, replace the old file with the new one
            os.replace(tmp, self.file_path)

    def add(self, task_id: str, operation: str, data: dict):
        """
        Adds a new operation to the queue.

        Arguments:
        - `task_id`: The ID of the task being changed.
        - `operation`: The type of change ('create', 'update', or 'delete').
        - `data`: The full details of the change, including an `updated_at` timestamp
                  to determine which change is the latest during synchronization.
        """
        item = {
            "task_id": task_id,
            "operation": operation,
            "data": data,
            "retry_count": 0,       # Tracks how many times syncing this item has failed
            "queued_at": now_iso()  # When the item was added to the queue
        }
        # Add the new operation to the queue and save it
        with self._lock:
            self.queue.append(item)
            self._save()

    def get_batch(self, limit: int = 50):
        # Returns a subset of queued operations (up to `limit`) to process in one sync batch
        with self._lock:
            return list(self.queue[:limit])

    def remove_items(self, items):
        # Removes specific items from the queue once they’ve been successfully synced
        with self._lock:
            s = set()
            # Create unique identifiers for each item so we can compare them accurately
            for it in items:
                s.add((it.get("task_id"), it.get("operation"), it.get("data", {}).get("updated_at"), it.get("queued_at")))
            newq = []
            # Keep only the items that are still pending (not in the removal list)
            for q in self.queue:
                key = (q.get("task_id"), q.get("operation"), q.get("data", {}).get("updated_at"), q.get("queued_at"))
                if key not in s:
                    newq.append(q)
            self.queue = newq
            self._save()

    def size(self):
        # Returns the total number of operations currently in the queue
        with self._lock:
            return len(self.queue)

    def increment_retry(self, item):
        # If syncing a specific operation fails, increase its retry count
        # so the system can keep track of how many times it’s been attempted
        with self._lock:
            for q in self.queue:
                if q is item:  # Match the exact queue item
                    q["retry_count"] = q.get("retry_count", 0) + 1
                    break
            self._save()

# Create a single shared instance of LocalQueue (a singleton)
# This means all parts of the system use the same queue instance
# You can change the storage file path using the QUEUE_FILE environment variable if needed
sync_queue = LocalQueue(file_path=os.getenv("QUEUE_FILE", "./sync_queue.json"))
