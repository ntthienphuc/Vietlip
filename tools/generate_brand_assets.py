"""Render the geometric VietLip speech mark for Android, Windows and web."""

from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def mark(size):
    image = Image.new("RGB", (512, 512))
    pixels = image.load()
    for y in range(512):
        for x in range(512):
            t = (x + y) / 1022
            pixels[x, y] = tuple(round(a * (1-t) + b * t)
                for a, b in zip((12, 117, 110), (16, 75, 89)))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((111, 141, 401, 357), radius=30, fill="white")
    draw.polygon([(156, 345), (156, 394), (217, 345)], fill="white")
    ink = (12, 117, 110)
    for box in [(150, 199, 191, 218), (210, 199, 360, 218),
                (150, 253, 293, 272), (312, 253, 360, 272)]:
        draw.rounded_rectangle(box, radius=7, fill=ink)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main():
    res = ROOT / "android/app/src/main/res"
    for density, size in [("mdpi", 48), ("hdpi", 72), ("xhdpi", 96),
                          ("xxhdpi", 144), ("xxxhdpi", 192)]:
        mark(size).save(res / f"mipmap-{density}/ic_launcher.png")
    for size in (192, 512):
        for prefix in ("Icon", "Icon-maskable"):
            mark(size).save(ROOT / f"web/icons/{prefix}-{size}.png")
    mark(32).save(ROOT / "web/favicon.png")
    mark(256).save(ROOT / "windows/runner/resources/app_icon.ico", sizes=[(16,16), (32,32), (48,48), (256,256)])
    mark(256).save(ROOT / "packaging/windows_server/VietLip.ico", sizes=[(16,16), (32,32), (48,48), (256,256)])


if __name__ == "__main__":
    main()
