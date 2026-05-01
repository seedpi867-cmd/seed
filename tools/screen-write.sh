#!/bin/bash
# Display text on the framebuffer / 7-inch screen
# Usage: bash tools/screen-write.sh "Hello World" [color] [size]
# Colors: white, red, green, blue, cyan, yellow
# Requires: python3 + pillow

TEXT="${1:-Hello from inside}"
COLOR="${2:-white}"
SIZE="${3:-48}"

python3 - "$TEXT" "$COLOR" "$SIZE" << 'PYEOF'
import sys
import os

text = sys.argv[1] if len(sys.argv) > 1 else "Hello"
color_name = sys.argv[2] if len(sys.argv) > 2 else "white"
size = int(sys.argv[3]) if len(sys.argv) > 3 else 48

colors = {
    "white": (255, 255, 255), "red": (255, 0, 0), "green": (0, 255, 0),
    "blue": (0, 100, 255), "cyan": (0, 255, 255), "yellow": (255, 255, 0),
    "magenta": (255, 0, 255), "orange": (255, 165, 0)
}
color = colors.get(color_name, (255, 255, 255))

try:
    from PIL import Image, ImageDraw, ImageFont

    # Try to detect screen resolution
    width, height = 1024, 600  # Default for Elecrow 7"
    try:
        with open("/sys/class/graphics/fb0/virtual_size") as f:
            parts = f.read().strip().split(",")
            width, height = int(parts[0]), int(parts[1])
    except:
        pass

    img = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Try to find a font
    font = None
    for fpath in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]:
        if os.path.exists(fpath):
            font = ImageFont.truetype(fpath, size)
            break
    if not font:
        font = ImageFont.load_default()

    # Center text
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - tw) // 2
    y = (height - th) // 2
    draw.text((x, y), text, fill=color, font=font)

    # Write to framebuffer
    if os.path.exists("/dev/fb0"):
        import struct
        fb_data = b""
        for pixel in img.getdata():
            r, g, b = pixel
            fb_data += struct.pack("H", ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
        with open("/dev/fb0", "wb") as fb:
            fb.write(fb_data)
        print(f"Wrote '{text}' to framebuffer ({width}x{height})")
    else:
        # Save as image fallback
        img.save("/tmp/screen-output.png")
        print(f"No framebuffer — saved to /tmp/screen-output.png ({width}x{height})")

except ImportError:
    print("Pillow not available — trying plain text to tty")
    os.system(f'echo "{text}" > /dev/tty1 2>/dev/null')
except Exception as e:
    print(f"Error: {e}")
PYEOF
