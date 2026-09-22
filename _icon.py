# 生成主屏幕图标 icon-512.png / icon-180.png。
# 用 PIL 直接画，不引无头浏览器——图标是静态的，没必要绕那一圈。
import pathlib
from PIL import Image, ImageDraw, ImageFont

BASE = pathlib.Path(__file__).parent
TOP, BOT = (36, 58, 96), (8, 14, 28)      # 背景竖向渐变
ACC = (122, 168, 255)                      # "6" 用主题蓝
FONT = r"C:\Windows\Fonts\seguisb.ttf"     # Segoe UI Semibold，纯 ASCII 够用

def gradient(size):
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        # 上浅下深，再叠一点从上方打下来的高光
        r = int(TOP[0] + (BOT[0] - TOP[0]) * t)
        g = int(TOP[1] + (BOT[1] - TOP[1]) * t)
        b = int(TOP[2] + (BOT[2] - TOP[2]) * t)
        for x in range(size):
            d = ((x - size / 2) ** 2 + (y - size * 0.32) ** 2) ** .5 / (size * .78)
            k = max(0.0, 1 - d) ** 2 * 0.28
            px[x, y] = (min(255, int(r + 26 * k)), min(255, int(g + 34 * k)), min(255, int(b + 46 * k)))
    return img

def make(size):
    img = gradient(size)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, int(size * 0.34))
    # "CET" 白、"6" 蓝，整体居中——两个字号一样，靠颜色分开
    parts = [("CET", (238, 244, 255), f), ("6", ACC, f)]
    widths = [d.textlength(t, font=fo) for t, _, fo in parts]
    total = sum(widths)
    x = size / 2 - total / 2
    for (t, col, fo), w in zip(parts, widths):
        d.text((x, size * 0.5), t, font=fo, fill=col, anchor="lm")
        x += w
    out = BASE / ("icon-%d.png" % size)
    img.save(out)
    return out

for s in (512, 180):
    print("写出", make(s).name)
