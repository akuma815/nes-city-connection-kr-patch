"""패치 설정(JSON)을 읽어 CHR 글리프와 PRG 문자열을 반영한 ROM을 만든다.

원칙:
- 문자열은 **원본 바이트가 설정과 일치할 때만** 덮어쓴다. 길이도 강제로 같아야 한다.
- 글리프는 PT1(`$1000`)의 같은 인덱스에 **두 뱅크 모두** 쓴다. 한쪽만 쓰면 스테이지마다 깨진다.
- 마지막에 원본과 diff를 떠서 **선언한 오프셋 외의 변경이 0**인지 검사한다(Expected Write).

사용법:
    python workspace/scripts/build_patch.py workspace/config/patch_poc.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_glyphs import glyph_tile  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EXTRACTED = ROOT / "extracted"
ORIGINAL = ROOT / "original" / "City Connection (Japan).nes"

PRG_CPU_BASE = 0x8000
CHR_BANK_SIZE = 8192
PT1_OFFSET = 4096
TILE_BYTES = 16

# 제어값과 겹치는 인덱스에는 글리프를 넣을 수 없다.
FORBIDDEN_TILES = {0xFE, 0xFF}
# 회수 금지: 숫자와 게이지 블록.
PROTECTED_TILES = set(range(0x30, 0x40))

PATTERNS = {
    # 회수 후보 타일이 실제로 배경에 쓰이는지 보는 카나리아. 눈에 확 띄어야 한다.
    "canary": [0b10101010, 0b01010101] * 4,
    "solid": [0xFF] * 8,
    "blank": [0x00] * 8,
}


def cpu_to_prg(addr: int) -> int:
    if 0xC000 <= addr <= 0xFFFF:
        return addr - 0xC000
    if 0x8000 <= addr <= 0xBFFF:
        return addr - 0x8000
    raise SystemExit(f"PRG 범위 밖 주소: ${addr:04X}")


def parse_bytes(s: str) -> bytes:
    return bytes(int(t, 16) for t in s.split())


def rows_to_tile(rows: list[int], color: int = 3) -> bytes:
    """8바이트 1bpp 행 비트맵을 NES 2bpp 타일로. color는 1~3 중 하나를 칠한다.

    원본 폰트는 값 3, 타이틀 로고 본체는 값 2를 쓴다. 색을 맞춰야 팔레트를 안 건드린다.
    """
    if color not in (1, 2, 3):
        raise SystemExit(f"color는 1~3이어야 한다: {color}")
    plane0 = bytes(rows) if color & 1 else bytes(8)
    plane1 = bytes(rows) if color & 2 else bytes(8)
    return plane0 + plane1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--out-dir", default="build")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    header = bytearray((EXTRACTED / "header.bin").read_bytes())
    prg = bytearray((EXTRACTED / "prg.bin").read_bytes())
    chr_ = bytearray((EXTRACTED / "chr.bin").read_bytes())
    banks = len(chr_) // CHR_BANK_SIZE

    prg_expected: set[int] = set()
    chr_expected: set[int] = set()
    log: list[str] = []

    # --- 글리프 ---
    for g in cfg.get("glyphs", []):
        tile = int(g["tile"], 16)
        # table: "bg" = PT1($1000, 본문 폰트), "sprite" = PT0($0000, 자동차·로고)
        table = g.get("table", "bg")
        if table not in ("bg", "sprite"):
            raise SystemExit(f"table은 bg 또는 sprite여야 한다: {table}")
        pt_offset = PT1_OFFSET if table == "bg" else 0
        if table == "bg":
            if tile in FORBIDDEN_TILES:
                raise SystemExit(f"타일 0x{tile:02X}는 제어값과 겹쳐 글리프를 넣을 수 없다")
            if tile in PROTECTED_TILES and not g.get("force"):
                raise SystemExit(f"타일 0x{tile:02X}는 보호 범위(숫자/게이지)다. force 필요")
        if "char" in g:
            data = glyph_tile(g["char"])
            what = f"'{g['char']}'"
        elif "pattern" in g:
            data = rows_to_tile(PATTERNS[g["pattern"]], g.get("color", 3))
            what = f"패턴 {g['pattern']}"
        elif "rows" in g:
            # design_logo.py가 만든 8바이트 1bpp 행 비트맵.
            raw = bytes.fromhex(g["rows"])
            if len(raw) != 8:
                raise SystemExit(f"rows는 8바이트여야 한다: {g}")
            data = rows_to_tile(list(raw), g.get("color", 3))
            what = f"직접 지정 비트맵(색 {g.get('color', 3)})"
        elif "bytes" in g:
            # 이미 2bpp로 만들어진 타일. 여러 색을 쓰는 로고 그림에 쓴다.
            data = bytes.fromhex(g["bytes"])
            if len(data) != TILE_BYTES:
                raise SystemExit(f"bytes는 {TILE_BYTES}바이트여야 한다: {g}")
            what = "2bpp 타일"
        else:
            raise SystemExit(f"글리프 항목에 char, pattern, rows 중 하나가 필요하다: {g}")
        target_banks = g.get("banks")  # 예: [0] 이면 뱅크 0에만 쓴다
        bank_list = target_banks if target_banks is not None else list(range(banks))
        for b in bank_list:
            off = b * CHR_BANK_SIZE + pt_offset + tile * TILE_BYTES
            chr_[off : off + TILE_BYTES] = data
            chr_expected.update(range(off, off + TILE_BYTES))
        where = f"뱅크 {','.join(str(b) for b in bank_list)}"
        log.append(f"  CHR {table.upper():<6} 타일 0x{tile:02X} <- {what}  ({where})")

    # --- 문자열 ---
    for s in cfg.get("strings", []):
        addr = int(s["addr"], 16)
        off = cpu_to_prg(addr)
        want = parse_bytes(s["original"])
        new = parse_bytes(s["tiles"])
        if len(new) != len(want):
            raise SystemExit(
                f"{s['id']}: 길이가 다르다 (원본 {len(want)} vs 새 값 {len(new)}). "
                "코드가 밀리므로 길이는 반드시 같아야 한다"
            )
        have = bytes(prg[off : off + len(want)])
        if have != want:
            raise SystemExit(
                f"{s['id']} @ ${addr:04X}: 원본 바이트 불일치\n"
                f"  기대 {want.hex(' ')}\n  실제 {have.hex(' ')}"
            )
        prg[off : off + len(new)] = new
        prg_expected.update(range(off, off + len(new)))
        log.append(f"  PRG ${addr:04X} [{len(new)}] {want.hex(' ')} -> {new.hex(' ')}   ({s['id']})")

    # --- 조립 ---
    header[4] = len(prg) // 16384
    header[5] = len(chr_) // CHR_BANK_SIZE
    rom = bytes(header) + bytes(prg) + bytes(chr_)

    # --- Expected Write 검사 ---
    original = ORIGINAL.read_bytes()
    prg_base = 16
    chr_base = 16 + len(prg)
    allowed = {prg_base + o for o in prg_expected} | {chr_base + o for o in chr_expected}
    changed = {i for i in range(min(len(rom), len(original))) if rom[i] != original[i]}
    unexpected = changed - allowed
    missing = allowed - changed  # 값이 원래와 같아 결과적으로 안 바뀐 자리(정상일 수 있음)

    out = ROOT / args.out_dir / f"{cfg['name']}.nes"
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"[{cfg['name']}] {cfg.get('description','')}")
    for line in log:
        print(line)
    print(f"\n허용 변경 바이트 : {len(allowed)}")
    print(f"실제 변경 바이트 : {len(changed)}")
    print(f"허용 밖 변경     : {len(unexpected)}  {'PASS' if not unexpected else 'FAIL'}")
    if missing:
        print(f"(참고) 선언했으나 값이 같아 변경되지 않은 바이트 {len(missing)}개")
    if unexpected:
        for i in sorted(unexpected)[:20]:
            print(f"  0x{i:05X}: 원본 0x{original[i]:02X} -> 0x{rom[i]:02X}")
        raise SystemExit(1)

    out.write_bytes(rom)
    print(f"\n출력    : {out}")
    print(f"크기    : {len(rom)}")
    print(f"SHA-256 : {hashlib.sha256(rom).hexdigest()}")


if __name__ == "__main__":
    main()
