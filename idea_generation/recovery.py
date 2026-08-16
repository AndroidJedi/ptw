from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RecoveryExhausted(RuntimeError):
    pass


def recover(step: str, operation: Callable[[int], T], notify: Callable[[str], None]) -> T:
    """Initial call plus at most two automatic recovery attempts."""
    try:
        return operation(1)
    except Exception as first:
        notify(f"🟡 Recoverable error\n{step}\nCause: {type(first).__name__}\nRecovery 1/2")
    for recovery_number in (1, 2):
        try:
            result = operation(recovery_number + 1)
            notify(f"🟢 Recovery succeeded\n{step}\nAttempt {recovery_number}/2\nExecution continues automatically.")
            return result
        except Exception as error:
            if recovery_number == 1:
                notify(f"🟠 Recovery attempt 1 failed\n{step}\nTrying 2/2 automatically.")
                continue
            notify(f"🔴 Automatic recovery failed\n{step}\nAttempts: 2/2\nCompleted data preserved.")
            raise RecoveryExhausted(f"{step}: {type(error).__name__}") from error
