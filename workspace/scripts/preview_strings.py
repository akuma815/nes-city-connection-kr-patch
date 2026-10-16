"""번역 원장의 각 문자열을 패치된 ROM의 폰트로 렌더해 한 장에 모은다.

게임오버·보너스·엔딩·일시정지처럼 플레이로 도달하기 어려운 화면을
게임을 돌리지 않고 눈으로 확인하기 위한 도구다.
실제 화면 배치(좌표·팔레트)까지 보증하지는 않는다. 글자가 맞는지만 본다.

사용법:
    python workspace/scripts/preview_strings.py build/city_connection_kr.nes
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "workspace" / "text" / "translation" / "translation.json"
OUT = ROOT / "work"

PREVIEW = [(16, 16, 24), (110, 110, 130), (200, 140, 180), (255, 255, 255)]
SCALE = 3


def load_rom(path: Path) -> tuple[bytes, bytes]:
    data = path.read_bytes()
    prg_size = data[4] * 16384
    chr_size = data[5] * 8192
    return data[16 : 16 + prg_size], data[16 + prg_size : 16 + prg_size + chr_size]


def decode(chr_: bytes, base: int, tile: int) -> list[list[int]]:
    off = base + tile * 16
    raw = chr_[off : off + 16]
    return [
        [((raw[y] >> (7 - x)) & 1) | (((raw[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)]
        for y in range(8)
    ]


def render_row(chr_: bytes, base: int, tiles: list[int]) -> Image.Image:
    img = Image.new("RGB", (len(tiles) * 8, 8), PREVIEW[0])
    px = img.load()
    for i, t in enumerate(tiles):
        if t in (0xFE, 0xFF):
            continue
        cell = decode(chr_, base, t)
        for y in range(8):
            for x in range(8):
                px[i * 8 + x, y] = PREVIEW[cell[y][x]]
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", help="프로젝트 루트 기준 .nes 경로")
    args = ap.parse_args()

    prg, chr_ = load_rom(ROOT / args.rom)
    led = json.loads(LEDGER.read_text(encoding="utf-8"))

    rows: list[tuple[str, Image.Image]] = []
    for e in led["entries"]:
        addr = int(e["addr"], 16)
        off = addr - (0xC000 if addr >= 0xC000 else 0x8000)
        data = list(prg[off : off + e["length"]])
        # 0xFE로 줄을 나눠 보여 준다. 실제 화면에서도 줄바꿈이다.
        line: list[int] = []
        parts: list[list[int]] = []
        for b in data:
            if b in (0xFE, 0xFF):
                if line:
                    parts.append(line)
                    line = []
                continue
            line.append(b)
        if line:
            parts.append(line)
        for n, part in enumerate(parts):
            label = e["id"] if n == 0 else f"{e['id']}({n + 1})"
            rows.append((label, render_row(chr_, 4096, part)))

    # 스프라이트 텍스트는 PT0에 있다.
    for s in led.get("sprite_text", []):
        tiles = [int(t, 16) for t in s["tiles"]]
        rows.append((s["id"] + " (PT0)", render_row(chr_, 0, tiles)))

    pad = 4
    label_w = 150
    width = label_w + max(im.width for _, im in rows) * SCALE + pad * 2
    height = sum(im.height * SCALE + pad for _, im in rows) + pad
    sheet = Image.new("RGB", (width, height), (28, 28, 36))
    d = ImageDraw.Draw(sheet)
    y = pad
    for label, im in rows:
        d.text((6, y + 4), label, fill=(255, 220, 120))
        sheet.paste(im.resize((im.width * SCALE, im.height * SCALE), Image.NEAREST), (label_w, y))
        y += im.height * SCALE + pad

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "string_preview.png"
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
