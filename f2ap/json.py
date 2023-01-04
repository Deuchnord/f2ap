import json

from datetime import datetime
from typing import Any


class ActivityJsonEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()

        return o
