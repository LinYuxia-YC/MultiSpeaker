"""Generate the application icon / logo (Pillow)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(r"I:\DSHwork\MultiSpeaker\app\resources")
OUT.mkdir(parents=True, exist_ok=True)
S = 1024


def gradient(size: int):
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    top = (58, 108, 208)
    bottom = (124, 76, 214)
    for y in range(size):
        t = y / (size - 1)
        # diagonal-ish blend
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        d.line([(0, y), (size, y)], fill=(r, g, b))
    return img


def rounded_mask(size: int, radius: int):
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def draw_icon(size: int = S) -> Image.Image:
    k = size / 1024.0
    bg = gradient(size).convert("RGBA")
    # soft highlight
    hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(hl)
    d.ellipse([-size * 0.25, -size * 0.55, size * 0.95, size * 0.35], fill=(255, 255, 255, 34))
    hl = hl.filter(ImageFilter.GaussianBlur(60 * k))
    bg = Image.alpha_composite(bg, hl)

    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    white = (255, 255, 255, 245)

    # speaker body + cone
    d.rounded_rectangle([250 * k, 424 * k, 392 * k, 600 * k], radius=26 * k, fill=white)
    d.polygon(
        [(392 * k, 458 * k), (540 * k, 352 * k), (540 * k, 672 * k), (392 * k, 566 * k)],
        fill=white,
    )

    # sound arcs
    cx, cy = 540 * k, 512 * k
    for radius, width in ((138, 30), (222, 30), (306, 30)):
        d.arc(
            [cx - radius * k, cy - radius * k, cx + radius * k, cy + radius * k],
            start=-52,
            end=52,
            fill=white,
            width=int(width * k),
        )

    icon = Image.alpha_composite(bg, layer)
    mask = rounded_mask(size, int(230 * k))
    icon.putalpha(mask)
    return icon


icon = draw_icon(S)
big = icon.resize((512, 512), Image.LANCZOS)
big.save(OUT / "logo.png")
icon.resize((256, 256), Image.LANCZOS).save(OUT / "app_256.png")
icon.save(
    OUT / "app.ico",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("written:", list(OUT.glob("*")))
