from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


OUT = Path.cwd() / "output" / "seed_intro_animation"
SIZE = 1200
SCALE = 2
W = SIZE * SCALE
H = SIZE * SCALE

CREAM = (247, 245, 242)
SAGE_DARK = (45, 106, 79)
SAGE = (82, 183, 136)
SAGE_LIGHT = (130, 210, 166)
GOLD = (212, 165, 116)
BROWN = (139, 115, 85)
TERRACOTTA = (196, 149, 106)
SOIL = (154, 123, 88)
SOIL_LIGHT = (181, 145, 101)
ROOT = (237, 226, 205)

CX = SIZE / 2
MOUND_LEFT = 300
MOUND_RIGHT = 900
MOUND_WIDTH = MOUND_RIGHT - MOUND_LEFT
TOP_SAFE = 48
SIDE_SAFE = 96
BOTTOM_SAFE = 64

TITLE = "Welcome to Seed AGI"
TAGLINE = "Take a look into my world"


def sc(v: float) -> int:
    return int(round(v * SCALE))


def pt(x: float, y: float) -> tuple[int, int]:
    return sc(x), sc(y)


def rgba(color: tuple[int, int, int], alpha: int = 255) -> tuple[int, int, int, int]:
    return (*color, alpha)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float, alpha: int = 255) -> tuple[int, int, int, int]:
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3)) + (alpha,)


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def cubic(p0, p1, p2, p3, steps=58) -> list[tuple[float, float]]:
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def draw_line(draw: ImageDraw.ImageDraw, points, fill, width: float) -> None:
    if len(points) >= 2:
        draw.line([pt(x, y) for x, y in points], fill=fill, width=sc(width), joint="curve")


def rotate(x: float, y: float, angle: float) -> tuple[float, float]:
    ca = math.cos(angle)
    sa = math.sin(angle)
    return x * ca - y * sa, x * sa + y * ca


def leaf_points(cx: float, cy: float, length: float, width: float, angle: float) -> list[tuple[float, float]]:
    pts = []
    steps = 34
    for side in [1, -1]:
        span = range(steps + 1) if side == 1 else range(steps, -1, -1)
        for i in span:
            t = i / steps
            x = (t - 0.5) * length
            y = side * width * (math.sin(math.pi * t) ** 0.76)
            xr, yr = rotate(x, y, angle)
            pts.append((cx + xr, cy + yr))
    return pts


def draw_leaf(draw: ImageDraw.ImageDraw, cx, cy, length, width, angle, fill=rgba(SAGE), outline=rgba(SAGE_DARK), shadow=True) -> None:
    pts = leaf_points(cx, cy, length, width, angle)
    if shadow:
        draw.polygon([pt(x + 5, y + 6) for x, y in pts], fill=rgba(BROWN, 34))
    draw.polygon([pt(x, y) for x, y in pts], fill=fill)
    draw.line([pt(x, y) for x, y in pts + [pts[0]]], fill=outline, width=sc(3.2), joint="curve")
    sx, sy = rotate(-length * 0.36, 0, angle)
    ex, ey = rotate(length * 0.39, 0, angle)
    draw.line([pt(cx + sx, cy + sy), pt(cx + ex, cy + ey)], fill=rgba(CREAM, 150), width=sc(1.9))
    hi = leaf_points(cx - math.sin(angle) * width * 0.16, cy + math.cos(angle) * width * 0.16, length * 0.62, width * 0.31, angle)
    draw.polygon([pt(x, y) for x, y in hi], fill=rgba(SAGE_LIGHT, 70))


def mound_top_y(x: float) -> float:
    local = (x - CX) / (MOUND_WIDTH / 2)
    arch = 820 - 82 * math.exp(-(local / 0.55) ** 2)
    edge_lift = 18 * abs(local) ** 2
    wiggle = 4.0 * math.sin((x - MOUND_LEFT) / 52)
    return arch + edge_lift + wiggle


def mound_bottom_y(x: float) -> float:
    local = (x - CX) / (MOUND_WIDTH / 2)
    return 1045 - 24 * (1 - local * local) + 4.0 * math.sin((x - MOUND_LEFT) / 70 + 1.2)


BASE_Y = mound_top_y(CX)
SEED_POS = (CX - 20, BASE_Y + 98)
BLOOM_CENTER_Y = 410


def mound_paths() -> tuple[list[tuple[float, float]], list[tuple[float, float]], list[tuple[float, float]]]:
    xs = list(range(MOUND_LEFT, MOUND_RIGHT + 1, 8))
    top = [(x, mound_top_y(x)) for x in xs]
    bottom = [(x, mound_bottom_y(x)) for x in reversed(xs)]
    return top, bottom, top + bottom


def paper_background() -> Image.Image:
    rng = random.Random(66001)
    img = Image.new("RGB", (W, H), CREAM)
    pix = img.load()
    waves = [(rng.choice([1, 2, 3, 4, 6]), rng.choice([1, 2, 3, 5]), rng.random() * math.tau, rng.uniform(0.10, 0.42)) for _ in range(13)]
    for y in range(H):
        for x in range(W):
            v = 0.0
            for fx, fy, phase, amp in waves:
                v += amp * math.sin(math.tau * (fx * x / W + fy * y / H) + phase)
            delta = int(round(v * 0.62))
            pix[x, y] = tuple(max(0, min(255, CREAM[i] + delta)) for i in range(3))

    fibers = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(fibers)
    for _ in range(230):
        x = rng.uniform(0, SIZE)
        y = rng.uniform(0, SIZE)
        length = rng.uniform(24, 118)
        angle = rng.choice([0, math.pi / 2]) + rng.uniform(-0.16, 0.16)
        d.line([pt(x, y), pt(x + math.cos(angle) * length, y + math.sin(angle) * length)], fill=rgba(rng.choice([BROWN, GOLD, SAGE_DARK]), rng.randrange(4, 8)), width=sc(0.42))
    return Image.alpha_composite(img.convert("RGBA"), fibers)


def build_mound_mask() -> Image.Image:
    _top, _bottom, poly = mound_paths()
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([pt(x, y) for x, y in poly], fill=255)
    return mask


def soil_layer() -> tuple[Image.Image, Image.Image]:
    rng = random.Random(66002)
    top, _bottom, poly = mound_paths()
    mask = build_mound_mask()
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((sc(MOUND_LEFT + 28), sc(mound_bottom_y(CX) - 20), sc(MOUND_RIGHT - 28), sc(mound_bottom_y(CX) + 42)), fill=rgba(BROWN, 38))
    shadow = shadow.filter(ImageFilter.GaussianBlur(sc(12)))
    layer.alpha_composite(shadow)

    d.polygon([pt(x, y) for x, y in poly], fill=rgba(SOIL, 252))
    d.line([pt(x, y) for x, y in top], fill=rgba(BROWN), width=sc(5.8), joint="curve")
    d.line([pt(x, y - 2) for x, y in top], fill=rgba(SOIL_LIGHT, 145), width=sc(2.5), joint="curve")

    for i, (offset, color, alpha, width) in enumerate([(27, SOIL_LIGHT, 118, 2.8), (55, TERRACOTTA, 104, 2.7), (86, BROWN, 86, 2.5), (117, GOLD, 64, 2.0)]):
        line = [(x, mound_top_y(x) + offset + 4 * math.sin(x / 74 + i * 0.7)) for x in range(MOUND_LEFT + 14, MOUND_RIGHT - 13, 10)]
        strata = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(strata)
        sd.line([pt(x, y) for x, y in line], fill=rgba(color, alpha), width=sc(width), joint="curve")
        strata.putalpha(Image.composite(strata.getchannel("A"), Image.new("L", (W, H), 0), mask))
        layer.alpha_composite(strata)

    texture = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(texture)
    for _ in range(700):
        x = rng.uniform(MOUND_LEFT + 18, MOUND_RIGHT - 18)
        y = rng.uniform(mound_top_y(x) + 8, mound_bottom_y(x) - 4)
        r = rng.uniform(0.8, 3.0)
        td.ellipse((sc(x - r), sc(y - r), sc(x + r), sc(y + r)), fill=rng.choice([rgba(BROWN, 48), rgba(TERRACOTTA, 54), rgba(GOLD, 36), rgba(CREAM, 31)]))
    texture.putalpha(Image.composite(texture.getchannel("A"), Image.new("L", (W, H), 0), mask))
    layer.alpha_composite(texture)

    underground_glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(underground_glow)
    gd.ellipse((sc(CX - 170), sc(BASE_Y + 18), sc(CX + 170), sc(BASE_Y + 165)), fill=rgba(CREAM, 36))
    underground_glow = underground_glow.filter(ImageFilter.GaussianBlur(sc(15)))
    underground_glow.putalpha(Image.composite(underground_glow.getchannel("A"), Image.new("L", (W, H), 0), mask))
    layer.alpha_composite(underground_glow)
    return layer, mask


SOIL_LAYER, SOIL_MASK = soil_layer()


def compose_base() -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.alpha_composite(SOIL_LAYER)
    return img


def shoot_path() -> list[tuple[float, float]]:
    seed_x, seed_y = SEED_POS
    underground = cubic((seed_x + 31, seed_y - 6), (CX + 34, seed_y - 47), (CX - 10, BASE_Y + 23), (CX, BASE_Y - 5), 54)
    above = cubic((CX, BASE_Y - 5), (CX - 24, BASE_Y - 150), (CX + 12, 560), (CX, BLOOM_CENTER_Y), 112)
    return underground + above[1:]


FULL_SHOOT_PATH = shoot_path()


def partial_path(points: list[tuple[float, float]], progress: float) -> list[tuple[float, float]]:
    if progress <= 0:
        return []
    count = max(2, int(1 + (len(points) - 1) * min(1, progress)))
    return points[:count]


def path_point(points: list[tuple[float, float]], fraction: float) -> tuple[float, float]:
    idx = max(0, min(len(points) - 1, int((len(points) - 1) * fraction)))
    return points[idx]


def draw_seed(draw: ImageDraw.ImageDraw, split: float) -> None:
    x, y = SEED_POS
    w = 58 + split * 8
    h = 39 + split * 5
    pts = leaf_points(x, y, w, h * 0.53, -0.18)
    draw.ellipse((sc(x - w * 0.58 + 6), sc(y - h * 0.55 + 7), sc(x + w * 0.58 + 6), sc(y + h * 0.55 + 7)), fill=rgba(BROWN, 44))
    draw.polygon([pt(px, py) for px, py in pts], fill=mix(GOLD, TERRACOTTA, 0.25))
    draw.line([pt(px, py) for px, py in pts + [pts[0]]], fill=rgba(BROWN), width=sc(3.2), joint="curve")
    draw.arc((sc(x - 23), sc(y - 16), sc(x + 20), sc(y + 15)), 205, 65, fill=rgba(CREAM, 95), width=sc(1.8))


def draw_roots(draw: ImageDraw.ImageDraw, progress: float) -> None:
    if progress <= 0:
        return
    x, y = SEED_POS
    main_end = 28 + 94 * progress
    main = cubic((x + 4, y + 14), (x + 3, y + 36), (x - 12, y + 64 + 22 * progress), (x - 4, y + main_end), 44)
    draw_line(draw, main, rgba(BROWN, 92), 9.5)
    draw_line(draw, main, rgba(ROOT), 6.2)
    for t, dx, dy, need in [(0.38, -38, 30, 0.25), (0.54, 42, 30, 0.38), (0.70, -52, 38, 0.58), (0.82, 50, 34, 0.78)]:
        if progress < need:
            continue
        amount = ease((progress - need) / 0.22)
        sx, sy = path_point(main, t)
        branch = cubic((sx, sy), (sx + dx * 0.22 * amount, sy + dy * 0.20 * amount), (sx + dx * 0.70 * amount, sy + dy * 0.72 * amount), (sx + dx * amount, sy + dy * amount), 20)
        draw_line(draw, branch, rgba(BROWN, 62), 5.4)
        draw_line(draw, branch, rgba(ROOT, 230), 3.3)


def draw_crack(draw: ImageDraw.ImageDraw, progress: float) -> None:
    if progress <= 0:
        return
    y = BASE_Y - 3
    p = ease(progress)
    draw.ellipse((sc(CX - 21 - 23 * p), sc(y - 8 - 5 * p), sc(CX + 21 + 23 * p), sc(y + 10 + 5 * p)), fill=rgba(BROWN, int(44 + 40 * p)))
    draw_line(draw, [(CX - 32 - 27 * p, y + 4), (CX - 19 - 9 * p, y - 6), (CX - 3, y - 3), (CX + 14 + 9 * p, y - 10), (CX + 32 + 27 * p, y - 2)], rgba(BROWN, int(140 + 60 * p)), 2.5 + 1.6 * p)


def draw_shoot(draw: ImageDraw.ImageDraw, img: Image.Image, progress: float) -> None:
    path = partial_path(FULL_SHOOT_PATH, progress)
    if not path:
        return
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.line([pt(x + 5, y + 6) for x, y in path], fill=rgba(BROWN, 44), width=sc(13.5), joint="curve")
    shadow = shadow.filter(ImageFilter.GaussianBlur(sc(3)))
    img.alpha_composite(shadow)
    width = 6.2 + 4.2 * ease(progress)
    draw_line(draw, path, rgba(SAGE_DARK), width + 3.9)
    draw_line(draw, path, rgba(SAGE), width)
    draw_line(draw, [(x - 2, y) for x, y in path], rgba(SAGE_LIGHT, 145), max(1.7, width * 0.28))


def draw_flower(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float, open_amount: float) -> None:
    if open_amount <= 0:
        return
    p = ease(open_amount)
    outer_len = 78 * scale * (0.36 + 0.64 * p)
    outer_w = 27 * scale * (0.48 + 0.52 * p)
    outer_colors = [rgba(SAGE), rgba(SAGE_LIGHT), mix(SAGE_DARK, SAGE, 0.45), mix(SAGE, GOLD, 0.18)]
    for i in range(10):
        angle = -math.pi / 2 + math.tau * i / 10
        px = cx + math.cos(angle) * outer_len * 0.24 * p
        py = cy + math.sin(angle) * outer_len * 0.24 * p
        draw_leaf(draw, px, py, outer_len, outer_w, angle, fill=outer_colors[i % len(outer_colors)], outline=rgba(SAGE_DARK), shadow=True)

    inner_len = 48 * scale * (0.40 + 0.60 * p)
    inner_w = 18 * scale * (0.52 + 0.48 * p)
    for i in range(7):
        angle = -math.pi / 2 + math.tau * (i + 0.5) / 7
        px = cx + math.cos(angle) * inner_len * 0.18 * p
        py = cy + math.sin(angle) * inner_len * 0.18 * p
        draw_leaf(draw, px, py, inner_len, inner_w, angle, fill=mix(SAGE_LIGHT, GOLD, 0.10), outline=rgba(SAGE_DARK), shadow=False)

    r = 15 * scale
    draw.ellipse((sc(cx - r), sc(cy - r), sc(cx + r), sc(cy + r)), fill=rgba(GOLD), outline=rgba(SAGE_DARK), width=sc(2.8))
    draw.ellipse((sc(cx - r * 0.42), sc(cy - r * 0.42), sc(cx + r * 0.42), sc(cy + r * 0.42)), fill=rgba(CREAM, 135))


def draw_leaves_and_bloom(draw: ImageDraw.ImageDraw, shoot_progress: float, timeline: float) -> None:
    leaf_open = ease((timeline - 0.28) / 0.18)
    if leaf_open > 0 and shoot_progress >= 0.70:
        lx, ly = path_point(FULL_SHOOT_PATH, 0.70)
        leaf_len = 56 + 132 * leaf_open
        leaf_w = 16 + 40 * leaf_open
        draw_leaf(draw, lx - (36 + 70 * leaf_open), ly + 5, leaf_len, leaf_w, -0.50, rgba(SAGE))
        draw_leaf(draw, lx + (38 + 72 * leaf_open), ly - 8, leaf_len, leaf_w, 0.48, rgba(SAGE))

    bloom = ease((timeline - 0.47) / 0.25)
    bud = ease((timeline - 0.40) / 0.14)
    if bud > 0 and bloom < 0.25 and shoot_progress >= 0.98:
        r = 12 + 18 * bud
        draw.ellipse((sc(CX - r), sc(BLOOM_CENTER_Y - r), sc(CX + r), sc(BLOOM_CENTER_Y + r)), fill=rgba(SAGE_LIGHT), outline=rgba(SAGE_DARK), width=sc(3.0))
    draw_flower(draw, CX, BLOOM_CENTER_Y, 1.05 + 0.28 * bloom, bloom)


def draw_particles(draw: ImageDraw.ImageDraw, timeline: float) -> None:
    if timeline < 0.50:
        return
    p = ease((timeline - 0.50) / 0.22)
    rng = random.Random(8811)
    for i in range(30):
        angle = rng.uniform(-math.pi, 0)
        radius = rng.uniform(110, 270) * p
        x = CX + math.cos(angle) * radius
        y = BLOOM_CENTER_Y + math.sin(angle) * radius * 0.62
        r = rng.uniform(2.0, 5.0) * (0.6 + 0.4 * p)
        color = rng.choice([GOLD, SAGE, SAGE_DARK, SAGE_LIGHT])
        alpha = int(45 + 115 * p)
        draw.ellipse((sc(x - r), sc(y - r), sc(x + r), sc(y + r)), fill=rgba(color, alpha))


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, sc(size))


FONT_REG = r"C:\Windows\Fonts\segoeui.ttf"
FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
TITLE_FONT = font(FONT_BOLD, 68)
TAG_FONT = font(FONT_REG, 34)


def draw_centered_text(layer: Image.Image, text: str, y: float, font_obj: ImageFont.FreeTypeFont, fill, alpha: int) -> None:
    if not text or alpha <= 0:
        return
    d = ImageDraw.Draw(layer)
    bbox = d.textbbox((0, 0), text, font=font_obj)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    d.text((x + sc(2), sc(y) + sc(2)), text, font=font_obj, fill=rgba(BROWN, int(alpha * 0.16)))
    d.text((x, sc(y)), text, font=font_obj, fill=(*fill[:3], alpha))


def draw_title_text(img: Image.Image, timeline: float) -> None:
    text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    title_p = ease((timeline - 0.54) / 0.24)
    tag_p = ease((timeline - 0.76) / 0.18)
    if title_p > 0:
        visible = max(1, int(math.ceil(len(TITLE) * title_p)))
        title_text = TITLE[:visible]
        draw_centered_text(text_layer, title_text, 105, TITLE_FONT, SAGE_DARK, int(255 * min(1, title_p * 1.4)))
    if tag_p > 0:
        visible = max(1, int(math.ceil(len(TAGLINE) * tag_p)))
        tag_text = TAGLINE[:visible]
        draw_centered_text(text_layer, tag_text, 197, TAG_FONT, BROWN, int(230 * min(1, tag_p * 1.4)))
    img.alpha_composite(text_layer)


def make_frame(frame: int) -> Image.Image:
    t = (frame - 1) / 71
    seed_split = ease((t - 0.02) / 0.16)
    root_progress = ease((t - 0.05) / 0.26)
    crack_progress = ease((t - 0.15) / 0.16)
    shoot_progress = ease((t - 0.09) / 0.42)

    img = compose_base()
    draw = ImageDraw.Draw(img)
    draw_roots(draw, root_progress)
    draw_seed(draw, seed_split)
    draw_crack(draw, crack_progress)
    draw_shoot(draw, img, shoot_progress)
    draw_leaves_and_bloom(draw, shoot_progress, t)
    draw_particles(draw, t)
    draw_title_text(img, t)
    return img.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def on_cream(img: Image.Image) -> Image.Image:
    bg = Image.new("RGBA", img.size, rgba(CREAM))
    bg.alpha_composite(img.convert("RGBA"))
    return bg.convert("RGB")


def make_contact_sheet(paths: list[Path]) -> Image.Image:
    thumb = 150
    pad = 10
    cols = 9
    rows = 8
    sheet = Image.new("RGB", (cols * thumb + (cols + 1) * pad, rows * thumb + (rows + 1) * pad), CREAM)
    for idx, path in enumerate(paths):
        im = on_cream(Image.open(path)).resize((thumb, thumb), Image.Resampling.LANCZOS)
        x = pad + (idx % cols) * (thumb + pad)
        y = pad + (idx // cols) * (thumb + pad)
        sheet.paste(im, (x, y))
    return sheet


def make_animation_preview(paths: list[Path]) -> None:
    transparent_frames = [Image.open(path).convert("RGBA").resize((840, 840), Image.Resampling.LANCZOS) for path in paths]
    cream_frames = [on_cream(frame).resize((840, 840), Image.Resampling.LANCZOS) for frame in transparent_frames]
    durations = [48] * 71 + [1200]
    transparent_frames[0].save(OUT / "preview_animation_transparent.webp", save_all=True, append_images=transparent_frames[1:], duration=durations, loop=0, quality=92, method=6)
    cream_frames[0].save(OUT / "preview_animation_on_cream.webp", save_all=True, append_images=cream_frames[1:], duration=durations, loop=0, quality=92, method=6)


def validate(paths: list[Path]) -> None:
    if len(paths) != 72:
        raise ValueError(f"Expected 72 frames, got {len(paths)}")
    final = Image.open(paths[-1]).convert("RGBA")
    for path in paths:
        im = Image.open(path)
        if im.size != (SIZE, SIZE):
            raise ValueError(f"{path.name}: expected {SIZE}x{SIZE}, got {im.size}")
        if im.mode != "RGBA":
            raise ValueError(f"{path.name}: expected RGBA, got {im.mode}")
        corners = [im.getpixel(p)[3] for p in [(0, 0), (SIZE - 1, 0), (0, SIZE - 1), (SIZE - 1, SIZE - 1)]]
        if any(corners):
            raise ValueError(f"{path.name}: transparent corners expected, got {corners}")
    margins = [
        (0, 0, SIZE, TOP_SAFE),
        (0, SIZE - BOTTOM_SAFE, SIZE, SIZE),
        (0, 0, SIDE_SAFE, SIZE),
        (SIZE - SIDE_SAFE, 0, SIZE, SIZE),
    ]
    for crop in margins:
        if final.crop(crop).getchannel("A").getbbox() is not None:
            raise ValueError(f"Final artwork enters safety margin {crop}")
    final_bbox = final.getchannel("A").getbbox()
    if final_bbox is None:
        raise ValueError("Final frame has no animated content")
    if final_bbox[1] < TOP_SAFE or final_bbox[3] > SIZE - BOTTOM_SAFE:
        raise ValueError(f"Final artwork too close to edge: {final_bbox}")


def main() -> None:
    global OUT

    parser = argparse.ArgumentParser(description="Generate a high-quality Seed AGI intro animation frame pack.")
    parser.add_argument("--out", type=Path, default=OUT, help="Output folder for frames and previews.")
    args = parser.parse_args()

    OUT = args.out.resolve()
    OUT.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for frame in range(1, 73):
        path = OUT / f"frame_{frame:02d}.png"
        make_frame(frame).save(path)
        paths.append(path)
    validate(paths)
    make_contact_sheet(paths).save(OUT / "preview_contact_sheet.png")
    make_animation_preview(paths)
    print(f"Wrote {len(paths)} transparent Seed intro frames to {OUT}")


if __name__ == "__main__":
    main()
