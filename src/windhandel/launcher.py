"""
Entry point: start the API subprocess, then run the TUI.
The API is a child of this process and is torn down when the TUI exits.
"""

from __future__ import annotations

import subprocess
import sys
import time

from windhandel.config import (
    API_HOST,
    API_PORT,
    LOG_LEVEL,
    configure_logging,
    log_path,
)

STARTUP_GRACE_SECONDS = 2.0
POLL_INTERVAL = 0.1


def _tail(path, lines: int = 25) -> str:
    try:
        return "".join(path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)[-lines:])
    except OSError:
        return "(no output captured)"


def main() -> None:
    tui_log = configure_logging("tui")
    api_log = log_path("api")

    # Line-buffered append so a crash still flushes what it managed to write.
    with open(api_log, "a", encoding="utf-8", buffering=1) as api_out:
        api_out.write(f"\n--- starting api on {API_HOST}:{API_PORT} ---\n")
        api_process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "windhandel.api:app",
                "--host", API_HOST,
                "--port", str(API_PORT),
                "--log-level", LOG_LEVEL.lower(),
            ],
            stdout=api_out,
            stderr=subprocess.STDOUT,
        )

        deadline = time.monotonic() + STARTUP_GRACE_SECONDS
        while time.monotonic() < deadline:
            if api_process.poll() is not None:
                # Safe to print: the TUI has not started
                print(
                    f"API failed to start (exit code {api_process.returncode}).\n"
                    f"Log: {api_log}\n\n{_tail(api_log)}",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            time.sleep(POLL_INTERVAL)

        from windhandel.tui import WindhandelApp

        try:
            WindhandelApp().run()
        finally:
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_process.kill()
                api_process.wait()

    print(f"Logs: {tui_log}  {api_log}", file=sys.stderr)


if __name__ == "__main__":
    main()