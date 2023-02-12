from typing import Any


def force_int(val: Any, default: Any = 0) -> int:
    # noinspection PyBroadException
    try:
        return int(val)
    except Exception:
        return default
