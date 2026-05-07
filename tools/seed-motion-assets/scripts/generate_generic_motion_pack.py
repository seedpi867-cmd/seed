from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


CREAM = (247, 245, 242)
SAGE_DARK = (45, 106, 79)
SAGE = (82, 183, 136)
SAGE_LIGHT = (130, 210, 166)
GOLD = (212, 165, 116)
BROWN = (139, 115, 85)
TERRACOTTA = (196, 149, 106)
ROOT = (237, 226, 205)

TITLE_DEFAULT = "Welcome to Seed AGI"
TAGLINE_DEFAULT = "Take a look into my world"


class MotionPack:
    def __init__(
        self,
        out: Path,
        thing: str,
        title: str,
        tagline: str,
        size: int = 1200,
        frames: int = 72,
        background: str = "transparent",
    ) -> None:
        self.out = out
        self.thing = thing.strip() or "seed bloom"
        self.title = title.strip() or TITLE_DEFAULT
        self.tagline = tagline.strip() or TAGLINE_DEFAULT
        self.size = size
        self.frames = frames
        self.background = "transparent" if background == "auto" else background
        self.scale = 2
        self.w = size * self.scale
        self.h = size * self.scale
        self.cx = size / 2
        self.top_safe = 48
        self.side_safe = 96
        self.bottom_safe = 64
        self.font_bold = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", self.sc(68))
        self.font_reg = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", self.sc(34))

    def sc(self, value: float) -> int:
        return int(round(value * self.scale))

    def pt(self, x: float, y: float) -> tuple[int, int]:
        return self.sc(x), self.sc(y)

    def rgba(self, color: tuple[int, int, int], alpha: int = 255) -> tuple[int, int, int, int]:
        return (*color, alpha)

    def ease(self, value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3 - 2 * value)

    def cubic(self, p0, p1, p2, p3, steps=48) -> list[tuple[float, float]]:
        pts = []
        for i in range(steps + 1):
            t = i / steps
            u = 1 - t
            x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
            y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
            pts.append((x, y))
        return pts

    def draw_line(self, draw: ImageDraw.ImageDraw, points, fill, width: float) -> None:
        if len(points) >= 2:
            draw.line([self.pt(x, y) for x, y in points], fill=fill, width=self.sc(width), joint="curve")

    def rotate(self, x: float, y: float, angle: float) -> tuple[float, float]:
        ca = math.cos(angle)
        sa = math.sin(angle)
        return x * ca - y * sa, x * sa + y * ca

    def leaf_points(self, cx: float, cy: float, length: float, width: float, angle: float) -> list[tuple[float, float]]:
        pts = []
        for side in [1, -1]:
            span = range(35) if side == 1 else range(34, -1, -1)
            for i in span:
                t = i / 34
                x = (t - 0.5) * length
                y = side * width * (math.sin(math.pi * t) ** 0.76)
                xr, yr = self.rotate(x, y, angle)
                pts.append((cx + xr, cy + yr))
        return pts

    def draw_leaf(self, draw: ImageDraw.ImageDraw, cx, cy, length, width, angle, fill=None, outline=None, shadow=True) -> None:
        fill = fill or self.rgba(SAGE)
        outline = outline or self.rgba(SAGE_DARK)
        pts = self.leaf_points(cx, cy, length, width, angle)
        if shadow:
            draw.polygon([self.pt(x + 5, y + 6) for x, y in pts], fill=self.rgba(BROWN, 34))
        draw.polygon([self.pt(x, y) for x, y in pts], fill=fill)
        draw.line([self.pt(x, y) for x, y in pts + [pts[0]]], fill=outline, width=self.sc(3.2), joint="curve")
        sx, sy = self.rotate(-length * 0.36, 0, angle)
        ex, ey = self.rotate(length * 0.39, 0, angle)
        draw.line([self.pt(cx + sx, cy + sy), self.pt(cx + ex, cy + ey)], fill=self.rgba(CREAM, 150), width=self.sc(1.9))

    def base(self) -> Image.Image:
        if self.background == "transparent":
            return Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        rng = random.Random(2001)
        img = Image.new("RGBA", (self.w, self.h), self.rgba(CREAM))
        draw = ImageDraw.Draw(img)
        for _ in range(240):
            x = rng.uniform(0, self.size)
            y = rng.uniform(0, self.size)
            length = rng.uniform(26, 150)
            angle = rng.choice([0, math.pi / 2]) + rng.uniform(-0.16, 0.16)
            draw.line(
                [self.pt(x, y), self.pt(x + math.cos(angle) * length, y + math.sin(angle) * length)],
                fill=self.rgba(rng.choice([BROWN, GOLD, SAGE_DARK]), rng.randrange(4, 8)),
                width=self.sc(0.45),
            )
        return img

    def draw_title(self, img: Image.Image, t: float) -> None:
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        title_p = self.ease((t - 0.54) / 0.24)
        tag_p = self.ease((t - 0.76) / 0.18)
        self._draw_revealed_text(draw, self.title, 105, self.font_bold, SAGE_DARK, title_p, 255)
        self._draw_revealed_text(draw, self.tagline, 197, self.font_reg, BROWN, tag_p, 230)
        img.alpha_composite(layer)

    def _draw_revealed_text(self, draw: ImageDraw.ImageDraw, text: str, y: float, font, color, progress: float, max_alpha: int) -> None:
        if progress <= 0:
            return
        visible = max(1, int(math.ceil(len(text) * progress)))
        shown = text[:visible]
        bbox = draw.textbbox((0, 0), shown, font=font)
        x = (self.w - (bbox[2] - bbox[0])) // 2
        alpha = int(max_alpha * min(1, progress * 1.4))
        draw.text((x + self.sc(2), self.sc(y) + self.sc(2)), shown, font=font, fill=self.rgba(BROWN, int(alpha * 0.16)))
        draw.text((x, self.sc(y)), shown, font=font, fill=(*color, alpha))

    def draw_particles(self, draw: ImageDraw.ImageDraw, t: float, center_y: float) -> None:
        if t < 0.50:
            return
        p = self.ease((t - 0.50) / 0.22)
        rng = random.Random(sum((idx + 1) * ord(ch) for idx, ch in enumerate(self.thing)) % 100000)
        for _ in range(30):
            angle = rng.uniform(-math.pi, 0)
            radius = rng.uniform(110, 270) * p
            x = self.cx + math.cos(angle) * radius
            y = center_y + math.sin(angle) * radius * 0.62
            r = rng.uniform(2.0, 5.0) * (0.6 + 0.4 * p)
            color = rng.choice([GOLD, SAGE, SAGE_DARK, SAGE_LIGHT])
            draw.ellipse((self.sc(x - r), self.sc(y - r), self.sc(x + r), self.sc(y + r)), fill=self.rgba(color, int(45 + 115 * p)))

    def draw_symbol(self, draw: ImageDraw.ImageDraw, t: float) -> None:
        p = self.ease((t - 0.08) / 0.45)
        bloom = self.ease((t - 0.44) / 0.28)
        subject = self.thing.lower()
        if any(word in subject for word in ["seed", "sprout", "flower", "plant", "tree"]):
            self.draw_seed_scene(draw, p, bloom)
        elif any(word in subject for word in ["rocket", "launch", "ship"]):
            self.draw_rocket_scene(draw, p, bloom)
        elif any(word in subject for word in ["brain", "mind", "agi", "agent", "ai"]):
            self.draw_mind_scene(draw, p, bloom)
        elif any(word in subject for word in ["book", "essay", "write", "story"]):
            self.draw_book_scene(draw, p, bloom)
        else:
            self.draw_generic_scene(draw, p, bloom)

    def draw_seed_scene(self, draw: ImageDraw.ImageDraw, p: float, bloom: float) -> None:
        base_y = 820
        soil_w = 600
        top = [(300 + i * 10, base_y - 70 * math.exp(-((300 + i * 10 - self.cx) / 160) ** 2) + 4 * math.sin(i / 4)) for i in range(61)]
        bottom = [(900 - i * 10, 1045 - 22 * math.sin(i / 60 * math.pi)) for i in range(61)]
        poly = top + bottom
        draw.polygon([self.pt(x, y) for x, y in poly], fill=self.rgba(SOIL, 252))
        draw.line([self.pt(x, y) for x, y in top], fill=self.rgba(BROWN), width=self.sc(5.8), joint="curve")
        seed = (self.cx - 20, base_y - 20)
        path = self.cubic((seed[0] + 25, seed[1] - 5), (self.cx + 35, seed[1] - 90), (self.cx - 15, 560), (self.cx, 410), 110)
        self.draw_line(draw, path[: max(2, int(len(path) * p))], self.rgba(SAGE_DARK), 13)
        self.draw_line(draw, path[: max(2, int(len(path) * p))], self.rgba(SAGE), 8)
        self.draw_leaf(draw, self.cx - 110, 610, 188 * p, 56 * p, -0.50)
        self.draw_leaf(draw, self.cx + 112, 600, 188 * p, 56 * p, 0.48)
        draw.ellipse((self.sc(seed[0] - 34), self.sc(seed[1] - 24), self.sc(seed[0] + 34), self.sc(seed[1] + 24)), fill=self.rgba(GOLD), outline=self.rgba(BROWN), width=self.sc(3))
        self.draw_green_bloom(draw, self.cx, 410, bloom)

    def draw_green_bloom(self, draw: ImageDraw.ImageDraw, cx: float, cy: float, bloom: float) -> None:
        if bloom <= 0:
            r = 12
            draw.ellipse((self.sc(cx - r), self.sc(cy - r), self.sc(cx + r), self.sc(cy + r)), fill=self.rgba(SAGE_LIGHT), outline=self.rgba(SAGE_DARK), width=self.sc(3))
            return
        p = self.ease(bloom)
        for i in range(10):
            angle = -math.pi / 2 + math.tau * i / 10
            self.draw_leaf(draw, cx + math.cos(angle) * 22 * p, cy + math.sin(angle) * 22 * p, 78 * (0.4 + 0.6 * p), 27 * (0.5 + 0.5 * p), angle, fill=[self.rgba(SAGE), self.rgba(SAGE_LIGHT), (*SAGE_DARK, 255)][i % 3])
        for i in range(7):
            angle = -math.pi / 2 + math.tau * (i + 0.5) / 7
            self.draw_leaf(draw, cx + math.cos(angle) * 12 * p, cy + math.sin(angle) * 12 * p, 48 * (0.45 + 0.55 * p), 18 * (0.55 + 0.45 * p), angle, fill=(*SAGE_LIGHT, 255), shadow=False)
        draw.ellipse((self.sc(cx - 18), self.sc(cy - 18), self.sc(cx + 18), self.sc(cy + 18)), fill=self.rgba(GOLD), outline=self.rgba(SAGE_DARK), width=self.sc(3))

    def draw_rocket_scene(self, draw: ImageDraw.ImageDraw, p: float, bloom: float) -> None:
        y = 790 - 360 * p
        cx = self.cx
        smoke_alpha = int(180 * (1 - p * 0.5))
        for i, r in enumerate([75, 58, 46, 34]):
            draw.ellipse((self.sc(cx - r - i * 36), self.sc(865 - r / 2), self.sc(cx + r - i * 36), self.sc(865 + r / 2)), fill=self.rgba(CREAM, smoke_alpha), outline=self.rgba(BROWN, 80))
            draw.ellipse((self.sc(cx - r + i * 36), self.sc(865 - r / 2), self.sc(cx + r + i * 36), self.sc(865 + r / 2)), fill=self.rgba(CREAM, smoke_alpha), outline=self.rgba(BROWN, 80))
        body = [(cx, y - 150), (cx + 58, y), (cx, y + 92), (cx - 58, y)]
        draw.polygon([self.pt(x, yy) for x, yy in body], fill=self.rgba(SAGE), outline=self.rgba(SAGE_DARK))
        draw.ellipse((self.sc(cx - 22), self.sc(y - 44), self.sc(cx + 22), self.sc(y),), fill=self.rgba(GOLD), outline=self.rgba(BROWN), width=self.sc(3))
        flame = [(cx - 22, y + 78), (cx, y + 155 + 40 * bloom), (cx + 22, y + 78)]
        draw.polygon([self.pt(x, yy) for x, yy in flame], fill=self.rgba(GOLD), outline=self.rgba(BROWN))

    def draw_mind_scene(self, draw: ImageDraw.ImageDraw, p: float, bloom: float) -> None:
        cx, cy = self.cx, 610
        radius = 70 + 110 * p
        draw.ellipse((self.sc(cx - radius), self.sc(cy - radius), self.sc(cx + radius), self.sc(cy + radius)), fill=self.rgba(SAGE, 80), outline=self.rgba(SAGE_DARK), width=self.sc(5))
        rng = random.Random(404)
        nodes = []
        for i in range(14):
            angle = math.tau * i / 14
            r = radius * rng.uniform(0.35, 0.95)
            nodes.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
        for a, b in zip(nodes, nodes[1:] + nodes[:1]):
            self.draw_line(draw, [a, b], self.rgba(SAGE_DARK, int(60 + 100 * p)), 2.5)
        for x, y in nodes:
            rr = 5 + 5 * bloom
            draw.ellipse((self.sc(x - rr), self.sc(y - rr), self.sc(x + rr), self.sc(y + rr)), fill=self.rgba(GOLD), outline=self.rgba(SAGE_DARK))
        self.draw_green_bloom(draw, cx, cy, bloom)

    def draw_book_scene(self, draw: ImageDraw.ImageDraw, p: float, bloom: float) -> None:
        cx, cy = self.cx, 720
        open_w = 170 + 120 * p
        draw.rounded_rectangle((self.sc(cx - open_w), self.sc(cy - 105), self.sc(cx), self.sc(cy + 105)), radius=self.sc(12), fill=self.rgba(CREAM, 235), outline=self.rgba(BROWN), width=self.sc(4))
        draw.rounded_rectangle((self.sc(cx), self.sc(cy - 105), self.sc(cx + open_w), self.sc(cy + 105)), radius=self.sc(12), fill=self.rgba(CREAM, 235), outline=self.rgba(BROWN), width=self.sc(4))
        for i in range(5):
            self.draw_line(draw, [(cx - open_w + 34, cy - 62 + i * 28), (cx - 26, cy - 50 + i * 20)], self.rgba(SAGE_DARK, 90), 2.2)
            self.draw_line(draw, [(cx + 26, cy - 50 + i * 20), (cx + open_w - 34, cy - 62 + i * 28)], self.rgba(SAGE_DARK, 90), 2.2)
        self.draw_green_bloom(draw, cx, cy - 145, bloom)

    def draw_generic_scene(self, draw: ImageDraw.ImageDraw, p: float, bloom: float) -> None:
        cx, cy = self.cx, 630
        r = 78 + 108 * p
        draw.ellipse((self.sc(cx - r), self.sc(cy - r), self.sc(cx + r), self.sc(cy + r)), fill=self.rgba(SAGE, 75), outline=self.rgba(SAGE_DARK), width=self.sc(5))
        for i in range(12):
            angle = math.tau * i / 12
            self.draw_leaf(draw, cx + math.cos(angle) * r * 0.68, cy + math.sin(angle) * r * 0.68, 46 * p, 14 * p, angle, fill=self.rgba(SAGE_LIGHT), shadow=False)
        self.draw_green_bloom(draw, cx, cy, bloom)

    def frame(self, frame_num: int) -> Image.Image:
        t = (frame_num - 1) / (self.frames - 1)
        img = self.base()
        draw = ImageDraw.Draw(img)
        self.draw_symbol(draw, t)
        self.draw_particles(draw, t, 410)
        self.draw_title(img, t)
        return img.resize((self.size, self.size), Image.Resampling.LANCZOS)

    def on_cream(self, img: Image.Image) -> Image.Image:
        bg = Image.new("RGBA", img.size, self.rgba(CREAM))
        bg.alpha_composite(img.convert("RGBA"))
        return bg.convert("RGB")

    def write(self) -> list[Path]:
        self.out.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(1, self.frames + 1):
            path = self.out / f"frame_{i:02d}.png"
            self.frame(i).save(path)
            paths.append(path)
        self.validate(paths)
        self.contact_sheet(paths).save(self.out / "preview_contact_sheet.png")
        self.previews(paths)
        return paths

    def contact_sheet(self, paths: list[Path]) -> Image.Image:
        thumb = 150
        pad = 10
        cols = 9
        rows = math.ceil(len(paths) / cols)
        sheet = Image.new("RGB", (cols * thumb + (cols + 1) * pad, rows * thumb + (rows + 1) * pad), CREAM)
        for idx, path in enumerate(paths):
            im = self.on_cream(Image.open(path)).resize((thumb, thumb), Image.Resampling.LANCZOS)
            x = pad + (idx % cols) * (thumb + pad)
            y = pad + (idx // cols) * (thumb + pad)
            sheet.paste(im, (x, y))
        return sheet

    def previews(self, paths: list[Path]) -> None:
        transparent = [Image.open(path).convert("RGBA").resize((840, 840), Image.Resampling.LANCZOS) for path in paths]
        cream = [self.on_cream(frame).resize((840, 840), Image.Resampling.LANCZOS) for frame in transparent]
        durations = [48] * (len(paths) - 1) + [1200]
        if self.background == "transparent":
            transparent[0].save(self.out / "preview_animation_transparent.webp", save_all=True, append_images=transparent[1:], duration=durations, loop=0, quality=92, method=6)
        cream[0].save(self.out / "preview_animation_on_cream.webp", save_all=True, append_images=cream[1:], duration=durations, loop=0, quality=92, method=6)

    def validate(self, paths: list[Path]) -> None:
        if len(paths) != self.frames:
            raise ValueError(f"Expected {self.frames} frames, got {len(paths)}")
        base = self.base().resize((self.size, self.size), Image.Resampling.LANCZOS)
        final = Image.open(paths[-1]).convert("RGBA")
        for path in paths:
            im = Image.open(path)
            if im.size != (self.size, self.size):
                raise ValueError(f"{path.name}: expected {self.size}x{self.size}, got {im.size}")
            if im.mode != "RGBA":
                raise ValueError(f"{path.name}: expected RGBA, got {im.mode}")
            corners = [im.getpixel(p)[3] for p in [(0, 0), (self.size - 1, 0), (0, self.size - 1), (self.size - 1, self.size - 1)]]
            if self.background == "transparent" and any(corners):
                raise ValueError(f"{path.name}: transparent corners expected, got {corners}")
            if self.background == "cream" and any(corner != 255 for corner in corners):
                raise ValueError(f"{path.name}: opaque background corners expected, got {corners}")
        for crop in [
            (0, 0, self.size, self.top_safe),
            (0, self.size - self.bottom_safe, self.size, self.size),
            (0, 0, self.side_safe, self.size),
            (self.size - self.side_safe, 0, self.size, self.size),
        ]:
            if self.background == "transparent" and final.crop(crop).getchannel("A").getbbox() is not None:
                raise ValueError(f"Final artwork enters safety margin {crop}")
            if self.background == "cream" and ImageChops.difference(base.crop(crop), final.crop(crop)).getbbox() is not None:
                raise ValueError(f"Final artwork enters safety margin {crop}")
        if final.getchannel("A").getbbox() is None:
            raise ValueError("Final frame has no visible content")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a generic high-quality Seed-style motion pack.")
    parser.add_argument("--thing", default="seed bloom", help="Generic thing to animate, e.g. 'rocket launch', 'AI mind', 'book opening'.")
    parser.add_argument("--title", default=TITLE_DEFAULT)
    parser.add_argument("--tagline", default=TAGLINE_DEFAULT)
    parser.add_argument("--out", type=Path, default=Path.cwd() / "output" / "seed_motion_pack")
    parser.add_argument("--size", type=int, default=1200)
    parser.add_argument("--frames", type=int, default=72)
    parser.add_argument("--background", choices=["auto", "transparent", "cream"], default="transparent")
    args = parser.parse_args()

    pack = MotionPack(args.out.resolve(), args.thing, args.title, args.tagline, args.size, args.frames, args.background)
    paths = pack.write()
    print(f"Wrote {len(paths)} {pack.background} frames and WebP previews to {pack.out}")


if __name__ == "__main__":
    main()
