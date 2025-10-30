from datetime import datetime, timezone
from dateutil import parser

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def parse_iso(ts: str):
    """
   The parser is used for converting the timestamp into ISO 8601 format.
   :param ts:
   :return:
    """
    if not ts:
        return None
    dt = parser.isoparse(ts)
    return dt
