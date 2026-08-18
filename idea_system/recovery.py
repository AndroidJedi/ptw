from __future__ import annotations
import time


class RecoveryExhausted(RuntimeError): pass


def recover(step, action, notify=lambda _: None, delays=(0, 0)):
    try:
        return action(1)
    except Exception as first:
        notify(f"🟡 Recoverable error\n{step}\nCause: {type(first).__name__}\n\nRecovery 1/2")
    for recovery in (1, 2):
        if delays[recovery-1]: time.sleep(delays[recovery-1])
        try:
            value = action(recovery + 1)
            notify(f"🟢 Recovery succeeded\n{step}\nAttempt {recovery}/2\n\nExecution continues automatically.")
            return value
        except Exception as error:
            if recovery == 1:
                notify(f"🟠 Recovery attempt 1 failed\n{step}\nTrying 2/2 automatically.")
            else:
                notify(f"🔴 Automatic recovery failed\n{step}\nAttempts: 2/2\n\nAutomatic progression stopped safely.\nCompleted data preserved.")
                raise RecoveryExhausted(str(error)) from error
