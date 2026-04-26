import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
WORKERS = (
    ("remote", ROOT_DIR / "remote_worker.py"),
    ("metadata", ROOT_DIR / "metadata_worker.py"),
)


class WorkerProcess:
    def __init__(self, name: str, script_path: Path, env: dict[str, str]):
        self.name = name
        self.script_path = script_path
        self.env = env
        self.process: subprocess.Popen | None = None
        self.output_threads: list[threading.Thread] = []

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            return

        self.process = subprocess.Popen(
            [sys.executable, str(self.script_path)],
            cwd=str(ROOT_DIR),
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._start_output_thread(self.process.stdout, "stdout")
        self._start_output_thread(self.process.stderr, "stderr")
        print(f"[manager] worker '{self.name}' iniciado com pid={self.process.pid}")

    def _start_output_thread(self, stream, stream_name: str) -> None:
        if stream is None:
            return

        def _pump() -> None:
            for line in iter(stream.readline, ""):
                msg = line.rstrip()
                if msg:
                    print(f"[{self.name}:{stream_name}] {msg}")

        thread = threading.Thread(target=_pump, daemon=True)
        thread.start()
        self.output_threads.append(thread)

    def terminate(self, timeout: float = 10.0) -> None:
        if not self.process or self.process.poll() is not None:
            return

        print(f"[manager] encerrando worker '{self.name}' (pid={self.process.pid})...")
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"[manager] worker '{self.name}' não encerrou a tempo; forçando kill.")
            self.process.kill()
            self.process.wait(timeout=5.0)

    def returncode(self) -> int | None:
        if not self.process:
            return None
        return self.process.poll()


def build_worker_env() -> dict[str, str]:
    return dict(os.environ)


def main() -> int:
    env = build_worker_env()

    workers = [WorkerProcess(name, script, env) for name, script in WORKERS]
    stopping = False

    def _shutdown(signame: str) -> None:
        nonlocal stopping
        if stopping:
            return

        stopping = True
        print(f"\n[manager] sinal {signame} recebido. Encerrando workers...")
        for worker in workers:
            worker.terminate()

    def _handle_sigint(sig, frame):
        _shutdown("SIGINT")

    def _handle_sigterm(sig, frame):
        _shutdown("SIGTERM")

    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigterm)

    for worker in workers:
        worker.start()

    exit_code = 0
    try:
        while not stopping:
            for worker in workers:
                code = worker.returncode()
                if code is None:
                    continue
                if code != 0:
                    print(f"[manager] worker '{worker.name}' finalizou com erro (exit_code={code}).")
                    exit_code = 1
                else:
                    print(f"[manager] worker '{worker.name}' finalizou normalmente (exit_code=0).")
                _shutdown("worker_exit")
                break
            time.sleep(0.5)
    finally:
        for worker in workers:
            worker.terminate()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
