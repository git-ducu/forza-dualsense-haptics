# forza-dualsense-haptics (DHE)

Forza Horizon 텔레메트리 기반 DualSense 햅틱 엔진

```
UDP 텔레메트리 → 차량 상태 정규화 → 햅틱 판단 레이어 → DualSense HID 출력
```

---

## 기능

- **적응형 트리거** — 페달 저항, ABS/트랙션 진동, 기어 킥, 레브 리미터 펄스
- **햅틱 오디오 엔진** — 4-bus 음향 믹서 (노면·차체·엔진·이벤트), 주파수 대역별 렌더링
- **실시간 GUI** — 라이브 계기판, 슬라이더 튜닝, 프리셋 관리 (내보내기/가져오기)
- **HID 직접 통신** — 외부 드라이버 불필요, USB/BT 자동 감지 + 자동 재연결

---

## 요구사항

- Windows 10/11 (x64)
- Python 3.13 x64 권장 (소스 실행 시 3.10+ 호환)
- DualSense 컨트롤러 (USB 또는 BT)
- Forza Horizon 4/5/6 — Data Out 활성화 (UDP)

---

## 빠른 시작 (릴리스 zip)

1. [Releases](../../releases)에서 최신 zip 다운로드
2. 압축 해제 → `DHE.exe` 실행
3. Forza: Settings → HUD → Data Out `ON`, IP `127.0.0.1`, Port `5300`
4. 주행 시작 — 트리거 피드백 즉시 활성화

---

## 소스 실행

```bash
# 의존성 설치
setup_vendor.bat

# 실행
run_dhe.bat
```

---

## 빌드 (PyInstaller)

```bash
pip install pyinstaller
build.bat          # → dist/DHE/DHE.exe
release.bat        # → DHE_v1.00.zip
```

---

## 프로젝트 구조

```
app.py              진입점
config/             설정 저장, 프리셋 관리
dsio/               HID 출력, 햅틱 렌더러, 트리거 코덱
telemetry/          UDP 수신, 차량 모델, 트리거 정책
runtime/            이벤트 루프, 로깅, 진단
ui/                 PySide6 대시보드
vendor/             번들 의존성 (git 미포함)
```

---

## Forza Data Out 설정

| 항목 | 값 |
|------|------|
| Data Out | ON |
| IP Address | 127.0.0.1 |
| Port | 5300 |

포트는 앱 내 Telemetry Connection 섹션에서 변경 가능합니다.

---

## 아키텍처

```
UDP 텔레메트리
→ 패킷 디코더
→ 정규화된 차량 상태
→ 트리거/햅틱 리졸버
→ DualSense HID 출력 라이터
→ (선택) 햅틱 오디오 렌더러
```

## 기술 노트

- dataclass 기반 텔레메트리 모델
- 결정론적 HID 리포트 패킹 (트리거 출력)
- 백그라운드 컨트롤러 라이터 + 재연결 처리
- 프리셋 기반 튜닝 저장소, 원자적 JSON 쓰기
- 버스 믹싱 + 리미터 단계의 오디오-햅틱 경로

---

## 라이선스

[Apache-2.0](LICENSE)

---

<details>
<summary>English</summary>

## forza-dualsense-haptics (DHE)

A telemetry-driven haptic engine for DualSense controllers with Forza Horizon.

```
UDP telemetry → normalized vehicle state → haptic decision layer → DualSense HID output
```

### Features

- **Trigger Feedback** — Pedal resistance, ABS/traction vibration, gear kick, rev limiter pulse
- **Haptic Audio Engine** — 4-bus mixer (surface · vehicle · engine · event), per-band rendering
- **Real-time GUI** — Live dashboard, slider tuning, preset management (export/import)
- **Direct HID** — No external driver needed, USB/BT auto-detect + reconnect

### Requirements

- Windows 10/11 (x64)
- Python 3.13 x64 recommended (3.10+ compatible from source)
- DualSense controller (USB or BT)
- Forza Horizon 4/5/6 — Data Out enabled (UDP)

### Quick Start (Release zip)

1. Download latest zip from [Releases](../../releases)
2. Extract → run `DHE.exe`
3. Forza: Settings → HUD → Data Out `ON`, IP `127.0.0.1`, Port `5300`
4. Start driving — trigger feedback activates immediately

### Source

```bash
setup_vendor.bat
run_dhe.bat
```

### Build (PyInstaller)

```bash
pip install pyinstaller
build.bat          # → dist/DHE/DHE.exe
release.bat        # → DHE_v1.00.zip
```

### Architecture

```
UDP telemetry
→ packet decoder
→ normalized vehicle state
→ trigger/haptic resolver
→ DualSense HID output writer
→ optional haptic audio renderer
```

### Engineering Notes

- Typed telemetry model using dataclasses
- Deterministic HID report packing for trigger output
- Background controller writer with reconnect handling
- Preset-based tuning store with atomic JSON writes
- Optional audio-haptic path with bus mixing and limiter stage

### License

[Apache-2.0](LICENSE)

</details>
