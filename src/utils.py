from datetime import datetime, timezone
from dateutil import parser

# Returns the current UTC time as a readable ISO 8601 string
def now_iso():
    return datetime.now(timezone.utc).isoformat()

# Turns an ISO 8601 timestamp string back into a datetime object
def parse_iso(ts: str):
    if not ts:
        return None
    return parser.isoparse(ts)
