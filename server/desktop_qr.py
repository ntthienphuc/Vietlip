"""Render a VietLip LAN pairing code using the packaged OpenCV runtime."""

from urllib.parse import urlencode


def pairing_code(address: str, size: int = 264) -> bytes:
    import cv2

    payload = "vietlip://pair?" + urlencode({"server": address})
    grid = cv2.QRCodeEncoder_create().encode(payload)
    grid = cv2.copyMakeBorder(grid, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
    scale = max(1, size // grid.shape[0])
    image = cv2.resize(grid, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    encoded, png = cv2.imencode(".png", image)
    if not encoded:
        raise RuntimeError("Không thể tạo mã QR.")
    return png.tobytes()
