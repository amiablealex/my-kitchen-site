"""Generate branded placeholder assets for the My Kitchen site.

All output uses the app's palette so the site looks intentional before real
images are dropped in. Replace any file with a real one of the SAME NAME.
"""
from PIL import Image, ImageDraw, ImageFont

GRAPE = (59, 16, 88)
SURFACE = (74, 26, 107)
SURFACE2 = (90, 42, 126)
TEXT = (245, 240, 250)
MUTED = (201, 184, 220)
DIVIDER = (255, 255, 255, 32)
RAINBOW = [
    (255, 95, 145), (254, 155, 70), (255, 210, 74), (177, 228, 109),
    (86, 208, 187), (90, 176, 255), (180, 136, 255),
]

OUT_IMG = "static/img"
OUT_ICO = "static/icons"


def font(size, bold=True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def centered(draw, cx, y, text, f, fill):
    l, t, r, b = draw.textbbox((0, 0), text, font=f)
    draw.text((cx - (r - l) / 2, y), text, font=f, fill=fill)
    return b - t


def rainbow_bar(img, x, y, w, h, r=None):
    """Draw a horizontal rainbow bar (the brand signature)."""
    bar = Image.new("RGB", (w, h))
    bd = ImageDraw.Draw(bar)
    n = len(RAINBOW)
    for i in range(w):
        seg = i / w * (n - 1)
        a = RAINBOW[int(seg)]
        b = RAINBOW[min(int(seg) + 1, n - 1)]
        t = seg - int(seg)
        col = tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))
        bd.line([(i, 0), (i, h)], fill=col)
    if r:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
        img.paste(bar, (x, y), mask)
    else:
        img.paste(bar, (x, y))


def phone_placeholder(name, label):
    """A 1080x2040 phone-shaped screenshot placeholder."""
    W, H = 1080, 2040
    img = Image.new("RGB", (W, H), GRAPE)
    d = ImageDraw.Draw(img)
    # top bar
    d.rectangle([0, 0, W, 150], fill=SURFACE)
    centered(d, W / 2, 56, "My Kitchen", font(46), TEXT)
    # rainbow signature
    rainbow_bar(img, 120, 320, W - 240, 26, r=13)
    d = ImageDraw.Draw(img)
    # framed cards to suggest content
    y = 440
    for i in range(4):
        d.rounded_rectangle([120, y, W - 120, y + 230], radius=28, fill=SURFACE, outline=SURFACE2, width=2)
        d.rounded_rectangle([160, y + 40, 320, y + 190], radius=20, fill=SURFACE2)
        d.rounded_rectangle([360, y + 60, W - 200, y + 96], radius=18, fill=SURFACE2)
        d.rounded_rectangle([360, y + 130, W - 320, y + 160], radius=15, fill=(70, 30, 100))
        y += 280
    # label
    centered(d, W / 2, H - 420, "SCREENSHOT", font(40), MUTED)
    centered(d, W / 2, H - 350, label, font(54), TEXT)
    centered(d, W / 2, H - 270, f"replace static/img/{name}", font(32, bold=False), MUTED)
    centered(d, W / 2, H - 210, f"{W}×{H} · keep the filename", font(30, bold=False), MUTED)
    img.save(f"{OUT_IMG}/{name}")
    print("wrote", name)


def og_card():
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), GRAPE)
    d = ImageDraw.Draw(img)
    rainbow_bar(img, 0, 0, W, 14)
    d = ImageDraw.Draw(img)
    centered(d, W / 2, 200, "My Kitchen", font(96), TEXT)
    centered(d, W / 2, 330, "The self-hosted recipe brain for your house", font(40, bold=False), MUTED)
    rainbow_bar(img, W // 2 - 120, 450, 240, 12, r=6)
    img.save(f"{OUT_IMG}/og-image.png")
    print("wrote og-image.png")


def app_icon(size, name):
    img = Image.new("RGB", (size, size), GRAPE)
    d = ImageDraw.Draw(img)
    pad = int(size * 0.16)
    d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=int(size * 0.18), fill=SURFACE)
    # a small rainbow "MK" mark: rainbow underline + M K letters
    f = font(int(size * 0.34))
    centered(d, size / 2, size * 0.30, "MK", f, TEXT)
    bw = int(size * 0.42)
    rainbow_bar(img, (size - bw) // 2, int(size * 0.64), bw, max(4, int(size * 0.05)), r=int(size * 0.02))
    img.save(f"{OUT_ICO}/{name}")
    print("wrote", name)


if __name__ == "__main__":
    phone_placeholder("screenshot-home.png", "Home")
    phone_placeholder("screenshot-wizard.png", "Lets Cook wizard")
    phone_placeholder("screenshot-suggestions.png", "Suggestions")
    phone_placeholder("screenshot-recipe.png", "A full recipe")
    og_card()
    app_icon(512, "icon-512.png")
    app_icon(192, "icon-192.png")
    app_icon(180, "icon-180.png")
    app_icon(64, "favicon.png")
    print("done")
