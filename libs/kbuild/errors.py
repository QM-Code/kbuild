import sys
from collections.abc import Callable
from typing import NoReturn


def emit_error(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)


def die(message: str, *, code: int = 2) -> NoReturn:
    emit_error(message)
    raise SystemExit(code)


def die_with_usage(message: str, usage: Callable[[int], None], *, code: int = 1) -> NoReturn:
    emit_error(message)
    usage(code)
    raise SystemExit(code)
