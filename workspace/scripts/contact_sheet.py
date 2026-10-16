"""QA 스크린샷 여러 장을 한 장의 대조 시트로 묶는다.

사용법:
    python workspace/scripts/contact_sheet.py work/qa/ready --cols 6
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="+", help="QA 출력 폴더. 여러 개 주면 이어 붙인다")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--pick", help="폴더마다 이 이름의 PNG만 고른다(확장자 제외)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    folders = [ROOT / f for f in args.folder]
    files = []
    for folder in folders:
        got = sorted(p for p in folder.glob("*.png") if p.name != "contact.png")
        if args.pick:
            got = [p for p in got if p.stem == args.pick]
        files.extend(got)
    if not files:
        raise SystemExit(f"PNG가 없다: {', '.join(str(f) for f in folders)}")

    imgs = [Image.open(p).convert("RGB") for p in files]
    if args.scale != 1.0:
        imgs = [im.resize((int(im.width * args.scale), int(im.height * args.scale)), Image.NEAREST) for im in imgs]

    w, h = imgs[0].size
    label = 14
    cols = args.cols
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (w + 4), rows * (h + label + 4)), (40, 40, 48))
    d = ImageDraw.Draw(sheet)
    for i, (im, p) in enumerate(zip(imgs, files)):
        x = (i % cols) * (w + 4) + 2
        y = (i // cols) * (h + label + 4) + 2
        sheet.paste(im, (x, y))
        label_text = p.stem if len(folders) == 1 else f"{p.parent.name}/{p.stem}"
        d.text((x + 2, y + h + 1), label_text, fill=(255, 220, 120))

    out = ROOT / args.out if args.out else folders[0] / "contact.png"
    sheet.save(out)
    print(f"{out}  ({len(imgs)}장, {cols}열)")


if __name__ == "__main__":
    main()
