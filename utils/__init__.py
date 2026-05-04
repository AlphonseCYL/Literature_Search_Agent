from .handle_query import handle_query
from .json_Unicode_2dict import normalize_json_to_dict
import os

__all__ = ["handle_query", "normalize_json_to_dict"]

def singleton(cls, *args, **kw):
    instances = {}

    def _singleton():
        key = str(cls) + str(os.getpid())
        if key not in instances:
            instances[key] = cls(*args, **kw)
        return instances[key]

    return _singleton