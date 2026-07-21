"""Run an isolated, full-function local preview without production release gates.

The preview uses a dedicated SQLite database and explicit development-only auth.
It does not read or mutate the normal Docker Compose database.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
WEB_DIR = ROOT / "apps" / "web"
STATE_DIR = ROOT / ".test-preview"
API_PORT = 58000
WEB_PORT = 55173


def wait_for(url: str, process: subprocess.Popen[bytes], timeout: float = 45) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Preview process exited with code {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for {url}")


def http_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.25)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def should_start(reset: bool) -> bool:
    api_ready = http_ready(f"http://127.0.0.1:{API_PORT}/health")
    web_ready = http_ready(f"http://127.0.0.1:{WEB_PORT}/app")
    if api_ready and web_ready:
        if reset:
            raise RuntimeError("Preview is already running. Stop it with Ctrl+C before using --reset.")
        return False
    occupied = [str(port) for port in (API_PORT, WEB_PORT) if port_in_use(port)]
    if occupied:
        raise RuntimeError(f"Preview cannot start because local port(s) {', '.join(occupied)} are already in use.")
    return True


def reset_database() -> None:
    try:
        for suffix in ("", "-shm", "-wal"):
            (STATE_DIR / f"preview.db{suffix}").unlink(missing_ok=True)
    except PermissionError as exc:
        raise RuntimeError("Preview database is still in use. Stop the previous preview and retry --reset.") from exc


def open_preview(no_open: bool) -> None:
    if not no_open:
        webbrowser.open(f"http://127.0.0.1:{WEB_PORT}/app")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the isolated local Luma product preview.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete only .test-preview/preview.db before starting, then show onboarding from the beginning",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="do not open the ready preview in the default browser",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    STATE_DIR.mkdir(exist_ok=True)
    try:
        if not should_start(args.reset):
            open_preview(args.no_open)
            print(f"Luma test preview is already running: http://127.0.0.1:{WEB_PORT}/app", flush=True)
            return 0
        if args.reset:
            reset_database()
    except RuntimeError as exc:
        print(f"Cannot start Luma test preview: {exc}", file=sys.stderr, flush=True)
        return 2
    database = (STATE_DIR / "preview.db").resolve().as_posix()
    api_env = os.environ.copy()
    api_env.update(
        DATABASE_URL=f"sqlite:///{database}",
        REDIS_URL="redis://127.0.0.1:56379/0",
        APP_ENVIRONMENT="development",
        PUBLIC_LAUNCH_ENABLED="true",
        DEVELOPMENT_AUTH_ENABLED="true",
        SESSION_SECRET=secrets.token_urlsafe(48),
        CORS_ORIGINS=f"http://127.0.0.1:{WEB_PORT}",
        TELEGRAM_WEBAPP_URL=f"http://127.0.0.1:{WEB_PORT}",
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env=api_env,
        check=True,
    )

    web_env = os.environ.copy()
    web_env.update(
        VITE_API_URL=f"http://127.0.0.1:{API_PORT}/v1",
        VITE_TEST_PREVIEW="true",
    )
    npm = "npm.cmd" if os.name == "nt" else "npm"
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(API_PORT)],
        cwd=API_DIR,
        env=api_env,
    )
    web = subprocess.Popen(
        [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", str(WEB_PORT), "--strictPort"],
        cwd=WEB_DIR,
        env=web_env,
    )
    children = (web, api)

    def stop(*_: object) -> None:
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        wait_for(f"http://127.0.0.1:{API_PORT}/health", api)
        wait_for(f"http://127.0.0.1:{WEB_PORT}/app", web)
        open_preview(args.no_open)
        print(f"Luma test preview: http://127.0.0.1:{WEB_PORT}/app", flush=True)
        print("Press Ctrl+C to stop. Use --reset next time to start onboarding again.", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        return next((child.returncode or 1 for child in children if child.poll() is not None), 1)
    finally:
        stop()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    raise SystemExit(main())
