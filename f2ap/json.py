import json

from datetime import datetime
from typing import Any
from uuid import UUID


class ActivityJsonEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()

        if isinstance(o, UUID):
            return str(o)

        return o
