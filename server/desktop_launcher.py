"""VietLip Windows companion. The bundled interpreter also supports headless QA."""

from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from desktop_runtime import (
    APP_NAME,
    APP_VERSION,
    ROOT,
    configure_runtime,
    data_dir,
    local_addresses,
    port_available,
    read_health,
)


class QueueLogHandler(logging.Handler):
    def __init__(self, target: queue.Queue):
        super().__init__()
        self.target = target

    def emit(self, record):
        try:
            self.target.put_nowait(("log", self.format(record)))
        except queue.Full:
            pass


def configure_logging(events=None):
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%H:%M:%S")
    handler = RotatingFileHandler(
        data_dir() / "server.log", maxBytes=4_000_000, backupCount=2, encoding="utf-8"
    )
    handlers = [handler]
    if events is not None:
        handlers.append(QueueLogHandler(events))
    else:
        handlers.append(logging.StreamHandler())
    for item in handlers:
        item.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)


def make_server(port):
    import uvicorn
    from app.main import app

    return uvicorn.Server(
        uvicorn.Config(
            app,
            host="0.0.0.0",
            port=port,
            log_config=None,
            access_log=False,
            ws_max_size=1100000,
            ws_max_queue=8,
        )
    )


class ServerWindow:
    def __init__(self, args):
        self.args = args
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} · {APP_VERSION}")
        self.root.geometry("760x650")
        self.root.minsize(700, 610)
        self.root.configure(bg="#f3f6f6")
        icon = ROOT.parent / "VietLip.ico"
        if icon.is_file():
            self.root.iconbitmap(str(icon))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue(maxsize=2000)
        self.server = None
        self.server_thread = None
        self.closing = False
        self.polling = False
        self.status = tk.StringVar(value="Đang chuẩn bị máy chủ…")
        self.detail = tk.StringVar(value="Lần đầu có thể cần vài phút để nạp mô hình.")
        self.network_status = tk.StringVar(
            value="Điện thoại và PC cần kết nối cùng mạng Wi-Fi / LAN."
        )
        self.addresses = local_addresses(args.port)
        self.lan = tk.StringVar(
            value=self.addresses[0] if self.addresses else "Chưa có địa chỉ mạng nội bộ"
        )
        self._build_ui()
        configure_logging(self.events)
        self.root.after(100, self.start)
        self.root.after(100, self.drain)
        self.root.after(500, self.poll)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f3f6f6")
        style.configure("TLabel", background="#f3f6f6", foreground="#16343c", font=("Segoe UI", 10))
        style.configure("Card.TFrame", background="white")
        style.configure("Card.TLabel", background="white")
        style.configure("Title.TLabel", font=("Segoe UI", 25, "bold"))
        style.configure(
            "Status.TLabel", background="white", foreground="#0c756e", font=("Segoe UI", 17, "bold")
        )
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 9))
        style.configure("Accent.TButton", background="#0c756e", foreground="white")
        style.map("Accent.TButton", background=[("active", "#105f5a")])
        panel = ttk.Frame(self.root, padding=24)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="VietLip", style="Title.TLabel").pack(anchor="w")
        ttk.Label(panel, text="Máy chủ đọc môi tiếng Việt  /  " + APP_VERSION).pack(anchor="w")
        card = ttk.Frame(panel, style="Card.TFrame", padding=20)
        card.pack(fill="x", pady=(20, 16))
        ttk.Label(card, textvariable=self.status, style="Status.TLabel", wraplength=620).pack(
            anchor="w"
        )
        ttk.Label(card, textvariable=self.detail, style="Card.TLabel", wraplength=620).pack(
            anchor="w", pady=(8, 0)
        )
        ttk.Label(panel, text="01  Nhập địa chỉ này trong app", font=("Segoe UI", 11, "bold")).pack(
            anchor="w"
        )
        lan_row = ttk.Frame(panel)
        lan_row.pack(fill="x", pady=(12, 8))
        self.address_box = ttk.Combobox(
            lan_row,
            textvariable=self.lan,
            values=self.addresses,
            state="readonly",
            width=32,
            font=("Segoe UI", 13),
        )
        self.address_box.pack(side="left", fill="x", expand=True)
        ttk.Button(
            lan_row,
            text="Sao chép IP",
            style="Accent.TButton",
            command=lambda: self.copy(self.lan.get()),
        ).pack(side="left", padx=8)
        ttk.Button(lan_row, text="Làm mới", command=self.refresh_addresses).pack(side="left")
        ttk.Label(panel, textvariable=self.network_status, wraplength=660).pack(
            anchor="w", pady=(3, 14)
        )
        ttk.Label(
            panel, text="02  Mở VietLip → Cài đặt → Lưu và kiểm tra", font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")
        ttk.Label(
            panel, text="Sau đó bấm Bắt đầu live. Giữ cửa sổ này mở trong phiên.", wraplength=660
        ).pack(anchor="w", pady=(5, 12))
        self.log_box = scrolledtext.ScrolledText(
            panel,
            height=5,
            state="disabled",
            font=("Consolas", 9),
            wrap="word",
            relief="flat",
            background="#e9efef",
            foreground="#30494f",
            borderwidth=0,
            padx=10,
            pady=8,
        )
        self.log_box.pack(fill="both", expand=True)
        actions = ttk.Frame(panel)
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="Mở nhật ký", command=lambda: os.startfile(data_dir())).pack(
            side="left"
        )
        ttk.Label(
            actions, text="Chỉ dùng hình ảnh · phụ đề cần kiểm tra", font=("Segoe UI", 9)
        ).pack(side="left", padx=12)
        ttk.Button(actions, text="Đóng máy chủ", command=self.close).pack(side="right")

    def start(self):
        def worker():
            try:
                existing = read_health(self.args.port)
                if existing:
                    self.events.put(("external", existing))
                    return
                if not port_available(self.args.port):
                    raise RuntimeError(
                        f"Cổng {self.args.port} đang được dùng. Đóng server cũ rồi mở lại."
                    )
                configure_runtime(self.args.device, self.args.trace_directory)
                self.server = make_server(self.args.port)
                if self.closing:
                    return
                self.server.run()
                self.events.put(("stopped", None))
            except BaseException as exc:
                logging.exception("Không khởi động được server")
                self.events.put(("error", str(exc)))

        self.server_thread = threading.Thread(target=worker, daemon=True)
        self.server_thread.start()

    def poll(self):
        if self.closing:
            return
        if not self.polling:
            self.polling = True

            def worker():
                self.events.put(("health", read_health(self.args.port)))

            threading.Thread(target=worker, daemon=True).start()
        self.root.after(1500, self.poll)

    def show_health(self, health):
        if health.get("app_version") != APP_VERSION:
            self.status.set("Đang có một server phiên bản khác")
            self.detail.set(
                "Đóng server cũ rồi mở lại VietLip để dùng bản đã cài. Cửa sổ này không dừng server đó."
            )
        elif health.get("realtime_available") and health.get("model_state") == "ready":
            self.status.set("Sẵn sàng đọc môi")
            device = (
                "GPU NVIDIA"
                if str(health.get("device", "")).startswith("cuda")
                else "CPU · sẽ chậm hơn GPU"
            )
            self.detail.set(f"{device}  ·  Mô hình đã nạp  ·  Tự nhận khoảng ngừng nói")
        elif health.get("last_error"):
            self.status.set("Chưa thể đọc môi")
            self.detail.set(health["last_error"])
        else:
            self.status.set("Đang nạp mô hình…")

    def drain(self):
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self.log_box.configure(state="normal")
                self.log_box.insert("end", value + "\n")
                if int(self.log_box.index("end-1c").split(".")[0]) > 500:
                    self.log_box.delete("1.0", "101.0")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
            elif kind in ("health", "external"):
                self.polling = False
                if value:
                    self.show_health(value)
            elif kind == "error":
                self.status.set("Không khởi động được máy chủ")
                self.detail.set(value)
            elif kind == "stopped" and not self.closing:
                self.status.set("Máy chủ đã dừng")
        if not self.closing:
            self.root.after(150, self.drain)

    def refresh_addresses(self):
        self.addresses = local_addresses(self.args.port)
        self.address_box.configure(values=self.addresses)
        self.lan.set(self.addresses[0] if self.addresses else "Chưa có địa chỉ mạng nội bộ")
        self.network_status.set("Đã cập nhật IP. Nếu đổi Wi-Fi, nhập lại địa chỉ mới trong app.")

    def copy(self, value):
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.network_status.set(f"Đã sao chép: {value}")

    def close(self):
        if self.closing:
            return
        self.closing = True
        if self.server:
            self.server.should_exit = True
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--port", type=int, default=7100)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--trace-directory", default="")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    if args.headless:
        configure_logging()
        if not port_available(args.port):
            raise RuntimeError(f"Port {args.port} is already in use")
        configure_runtime(args.device, args.trace_directory)
        make_server(args.port).run()
    else:
        try:
            ServerWindow(args).run()
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))
            raise


if __name__ == "__main__":
    main()
