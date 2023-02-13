from decimal import Decimal
from typing import Any


def force_int(val: Any, default: int = 0) -> int:
    # noinspection PyBroadException
    try:
        return int(val)
    except Exception:
        return default


def force_decimal(val: Any, default: Any = Decimal('0')) -> Decimal:
    # noinspection PyBroadException
    try:
        return Decimal(val)
    except Exception:
        return default
