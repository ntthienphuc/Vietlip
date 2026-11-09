"""Temporary LAN page for APK delivery and voluntary test-recording transfer.

Does not run recognition, browse arbitrary files, or change the live server.
Keep the output directory private to the local app project.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import shutil
import sys
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

PAGE = """<!doctype html><html lang="vi"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>VietLip · Gửi bản ghi</title>
<style>body{font:17px/1.55 system-ui;background:#f3f6f6;color:#17343b;margin:0;padding:24px}
main{max-width:580px;margin:auto}section{background:white;padding:22px;border-radius:18px;margin:18px 0}
h1{font-size:28px;margin-bottom:0}h2{font-size:20px}a,button{display:inline-block;border:0;border-radius:12px;
background:#0e7775;color:white;padding:12px 18px;font:inherit;text-decoration:none;cursor:pointer}
input,select{font:inherit;max-width:100%;margin:10px 0}button:disabled{opacity:.5}progress{width:100%}
small{color:#4e666b}#status{white-space:pre-wrap}</style><main>
<h1>VietLip</h1><p>Chuyển bản ghi thử nghiệm tới PC qua Wi-Fi.</p>
<section><h2>1. Cập nhật ứng dụng</h2><p>Bản __VERSION__ có nút xuất video.
Cài cập nhật để giữ lịch sử hiện có.</p><a href="/app.apk">Tải APK VietLip __VERSION__</a>
<p>Trong app: <b>Lịch sử → chọn phiên → Lưu video ra máy</b>. Chọn thư mục Downloads.</p></section>
<section><h2>2. Gửi video đã xuất</h2><p>Video có âm thanh được gửi tới PC này để đối chiếu.
Nhận dạng đọc môi vẫn chỉ dùng hình ảnh.</p><form id="form">
<label>Phiên thử <select name="scene"><option value="scene01">Scene 1</option>
<option value="scene02">Scene 2</option><option value="scene03">Scene 3</option>
<option value="scene04">Scene 4</option></select></label><br>
<input type="file" name="video" accept="video/mp4,.mp4" required><br>
<button id="send">Gửi tới PC</button><p><small>Tối đa 200 MB mỗi video. Giữ trang này mở khi gửi.</small></p>
<progress id="progress" max="100" value="0" hidden></progress><p id="status" role="status"></p></form></section>
</main><script>const form=document.querySelector('#form'),send=document.querySelector('#send'),
progress=document.querySelector('#progress'),status=document.querySelector('#status');
form.onsubmit=e=>{e.preventDefault();const file=form.video.files[0];if(!file)return;
if(file.size>200*1024*1024){status.textContent='Video vượt 200 MB.';return;}
send.disabled=true;progress.hidden=false;status.textContent='Đang gửi…';
const req=new XMLHttpRequest();req.open('POST','/upload');
req.upload.onprogress=e=>{if(e.lengthComputable)progress.value=e.loaded/e.total*100;};
req.onload=()=>{send.disabled=false;let data;try{data=JSON.parse(req.responseText);}catch{}
status.textContent=req.status===201?'PC đã nhận video. Bạn quay lại chat và báo đã gửi nhé.':
('Chưa gửi được. '+(data?.detail||'Hãy thử lại.'));};
req.onerror=()=>{send.disabled=false;status.textContent='Mất kết nối với PC. Hãy kiểm tra Wi-Fi và thử lại.';};
req.send(new FormData(form));};</script>"""


def create_app(apk: Path, output: Path, max_bytes: int = 200 * 1024 * 1024) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    output.mkdir(parents=True, exist_ok=True)
    version = re.search(r"VietLip-(\d+\.\d+\.\d+)", apk.name)
    page = PAGE.replace("__VERSION__", version.group(1) if version else "Android")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return page

    @app.get("/healthz")
    async def health():
        return {"service": "vietlip-lan-exchange", "apk_available": apk.is_file()}

    @app.get("/app.apk")
    async def download():
        if not apk.is_file():
            raise HTTPException(503, "Bản cập nhật chưa sẵn sàng. Hãy thử lại sau.")
        return FileResponse(
            apk, filename=apk.name, media_type="application/vnd.android.package-archive"
        )

    @app.post("/upload", status_code=201)
    async def upload(video: UploadFile = File(...), scene: str = Form(pattern=r"^scene[0-9]{2}$")):
        session_dir = output / f"{scene}-{uuid4().hex}"
        session_dir.mkdir()
        target = session_dir / "recording.mp4"
        digest = hashlib.sha256()
        size = 0
        header = b""
        try:
            with target.open("xb") as destination:
                while chunk := await video.read(1024 * 1024):
                    if not header:
                        header = chunk[:32]
                    size += len(chunk)
                    if size > max_bytes:
                        raise HTTPException(413, "Video vượt giới hạn dung lượng.")
                    if shutil.disk_usage(output).free < 1024 * 1024 * 1024:
                        raise HTTPException(507, "PC không còn đủ dung lượng trống.")
                    destination.write(chunk)
                    digest.update(chunk)
            if size < 12 or b"ftyp" not in header:
                raise HTTPException(422, "Tệp chưa có header MP4 hợp lệ.")
            receipt = {
                "scene": scene,
                "bytes": size,
                "sha256": digest.hexdigest(),
                "received_at_utc": datetime.now(timezone.utc).isoformat(),
                "media_decode_verified": False,
                "source": "user_selected_lan_upload",
            }
            (session_dir / "receipt.json").write_text(
                json.dumps(receipt, indent=2), encoding="utf8"
            )
            return receipt
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            await video.close()

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", required=True)
    parser.add_argument("--port", type=int, default=7101)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # pythonw has no console streams; keep errors local and readable.
    log = (args.output / "exchange.log").open("a", encoding="utf8", buffering=1)
    sys.stdout = sys.stderr = log
    logging.basicConfig(stream=log, level=logging.INFO)
    import uvicorn

    uvicorn.run(
        create_app(args.apk.resolve(), args.output.resolve()),
        host=args.bind,
        port=args.port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
