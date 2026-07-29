import subprocess
import sys

from windhandel.tui import WindhandelApp


def main() -> None:
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "windhandel.api:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        WindhandelApp().run()
    finally:
        api_process.terminate()
        api_process.wait()


if __name__ == "__main__":
    main()