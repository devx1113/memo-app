"""アプリアイコン (assets/app.ico, assets/app.png) を生成する。 python tools/make_icon.py"""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "assets"
S = 1024  # 高解像度で描いて縮小する


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def gradient(size, top, bottom):
    g = Image.new("RGBA", (1, size))
    for y in range(size):
        g.putpixel((0, y), lerp(top, bottom, y / (size - 1)))
    return g.resize((size, size))


def rounded_mask(size, box, r):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius=r, fill=255)
    return m


def build() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # 背景: 角丸スクエア + 青のグラデーション
    pad = 56
    bg = gradient(S, (64, 156, 255, 255), (24, 84, 214, 255))
    img.paste(bg, (0, 0), rounded_mask(S, [pad, pad, S - pad, S - pad], 210))

    # 上部のハイライト
    hl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse([-200, -620, S + 200, 380], fill=(255, 255, 255, 34))
    img.alpha_composite(Image.composite(hl, Image.new("RGBA", (S, S)), rounded_mask(S, [pad, pad, S - pad, S - pad], 210)))

    # メモ用紙の影
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([250, 236, 770, 836], radius=70, fill=(8, 30, 90, 120))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(28)))

    # メモ用紙
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([240, 200, 760, 800], radius=70, fill=(255, 255, 255, 255))
    # 用紙上部のバー (カレンダー風)
    top = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(top).rounded_rectangle([240, 200, 760, 800], radius=70, fill=(255, 94, 87, 255))
    clip = Image.new("L", (S, S), 0)
    ImageDraw.Draw(clip).rectangle([240, 200, 760, 330], fill=255)
    img.paste(top, (0, 0), clip_and(top, clip))
    d = ImageDraw.Draw(img)
    # リング
    for x in (360, 500, 640):
        d.rounded_rectangle([x - 18, 160, x + 18, 260], radius=18, fill=(232, 238, 248, 255))
    # 本文の線
    for i, (x2, c) in enumerate(((660, (60, 120, 230)), (660, (170, 186, 210)), (560, (170, 186, 210)))):
        y = 420 + i * 110
        d.rounded_rectangle([320, y, x2, y + 44], radius=22, fill=c + (255,))

    # ベル (右下のバッジ)
    badge = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    cx, cy, r = 742, 742, 190
    bd.ellipse([cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14], fill=(255, 255, 255, 255))
    bd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 176, 32, 255))
    # ベル本体
    bd.pieslice([cx - 80, cy - 118, cx + 80, cy + 42], 180, 360, fill="white")
    bd.rectangle([cx - 80, cy - 40, cx + 80, cy + 40], fill="white")
    bd.polygon([(cx - 80, cy + 30), (cx + 80, cy + 30), (cx + 112, cy + 74), (cx - 112, cy + 74)], fill="white")
    bd.ellipse([cx - 32, cy + 70, cx + 32, cy + 126], fill="white")
    bd.ellipse([cx - 18, cy - 142, cx + 18, cy - 106], fill="white")
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([cx - r - 10, cy - r + 6, cx + r + 18, cy + r + 30], fill=(8, 30, 90, 90))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)))
    img.alpha_composite(badge)
    return img


def clip_and(layer, mask):
    """layer のアルファと mask の積"""
    return ImageChops.multiply(layer.getchannel("A"), mask)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    big = build()
    big.resize((256, 256), Image.LANCZOS).save(OUT / "app.png")
    big.resize((512, 512), Image.LANCZOS).save(OUT / "app_512.png")
    sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]
    big.resize((256, 256), Image.LANCZOS).save(OUT / "app.ico", sizes=sizes)
    print("written:", *sorted(p.name for p in OUT.iterdir()))
