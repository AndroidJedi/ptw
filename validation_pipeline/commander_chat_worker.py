"""Kill a local Commander process group if its owning API disappears.

The API owns the only write end of an inherited pipe. EOF also covers SIGKILL
and crashes, where API lifespan cleanup cannot run. No credentials or tool
output travel through this pipe.
"""

import os
import signal
import subprocess
import sys
import threading


def main() -> int:
    parent_fd = int(sys.argv[1])

    def watch_parent():
        try:
            while os.read(parent_fd, 1):
                pass
        finally:
            os.killpg(os.getpgrp(), signal.SIGKILL)

    threading.Thread(target=watch_parent, daemon=True).start()
    if "app-server" in sys.argv[2:]:
        return subprocess.call(sys.argv[2:], stdin=sys.stdin)
    process = subprocess.Popen(sys.argv[2:], stdin=subprocess.PIPE, text=True)
    process.communicate(input=sys.stdin.read())
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
