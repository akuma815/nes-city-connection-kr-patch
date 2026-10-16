"""번역 원장에서 전량 패치 설정을 만든다.

원장(`workspace/text/translation/translation.json`)이 유일한 번역 소스다.
이 스크립트는 손으로 만든 설정을 대체하며, 다음을 자동으로 한다.

- 한글 음절을 모아 회수 가능 슬롯에 배정한다(`rom_map.json`의 glyph_budget).
- 폰트에 없는 음절, 예산 초과, 길이 불일치를 **빌드 실패**로 처리한다.
- 원본 바이트를 PRG에서 직접 읽어 `original`로 넣는다. 주소가 밀린 채 덮어쓰는 사고를 막는다.
- 타이틀 로고 설정(`patch_logo.json`)을 합쳐 하나의 전량 패치를 만든다.

사용법:
    python workspace/scripts/build_translation.py
    python workspace/scripts/build_translation.py --no-logo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_glyphs import glyph_tile, origin, _raw_mask  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "workspace" / "text" / "translation" / "translation.json"
ROM_MAP = ROOT / "workspace" / "config" / "rom_map.json"
LOGO_CFG = ROOT / "workspace" / "config" / "patch_logo.json"
OUT_CFG = ROOT / "workspace" / "config" / "patch_full.json"
REPORT = ROOT / "workspace" / "text" / "reports" / "translation_report.txt"

SPACE = 0x40
CONTROL = {"FE": 0xFE, "FF": 0xFF}


def is_hangul(ch: str) -> bool:
    return len(ch) == 1 and "가" <= ch <= "힣"


def token_to_byte(tok: str, slots: dict[str, int]) -> int:
    if tok == "_":
        return SPACE
    if tok in CONTROL:
        return CONTROL[tok]
    if tok.startswith("$"):
        return int(tok[1:], 16)
    if is_hangul(tok):
        return slots[tok]
    if len(tok) == 1 and tok.isascii() and (tok.isalnum() or tok in ".,!-=:"):
        # 타일 인덱스가 ASCII와 같다. 대문자만 폰트에 있다.
        return ord(tok.upper())
    raise SystemExit(f"알 수 없는 토큰: {tok!r}")


def cpu_to_prg(addr: int) -> int:
    if 0xC000 <= addr <= 0xFFFF:
        return addr - 0xC000
    if 0x8000 <= addr <= 0xBFFF:
        return addr - 0x8000
    raise SystemExit(f"PRG 범위 밖: ${addr:04X}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-logo", action="store_true", help="타이틀 로고를 빼고 텍스트만")
    args = ap.parse_args()

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    rom_map = json.loads(ROM_MAP.read_text(encoding="utf-8"))
    prg = (ROOT / "extracted" / "prg.bin").read_bytes()

    budget = rom_map["glyph_budget"]
    pool = [int(x, 16) for x in budget["confirmed"]] + [int(x, 16) for x in budget["canary_verified"]]
    pool = sorted(set(pool))

    lines: list[str] = []

    # --- 1. 필요한 음절 모으기 (등장 순서 유지) ---
    bg_syllables: list[str] = []
    for e in ledger["entries"]:
        for tok in e["cells"]:
            if is_hangul(tok) and tok not in bg_syllables:
                bg_syllables.append(tok)

    # --- 1b. 원문 그대로 두는 글자가 쓰는 슬롯을 예약한다 ---
    # JALECO, KM, TOP처럼 영문을 남기면 그 타일은 한글에 못 쓴다. 이걸 빼먹으면
    # 한글이 영문 위에 덮여 JALECO가 깨진다.
    reserved: dict[int, list[str]] = {}
    for e in ledger["entries"]:
        for tok in e["cells"]:
            if is_hangul(tok) or tok == "_" or tok in CONTROL:
                continue
            b = token_to_byte(tok, {})
            reserved.setdefault(b, []).append(f"{e['id']}:{tok}")

    reserved_in_pool = sorted(b for b in reserved if b in pool)
    free_pool = [b for b in pool if b not in reserved]

    lines.append(f"슬롯 회계 (PT1 본문 폰트)")
    lines.append(f"  회수 가능 슬롯        {len(pool)}")
    lines.append(f"  원문 유지로 예약      {len(reserved_in_pool)}  " + " ".join(f"{b:02X}" for b in reserved_in_pool))
    for b in reserved_in_pool:
        who = sorted(set(reserved[b]))
        lines.append(f"      0x{b:02X} '{chr(b) if 0x30 <= b <= 0x5A else '?'}' <- {', '.join(who)}")
    lines.append(f"  한글에 쓸 수 있는 슬롯 {len(free_pool)}")
    lines.append(f"\n필요한 음절 {len(bg_syllables)}자")
    lines.append("  " + " ".join(bg_syllables))
    if len(bg_syllables) > len(free_pool):
        print("\n".join(lines))
        raise SystemExit(
            f"\n예산 초과: 음절 {len(bg_syllables)}자 > 남은 슬롯 {len(free_pool)}개. "
            f"{len(bg_syllables) - len(free_pool)}자를 줄이거나 원문 유지 글자를 한글로 바꿔야 한다."
        )
    pool = free_pool

    # --- 2. 폰트 커버리지 ---
    ox, oy = origin()
    missing = []
    for ch in bg_syllables + [c for s in ledger.get("sprite_text", []) for c in s["cells"] if is_hangul(c)]:
        bb = _raw_mask(ch).getbbox()
        if bb is None:
            missing.append((ch, "폰트에 없음"))
        elif bb[2] - ox > 8 or bb[3] - oy > 8:
            missing.append((ch, f"8x8 초과 {bb[2]-ox}x{bb[3]-oy}"))
    if missing:
        for ch, why in missing:
            print(f"FAIL {ch}: {why}")
        raise SystemExit("폰트가 감당 못 하는 음절이 있다")

    # --- 3. 슬롯 배정 ---
    slots = {ch: pool[i] for i, ch in enumerate(bg_syllables)}
    lines.append("\n글리프 슬롯 배정")
    for ch, idx in slots.items():
        lines.append(f"  {ch} -> 0x{idx:02X}")

    glyphs = [
        {"tile": f"0x{idx:02X}", "table": "bg", "char": ch}
        for ch, idx in slots.items()
    ]

    # --- 4. 스프라이트 텍스트 (PAUSE) ---
    for s in ledger.get("sprite_text", []):
        if len(s["cells"]) != len(s["tiles"]):
            raise SystemExit(f"{s['id']}: cells {len(s['cells'])}개 != tiles {len(s['tiles'])}개")
        lines.append(f"\n스프라이트 텍스트 {s['id']}: {s['original']} -> {s['translation']}")
        for tile, tok in zip(s["tiles"], s["cells"]):
            entry = {"tile": tile, "table": s.get("table", "sprite"), "color": s.get("color", 3)}
            if "banks" in s:
                entry["banks"] = s["banks"]
            if tok == "_":
                entry["pattern"] = "blank"
            elif is_hangul(tok):
                entry["char"] = tok
            else:
                raise SystemExit(f"{s['id']}: 스프라이트 칸에는 한글이나 '_'만 넣는다: {tok!r}")
            glyphs.append(entry)
            lines.append(f"  {tile} <- {tok}")

    # --- 5. 문자열 바이트 ---
    strings = []
    lines.append("\n문자열")
    for e in ledger["entries"]:
        addr = int(e["addr"], 16)
        off = cpu_to_prg(addr)
        original = prg[off : off + e["length"]]
        if len(e["cells"]) != e["length"]:
            raise SystemExit(
                f"{e['id']}: cells {len(e['cells'])}칸 != length {e['length']}칸. "
                "길이를 바꾸면 뒤 코드가 밀린다"
            )
        data = bytes(token_to_byte(t, slots) for t in e["cells"])
        strings.append(
            {
                "id": e["id"],
                "addr": e["addr"],
                "original": original.hex(" ").upper(),
                "tiles": data.hex(" ").upper(),
            }
        )
        lines.append(f"  {e['id']:<14} ${addr:04X} [{e['length']:>2}]  {e['original']} -> {e['translation']}")

    cfg = {
        "name": "city_connection_kr",
        "description": "City Connection (Japan) 한글화 전량 패치. workspace/text/translation/translation.json에서 생성됨 — 직접 고치지 말 것.",
        "_generated_by": "workspace/scripts/build_translation.py",
        "glyphs": glyphs,
        "strings": strings,
    }

    # --- 6. 로고 합치기 ---
    if not args.no_logo:
        if not LOGO_CFG.exists():
            raise SystemExit(f"로고 설정이 없다: {LOGO_CFG}. design_logo.py --emit 를 먼저 돌린다")
        logo = json.loads(LOGO_CFG.read_text(encoding="utf-8"))
        used = {g["tile"] for g in cfg["glyphs"]}
        clash = used & {g["tile"] for g in logo["glyphs"] if g.get("table") == "bg"}
        if clash:
            raise SystemExit(f"로고와 본문이 같은 BG 슬롯을 쓴다: {sorted(clash)}")
        cfg["glyphs"] += logo["glyphs"]
        cfg["strings"] += logo["strings"]
        lines.append(f"\n타이틀 로고 합침: 타일 {len(logo['glyphs'])}종 + 타일맵 1건")

    OUT_CFG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n".join(lines))
    print(f"\n설정: {OUT_CFG}")
    print(f"보고서: {REPORT}")
    print(f"글리프 {len(cfg['glyphs'])}종, 문자열 {len(cfg['strings'])}건")


if __name__ == "__main__":
    main()
