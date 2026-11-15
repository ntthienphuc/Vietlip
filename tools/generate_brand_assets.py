"""Render VietLip's lip contours for Android, Windows and web."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def mark(size):
    image = Image.new("RGB", (512, 512), (56, 87, 214))
    draw = ImageDraw.Draw(image)

    def curve(a, b, c, d):
        return [
            (
                a[0] * (1 - t) ** 3
                + 3 * b[0] * (1 - t) ** 2 * t
                + 3 * c[0] * (1 - t) * t * t
                + d[0] * t**3,
                a[1] * (1 - t) ** 3
                + 3 * b[1] * (1 - t) ** 2 * t
                + 3 * c[1] * (1 - t) * t * t
                + d[1] * t**3,
            )
            for t in [i / 80 for i in range(81)]
        ]

    def point(x, y):
        return (98 + x * 316, 98 + y * 316)

    outline = (
        curve(point(0.06, 0.53), point(0.25, 0.48), point(0.30, 0.17), point(0.5, 0.33))
        + curve(
            point(0.5, 0.33), point(0.70, 0.17), point(0.75, 0.48), point(0.94, 0.53)
        )
        + curve(
            point(0.94, 0.53), point(0.72, 0.92), point(0.28, 0.92), point(0.06, 0.53)
        )
    )
    draw.line(outline, fill="white", width=28, joint="curve")
    middle = curve(
        point(0.13, 0.54), point(0.38, 0.61), point(0.62, 0.61), point(0.87, 0.54)
    )
    draw.line(middle, fill="white", width=28)
    for x, y in [middle[0], middle[-1]]:
        draw.ellipse((x - 14, y - 14, x + 14, y + 14), fill="white")
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main():
    res = ROOT / "android/app/src/main/res"
    for density, size in [
        ("mdpi", 48),
        ("hdpi", 72),
        ("xhdpi", 96),
        ("xxhdpi", 144),
        ("xxxhdpi", 192),
    ]:
        mark(size).save(res / f"mipmap-{density}/ic_launcher.png")
    for size in (192, 512):
        for prefix in ("Icon", "Icon-maskable"):
            mark(size).save(ROOT / f"web/icons/{prefix}-{size}.png")
    mark(32).save(ROOT / "web/favicon.png")
    mark(256).save(
        ROOT / "windows/runner/resources/app_icon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
    )
    mark(256).save(
        ROOT / "packaging/windows_server/VietLip.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
    )


if __name__ == "__main__":
    main()
