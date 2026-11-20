"""VietLip Windows companion. The bundled interpreter also supports headless QA."""

from __future__ import annotations

import argparse
import base64
import logging
from logging.handlers import RotatingFileHandler
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk

from desktop_gemini import configure_gemini
from desktop_qr import pairing_code

from desktop_runtime import (
    APP_NAME,
    APP_VERSION,
    DESKTOP_VERSION,
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
        self.root.title(f"{APP_NAME} · {DESKTOP_VERSION}")
        self.root.geometry("744x720")
        self.root.minsize(650, 640)
        self.root.configure(bg="#f5f8ff")
        icon = ROOT.parent / "VietLip.ico"
        if icon.is_file():
            self.root.iconbitmap(str(icon))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue(maxsize=2000)
        self.server = None
        self.server_thread = None
        self.closing = False
        self.polling = False
        self.was_ready = False
        self.missed_health = 0
        self.logs_visible = False
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
        style.configure("TFrame", background="#f5f8ff")
        style.configure("TLabel", background="#f5f8ff", foreground="#1e2742", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground="#5f6f84")
        style.configure("Card.TFrame", background="white")
        style.configure("Card.TLabel", background="white", foreground="#5f6f84")
        style.configure("Title.TLabel", font=("Segoe UI", 26, "bold"))
        style.configure(
            "Status.TLabel", background="white", foreground="#006b9a", font=("Segoe UI", 18, "bold")
        )
        style.configure("TButton", font=("Segoe UI", 10), padding=(14, 10))
        style.configure("Accent.TButton", background="#006b9a", foreground="white", borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#005a82"), ("pressed", "#004f72")])
        style.configure("TCombobox", padding=10, fieldbackground="white", foreground="#1e2742")
        panel = ttk.Frame(self.root, padding=28)
        panel.pack(fill="both", expand=True)
        footer = ttk.Frame(panel)
        footer.pack(side="bottom", fill="x", pady=(20, 0))
        ttk.Label(
            footer, text="Đọc môi bằng hình ảnh\nGợi ý câu qua Gemini khi được chọn", style="Muted.TLabel"
        ).pack(side="left")
        ttk.Button(footer, text="Đóng máy chủ", command=self.close).pack(side="right")
        self.footer = footer

        header = ttk.Frame(panel)
        header.pack(fill="x")
        ttk.Label(header, text="VietLip", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=DESKTOP_VERSION, style="Muted.TLabel").pack(
            side="right", anchor="s", pady=8
        )
        ttk.Label(panel, text="Máy chủ đọc môi tiếng Việt", style="Muted.TLabel").pack(
            anchor="w", pady=(2, 0)
        )
        card = ttk.Frame(panel, style="Card.TFrame", padding=20)
        card.pack(fill="x", pady=(24, 24))
        self.status_label = ttk.Label(
            card, textvariable=self.status, style="Status.TLabel", wraplength=600
        )
        self.status_label.pack(anchor="w")
        detail_label = ttk.Label(
            card, textvariable=self.detail, style="Card.TLabel", wraplength=600
        )
        detail_label.pack(anchor="w", pady=(8, 0))
        pairing = ttk.Frame(panel, style="Card.TFrame", padding=16)
        pairing.pack(fill="x", pady=(0, 16))
        self.qr_placeholder = tk.PhotoImage(width=1, height=1)
        self.qr_label = tk.Label(
            pairing, bg="white", fg="#5f6f84", width=264, height=264,
            wraplength=220, image=self.qr_placeholder, compound="center",
        )
        self.qr_label.pack(side="left", padx=(0, 18))
        connection = ttk.Frame(pairing, style="Card.TFrame")
        connection.pack(side="left", fill="both", expand=True, pady=8)
        ttk.Label(
            connection, text="Kết nối điện thoại", style="Card.TLabel",
            font=("Segoe UI", 15, "bold"), foreground="#1e2742",
        ).pack(anchor="w")
        ttk.Label(
            connection, text="Mở VietLip trên điện thoại\nvà vào Cài đặt → Quét QR.",
            style="Card.TLabel", justify="left",
        ).pack(anchor="w", pady=(6, 14))
        self.address_box = ttk.Combobox(
            connection,
            textvariable=self.lan,
            values=self.addresses,
            state="readonly",
            font=("Segoe UI", 12),
            width=25,
        )
        self.address_box.pack(fill="x")
        lan_actions = ttk.Frame(connection, style="Card.TFrame")
        lan_actions.pack(fill="x", pady=(12, 8))
        self.copy_button = ttk.Button(
            lan_actions,
            text="Sao chép địa chỉ",
            style="Accent.TButton",
            command=lambda: self.copy(self.lan.get()),
        )
        self.copy_button.pack(side="left")
        ttk.Button(lan_actions, text="Làm mới IP", command=self.refresh_addresses).pack(
            side="left", padx=(10, 0)
        )
        hint = ttk.Label(
            connection, textvariable=self.network_status, style="Card.TLabel",
            justify="left", wraplength=270,
        )
        hint.pack(anchor="w", pady=(6, 0))
        self.lan.trace_add("write", self.update_pairing_code)
        self.update_pairing_code()
        options = ttk.Frame(panel)
        options.pack(fill="x")
        self.key_button = ttk.Button(options, text="Cài đặt key Gemini", command=self.set_key, state="disabled")
        self.key_button.pack(side="left")
        self.log_toggle = ttk.Button(options, text="Xem nhật ký", command=self.toggle_logs)
        self.log_toggle.pack(side="left", padx=10)
        self.key_status = tk.StringVar(value="")
        ttk.Label(panel, textvariable=self.key_status, style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        self.log_container = ttk.Frame(panel)
        self.log_box = scrolledtext.ScrolledText(
            self.log_container,
            height=5,
            state="disabled",
            font=("Consolas", 9),
            wrap="word",
            relief="flat",
            background="#e9efed",
            foreground="#30494f",
            borderwidth=0,
            padx=12,
            pady=10,
        )
        self.log_box.pack(fill="both", expand=True)

        def resize(event):
            width = max(250, event.width - 40)
            self.status_label.configure(wraplength=width)
            detail_label.configure(wraplength=width)

        panel.bind("<Configure>", resize)

    def set_key(self):
        value = simpledialog.askstring(
            "Gemini", "Nhập key Gemini để thêm gợi ý sau mỗi câu. Key lưu trên PC này.",
            show="*", parent=self.root,
        )
        if value is None:
            return
        try:
            configure_gemini(value)
        except (OSError, ValueError):
            messagebox.showerror(APP_NAME, "Chưa lưu được key Gemini. Kiểm tra key rồi thử lại.", parent=self.root)
            return
        self.key_status.set("Đã lưu key Gemini. Chọn Kèm gợi ý câu trên điện thoại.")

    def toggle_logs(self):
        self.logs_visible = not self.logs_visible
        if self.logs_visible:
            self.log_container.pack(fill="both", expand=True, pady=(12, 0))
            self.log_toggle.configure(text="Ẩn nhật ký")
            if self.root.winfo_height() < 780:
                self.root.geometry(f"{self.root.winfo_width()}x780")
        else:
            self.log_container.pack_forget()
            self.log_toggle.configure(text="Xem nhật ký")

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
                configured = configure_gemini()
                self.events.put(("gemini", configured))
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
        self.missed_health = 0
        self.status_label.configure(foreground="#006b9a")
        if health.get("app_version") != APP_VERSION:
            self.status.set("Đang có một server phiên bản khác")
            self.detail.set(
                "Đóng server cũ rồi mở lại VietLip để dùng bản đã cài. Cửa sổ này không dừng server đó."
            )
        elif health.get("realtime_available") and health.get("model_state") == "ready":
            self.was_ready = True
            self.status.set("Sẵn sàng đọc môi")
            device = (
                "GPU NVIDIA"
                if str(health.get("device", "")).startswith("cuda")
                else "CPU · sẽ chậm hơn GPU"
            )
            self.detail.set(f"{device}. Tự nhận khoảng ngừng nói để chốt phụ đề.")
        elif health.get("last_error"):
            self.status_label.configure(foreground="#c2413b")
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
            elif kind == "gemini":
                self.key_button.configure(state="normal")
                self.key_status.set("Gemini đã có key trên PC." if value else "Phụ đề trực tiếp đã sẵn sàng. Thêm key để dùng gợi ý câu.")
            elif kind in ("health", "external"):
                self.polling = False
                if value:
                    self.show_health(value)
                elif self.was_ready:
                    self.missed_health += 1
                    if self.missed_health >= 3:
                        self.status_label.configure(foreground="#c2413b")
                        self.status.set("Máy chủ chưa phản hồi")
                        self.detail.set(
                            "Chờ một chút. Nếu trạng thái không đổi, đóng và mở lại VietLip Server."
                        )
            elif kind == "error":
                self.status_label.configure(foreground="#c2413b")
                self.status.set("Không khởi động được máy chủ")
                self.detail.set(value)
            elif kind == "stopped" and not self.closing:
                self.status.set("Máy chủ đã dừng")
        if not self.closing:
            self.root.after(150, self.drain)

    def refresh_addresses(self):
        current = self.lan.get()
        self.addresses = local_addresses(self.args.port)
        self.address_box.configure(values=self.addresses)
        self.lan.set(current if current in self.addresses else next(iter(self.addresses), ""))
        self.network_status.set("Đã làm mới IP. Quét lại nếu bạn vừa đổi mạng.")

    def update_pairing_code(self, *_):
        address = self.lan.get()
        self.qr_image = None
        if address in self.addresses:
            try:
                self.qr_image = tk.PhotoImage(data=base64.b64encode(pairing_code(address)))
            except Exception:
                logging.exception("Không thể tạo mã QR")
        self.copy_button.configure(state="normal" if address in self.addresses else "disabled")
        self.qr_label.configure(
            image=self.qr_image or self.qr_placeholder,
            compound="center",
            text="" if self.qr_image else (
                "Chưa có IP mạng nội bộ" if not self.addresses else "Có thể nhập IP trong Cài đặt"
            ),
        )

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
        configure_gemini()
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
