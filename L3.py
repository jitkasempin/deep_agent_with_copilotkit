#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path


LESSON = 3
PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STOP_REQUESTED = threading.Event()


def _request_stop(_signum: int, _frame: object) -> None:
    STOP_REQUESTED.set()


def _start_frontend(frontend_port: int, runtime_port: int) -> subprocess.Popen[str]:
    import helper

    if not (FRONTEND_DIR / "node_modules").is_dir():
        helper.install_frontend(frontend_dir=FRONTEND_DIR.name)

    log_path = FRONTEND_DIR / "dev-logs.txt"
    log_file = log_path.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(frontend_port)],
            cwd=FRONTEND_DIR,
            env=helper._node_env(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
    finally:
        log_file.close()

    try:
        print(f"Starting frontend on port {frontend_port} ...")
        frontend_ready = helper.wait_for_port(frontend_port, timeout=30)
        runtime_ready = helper.wait_for_port(runtime_port, timeout=30)

        if process.poll() is not None:
            raise RuntimeError(
                f"Frontend exited with code {process.returncode}. See {log_path}."
            )
        if not frontend_ready or not runtime_ready:
            missing = [
                str(port)
                for port, ready in (
                    (frontend_port, frontend_ready),
                    (runtime_port, runtime_ready),
                )
                if not ready
            ]
            raise RuntimeError(
                f"Frontend services did not open port(s) {', '.join(missing)}. "
                f"See {log_path}."
            )
    except BaseException:
        _stop_frontend(process)
        raise

    print(f"✓ App running at {helper.get_app_url(frontend_port)}")
    print(f"Read the logs: {log_path}")
    return process


def _stop_frontend(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except ProcessLookupError:
        return
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def _stop_backend(backend_port: int) -> None:
    import helper

    server = helper._servers.pop(backend_port, None)
    if server is not None:
        server.should_exit = True


def main() -> int:
    os.chdir(PROJECT_ROOT)

    import helper
    from backend.server import start_backend

    ports = helper.get_ports(LESSON)
    occupied = [port for port in ports.values() if helper.is_port_in_use(port)]
    if occupied:
        joined = ", ".join(str(port) for port in occupied)
        raise RuntimeError(
            f"Cannot start Lesson {LESSON}: port(s) {joined} are already in use."
        )

    helper.load_api_keys()
    if not os.environ.get("GOOGLE_API_KEY"):
        raise RuntimeError(
            "GOOGLE_API_KEY is required by the Lesson 3 Gemini agent. "
            "Add it to the project .env file or export it in the environment."
        )

    frontend_process: subprocess.Popen[str] | None = None
    try:
        start_backend(port=ports["backend"])
        if not helper.is_port_in_use(ports["backend"]):
            raise RuntimeError("The agent backend failed to start.")

        frontend_process = _start_frontend(
            frontend_port=ports["frontend"],
            runtime_port=ports["runtime"],
        )

        print("\nLesson 3 is ready:")
        print(f"  Frontend:        {helper.get_app_url(ports['frontend'])}")
        print(f"  Copilot runtime: http://localhost:{ports['runtime']}")
        print(f"  Agent backend:   http://localhost:{ports['backend']}")
        print("\nPress Ctrl+C to stop all services.")

        while not STOP_REQUESTED.wait(1):
            stopped = [
                str(port)
                for port in ports.values()
                if not helper.is_port_in_use(port)
            ]
            if stopped:
                raise RuntimeError(
                    f"Lesson 3 service(s) on port(s) {', '.join(stopped)} stopped."
                )
    finally:
        print("\nStopping Lesson 3 ...")
        _stop_frontend(frontend_process)
        _stop_backend(ports["backend"])
        time.sleep(0.5)
        print("✓ Lesson 3 stopped")

    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)
    raise SystemExit(main())
