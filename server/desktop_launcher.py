from __future__ import annotations

import json
import logging
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk


APP_NAME = "Lip Reader Server"
HOST = "0.0.0.0"
PORT = 7100
LOCAL_HEALTH_URL = f"http://127.0.0.1:{PORT}/healthz"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    root = Path(os.getenv("LOCALAPPDATA", str(Path.home())))
    target = root / "Lip Reader Server"
    target.mkdir(parents=True, exist_ok=True)
    return target


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            continue
        os.environ.setdefault(key.strip(), value.strip())


def configure_runtime() -> None:
    root = app_dir()
    load_env_file(root / "config.env")
    resources = root / "resources"
    defaults = {
        "LIP_MODEL_BACKEND": "auto_avsr",
        "LIP_MODEL_LOAD_ON_STARTUP": "true",
        "LIP_DEVICE": "auto",
        "LIP_PRECISION": "auto",
        "LIP_ALLOW_CPU_FALLBACK": "true",
        "LIP_MAX_UPLOAD_BYTES": "104857600",
        "LIP_MAX_FRAMES": "1125",
        "LIP_MAX_QUEUED_JOBS": "8",
        "LIP_JOB_RETENTION_SECONDS": "1800",
        "LIP_MIN_FRAMES": "8",
        "LIP_TARGET_FPS": "25",
        "AUTO_AVSR_CHECKPOINT": str(
            resources / "models" / "epoch=13-step=55986-002.ckpt"
        ),
        "AUTO_AVSR_ROOT": str(resources / "auto_avsr"),
        "VSR_SPM_MODEL": str(
            resources / "vocabulary" / "vi_unigram_2000.model"
        ),
        "VSR_SPM_UNITS": str(
            resources
            / "vocabulary"
            / "vi_unigram_2000.auto_avsr_units.txt"
        ),
        "LIP_LLM_TIMEOUT_SECONDS": "90",
        "LIP_LLM_NUM_CTX": "2048",
        "LIP_LLM_MAX_OUTPUT_TOKENS": "320",
        "LIP_LLM_KEEP_ALIVE": "0",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def local_ipv4() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()


def read_health(timeout: float = 1.5) -> dict | None:
    try:
        with urllib.request.urlopen(LOCAL_HEALTH_URL, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("service") == "lip-reader-api":
            return payload
    except (OSError, ValueError, urllib.error.URLError):
        return None
    return None


def find_ollama() -> Path | None:
    candidates = [
        Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path(os.getenv("PROGRAMFILES", "")) / "Ollama" / "ollama.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    from shutil import which

    resolved = which("ollama")
    return Path(resolved) if resolved else None


def ensure_ollama_started(logger: logging.Logger) -> None:
    if os.getenv("LIP_LLM_PROVIDER", "").strip().lower() != "ollama":
        return
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/tags", timeout=1.5
        ):
            return
    except (OSError, urllib.error.URLError):
        pass
    executable = find_ollama()
    if executable is None:
        logger.warning(
            "Không tìm thấy Ollama. Visual-only vẫn hoạt động; "
            "có thể cài LLM lại từ bộ cài."
        )
        return
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            [str(executable), "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        logger.info("Đã khởi động Ollama.")
    except OSError as exc:
        logger.warning("Không thể khởi động Ollama: %s", exc)


class QueueLogHandler(logging.Handler):
    def __init__(self, target: queue.Queue[str]):
        super().__init__()
        self.target = target

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.target.put_nowait(self.format(record))
        except Exception:
            pass


class ServerWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("760x560")
        self.root.minsize(680, 500)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.server = None
        self.server_thread: threading.Thread | None = None
        self.owns_server = False
        self.closing = False
        self.lan_ip = local_ipv4()
        self.status_var = tk.StringVar(value="Đang kiểm tra hệ thống…")
        self.model_var = tk.StringVar(value="Model: đang nạp")
        self.llm_var = tk.StringVar(value="LLM: đang kiểm tra")
        self.address_var = tk.StringVar(
            value=f"http://{self.lan_ip}:{PORT}"
        )
        self._build_ui()
        self._configure_logging()
        self.root.after(100, self.start)
        self.root.after(200, self._drain_logs)
        self.root.after(800, self._poll_health)

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame,
            text="Lip Reader Server",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            frame,
            text=(
                "Giữ cửa sổ này mở khi điện thoại đang đọc môi. "
                "Server tự chọn GPU nếu có và tự chuyển sang CPU nếu không."
            ),
            wraplength=700,
        ).pack(anchor=tk.W, pady=(4, 16))

        status = ttk.LabelFrame(frame, text="Trạng thái", padding=14)
        status.pack(fill=tk.X)
        ttk.Label(
            status,
            textvariable=self.status_var,
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky=tk.W, columnspan=3)
        ttk.Label(status, textvariable=self.model_var).grid(
            row=1, column=0, sticky=tk.W, pady=(8, 0), columnspan=3
        )
        ttk.Label(status, textvariable=self.llm_var).grid(
            row=2, column=0, sticky=tk.W, pady=(3, 0), columnspan=3
        )
        ttk.Label(status, text="Địa chỉ nhập trên điện thoại:").grid(
            row=3, column=0, sticky=tk.W, pady=(10, 0)
        )
        address_entry = ttk.Entry(
            status,
            textvariable=self.address_var,
            state="readonly",
            width=38,
        )
        address_entry.grid(row=3, column=1, sticky=tk.EW, padx=(8, 8), pady=(10, 0))
        ttk.Button(status, text="Sao chép", command=self.copy_address).grid(
            row=3, column=2, pady=(10, 0)
        )
        status.columnconfigure(1, weight=1)

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=14)
        ttk.Button(
            buttons,
            text="Mở trang trạng thái",
            command=lambda: webbrowser.open(LOCAL_HEALTH_URL),
        ).pack(side=tk.LEFT)
        ttk.Button(
            buttons,
            text="Mở tài liệu API",
            command=lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/docs"),
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text="Dừng server", command=self.close).pack(
            side=tk.RIGHT
        )

        ttk.Label(frame, text="Nhật ký", font=("Segoe UI", 10, "bold")).pack(
            anchor=tk.W
        )
        self.log_box = scrolledtext.ScrolledText(
            frame,
            height=14,
            state=tk.DISABLED,
            font=("Consolas", 9),
            wrap=tk.WORD,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def _configure_logging(self) -> None:
        log_path = data_dir() / "server.log"
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        queue_handler = QueueLogHandler(self.log_queue)
        queue_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(queue_handler)
        self.logger = logging.getLogger("lip_reader.launcher")
        self.logger.info("Nhật ký: %s", log_path)

    def start(self) -> None:
        configure_runtime()
        existing = read_health()
        if existing is not None:
            self.logger.info("Đã phát hiện Lip Reader Server đang chạy.")
            self._show_health(existing)
            return
        ensure_ollama_started(self.logger)
        self.status_var.set("Đang khởi động API và nạp checkpoint…")
        self.owns_server = True
        self.server_thread = threading.Thread(
            target=self._run_server,
            name="lip-reader-uvicorn",
            daemon=True,
        )
        self.server_thread.start()

    def _run_server(self) -> None:
        try:
            import uvicorn
            from app.main import app as fastapi_app

            config = uvicorn.Config(
                fastapi_app,
                host=HOST,
                port=PORT,
                log_level="info",
                log_config=None,
                access_log=True,
            )
            self.server = uvicorn.Server(config)
            self.server.run()
        except Exception:
            self.logger.exception("Server không thể khởi động.")
            self.root.after(
                0,
                lambda: self.status_var.set(
                    "Không thể khởi động server – xem nhật ký bên dưới."
                ),
            )

    def _poll_health(self) -> None:
        if self.closing:
            return
        health = read_health()
        if health is not None:
            self._show_health(health)
        elif self.server_thread and not self.server_thread.is_alive():
            self.status_var.set("Server đã dừng.")
        else:
            self.status_var.set("Đang nạp model; lần đầu có thể mất một vài phút…")
        self.root.after(1500, self._poll_health)

    def _show_health(self, health: dict) -> None:
        status = health.get("status", "unknown")
        loaded = bool(health.get("model_loaded"))
        state = health.get("model_state", "unknown")
        if status == "ok" and loaded:
            self.status_var.set("Sẵn sàng nhận video từ điện thoại.")
        else:
            self.status_var.set(f"Server: {status} · model: {state}")
        self.model_var.set(
            "Model: "
            f"{state} · {health.get('device', 'unknown')} "
            f"({health.get('precision', 'unknown')})"
        )
        if health.get("llm_available"):
            self.llm_var.set(f"LLM: sẵn sàng · {health.get('llm_model')}")
        else:
            self.llm_var.set("LLM: chưa cài hoặc chưa sẵn sàng · Visual-only vẫn dùng được")

    def copy_address(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.address_var.get())
        self.status_var.set("Đã sao chép địa chỉ server.")

    def _drain_logs(self) -> None:
        if self.closing:
            return
        lines = []
        while True:
            try:
                lines.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        if lines:
            self.log_box.configure(state=tk.NORMAL)
            self.log_box.insert(tk.END, "\n".join(lines) + "\n")
            self.log_box.see(tk.END)
            self.log_box.configure(state=tk.DISABLED)
        self.root.after(250, self._drain_logs)

    def close(self) -> None:
        if self.closing:
            return
        self.closing = True
        if self.owns_server and self.server is not None:
            self.status_var.set("Đang dừng server…")
            self.server.should_exit = True
            deadline = time.time() + 8
            while (
                self.server_thread
                and self.server_thread.is_alive()
                and time.time() < deadline
            ):
                self.root.update_idletasks()
                time.sleep(0.1)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    try:
        ServerWindow().run()
        return 0
    except Exception as exc:
        try:
            messagebox.showerror(APP_NAME, f"Không thể mở server:\n{exc}")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
