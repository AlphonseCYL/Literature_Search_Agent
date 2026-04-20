import json
import re
from typing import Any, Dict



def normalize_json_to_dict(payload: Any) -> Dict[str, Any]:
    """
    Normalize payload to dict and decode escaped unicode text into readable chars.

    Supported input:
    - dict
    - JSON string
    - double-serialized JSON string
    """
    data: Any = payload

    for _ in range(2):
        if isinstance(data, str):
            text = data.strip()
            if not text:
                raise ValueError("payload is empty")
            data = json.loads(text)
        else:
            break

    if not isinstance(data, dict):
        raise TypeError(
            f"normalize_json_to_dict expects dict/JSON-string, got: {type(payload).__name__}"
        )

    return data
