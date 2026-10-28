import glob, os, textwrap
from PIL import Image, ImageDraw, ImageFont
F = next((p for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/TTF/DejaVuSansMono.ttf", "/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf"] if os.path.exists(p)), None)
font = ImageFont.truetype(F, 15) if F else ImageFont.load_default()
os.makedirs("report/figures", exist_ok=True)
for p in sorted(glob.glob("report/logs/*.txt")):
    lines = []
    for l in open(p, errors="replace").read().rstrip().split("\n"):
        lines += textwrap.wrap(l, 110, subsequent_indent="  ") or [""]
    if len(lines) > 26:
        lines = lines[:2] + ["..."] + lines[-23:]
    W = max(len(l) for l in lines) * 9 + 40
    H = len(lines) * 20 + 50
    im = Image.new("RGB", (W, H), "#1e1e1e")
    d = ImageDraw.Draw(im)
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        d.ellipse((14 + i * 22, 12, 28 + i * 22, 26), fill=c)
    for i, l in enumerate(lines):
        d.text((20, 40 + i * 20), l, font=font, fill="#7ee787" if i == 0 else "#d4d4d4")
    im.save("report/figures/" + os.path.basename(p)[:-4] + ".png")
