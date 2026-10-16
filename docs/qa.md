# QA 기록과 계획

## 환경

- Mesen 2 (`H:\Mesen\Mesen.exe`), 헤드리스 테스트 러너 모드
- 실행 도구: `workspace/scripts/run_qa.py` → `workspace/tests/qa_capture.lua.tmpl`
- 실기 확인은 아직 없음

전제: Mesen 설정의 `Debug > ScriptWindow > AllowIoOsAccess = true`.
원본 설정은 `H:\Mesen\settings.json.bak-korproj`에 백업돼 있다.

## 실행 기록 (2026-08-12)

| 실행 | ROM | 프레임 | 목적 | 결과 |
| --- | --- | ---: | --- | --- |
| `work/qa/attract` | 원본 | 20,000 | 어트랙트 커버리지 | 타이틀·데모·게임오버 관측 |
| `work/qa/play` | 원본 | 20,000 | 입력 있는 커버리지 | 1스테이지만 도달 |
| `work/qa/ready` | `poc_ready` | 1,000 | **`준비` 표시 확인** | **PASS** |
| `work/qa/canary` | `canary_tiles` | 1,000 | 회수 후보 검증 | `0x3F` = 하늘로 판명 |
| `work/qa/canary2` | `canary_blank` | 6,000 | `0x3F` 제외 재검증 | 전 화면 미출현 |
| `work/qa/stage0`~`5` | `canary_blank` | 각 1,200 | 스테이지 강제 이동 확인 | 6개 도시 로드 성공 |
| `work/qa/orig_stage0`~`5` | 원본 | 각 3,000 | 전 도시 타일 집계 | 후보 11슬롯 PT1 사용 0회 |
| `work/qa/canary_s0`~`s5` | `canary_blank`(11슬롯) | 각 3,000 | **전 도시 카나리아** | **PASS — 18장 전부 미출현** |

## 최소 PoC (docs/decisions.md D-003) — 통과

- [x] 무변경 재조립 결과가 원본과 바이트 동일하다. (`build_rom.py --verify`)
- [x] `READY` → `준비` 치환 후 스테이지 시작 화면에 정상 표시된다. (`work/qa/ready/f00620.png`)
- [x] Expected Write: 선언한 오프셋 밖 변경 0바이트.
- [x] 글리프를 넣은 타일이 다른 화면에 잘못 나타나지 않는다. (11슬롯 카나리아, 6개 도시)
- [x] 뱅크가 바뀌는 뒤 스테이지에서도 깨지지 않는다. (스테이지 2·4·5 = 뱅크 1, 전부 확인)

## 커버리지 확장 — 완료 (2026-08-12)

스테이지 인덱스 변수 `$A0`을 찾아 6개 도시를 전부 로드했다(`docs/decisions.md` D-007).

```powershell
foreach ($n in 0..5) {
  python .\workspace\scripts\run_qa.py build/canary_blank.nes --out work/qa/canary_s$n --frames 3000 --poke A0=$n
}
python .\workspace\scripts\contact_sheet.py work/qa/canary_s0 work/qa/canary_s1 work/qa/canary_s2 work/qa/canary_s3 work/qa/canary_s4 work/qa/canary_s5 --cols 6 --out work/qa/canary_all_stages.png
```

결과: 6개 도시 18장 전부 체커보드 미출현 → **회수 가능 슬롯 38개 확정.**

## 전량 번역 QA (2026-08-12)

| 검사 | 도구 | 결과 |
| --- | --- | --- |
| 무변경 왕복 | `build_rom.py --verify` | **PASS** |
| 문자열 전수 감사 | `audit_strings.py` | **PASS** — 미등록 0 |
| 슬롯 예산·길이·폰트 커버리지 | `build_translation.py` | **PASS** — 한글 23자 / 슬롯 23 |
| Expected Write | `build_patch.py` | **PASS** — 허용 밖 변경 0바이트 |
| 전 문자열 정적 렌더 | `preview_strings.py` | **PASS** — `work/string_preview.png` |
| 어트랙트 20,000프레임 | `run_qa.py` | **PASS** — `work/qa/final/contact.png` |
| xdelta 왕복 | `make_dist.py` + 수동 적용 | **PASS** — SHA 일치 |

### QA가 잡은 결함

**`1 PLAYER` 간주 화면이 `1 PLA인용`으로 깨졌다.**
`$8B48`의 ` PLAYER`를 미사용 데이터로 잘못 판단해 `Y`·`R` 타일을 한글에 배정한 탓이다.
정적 조사로는 못 잡았고 20,000프레임 스윕의 스크린샷에서 발견했다.

재발 방지로 `audit_strings.py`를 만들었다. PPUDATA에 쓰는 모든 루프를 찾아
원장이 그 주소를 덮는지 대조하고, 안 덮으면 `**미등록**`으로 표시한다.

## 남은 QA 범위

### 정적으로만 확인한 화면 (실제 플레이 미도달)

- [ ] 게임 오버 — `게임 오버` + `PLAYER 1`
- [ ] 워프 보너스 — `워프보너스` / `기름✳1000` / `점`
- [ ] 일시정지 — `일시정지` (PT0 스프라이트)
- [ ] 엔딩 — `이제 모두` / `달렸다` / `기름 ✳100`

`preview_strings.py`로 글자는 확인했으나 화면상 좌표·팔레트는 보증하지 않는다.

### 화면별

- [ ] 타이틀: 로고, 메뉴(스프라이트 8개 한계), 저작권 줄, 커서 이동
- [ ] 1인용 / 2인용 진입
- [ ] 플레이 중 HUD(거리·연료)
- [ ] `READY` / `GAME OVER`
- [ ] 워프 보너스, 오일 점수 표시
- [ ] `PAUSE` 표시
- [ ] 엔딩 문구 (엔딩 도달 경로 미확보)

### 최종

- [ ] 회수한 타일 인덱스가 배경으로 오출력되지 않음
- [ ] QA한 빌드의 SHA-256 기록
- [ ] 실기 또는 다른 에뮬레이터 교차 확인

## 다시 돌리는 법

```powershell
python .\workspace\scripts\run_qa.py build/poc_ready.nes --out work/qa/ready --frames 1000 --shots "500:1000:20"
python .\workspace\scripts\contact_sheet.py work/qa/ready --cols 6
python .\workspace\scripts\analyze_tile_usage.py work/qa/attract work/qa/play
```

`analyze_tile_usage.py`에는 **원본 ROM 실행 결과만** 넣는다.
패치 빌드 결과를 섞으면 우리가 넣은 글리프 사용량이 배경 사용으로 잘못 집계된다.
