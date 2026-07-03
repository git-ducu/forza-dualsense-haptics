# forza-dualsense-haptics (DHE)

Forza Horizon 텔레메트리 기반 DualSense 햅틱 엔진
Telemetry-driven DualSense haptic engine for Forza Horizon

```
UDP telemetry → vehicle state → haptic decision → DualSense HID output
```

---

## 기능 / Features

- **적응형 트리거 / Adaptive Triggers** — 페달 저항, ABS 진동, 기어 킥, 레브 리미터
- **햅틱 오디오 엔진 / Haptic Audio** — 4-bus 음향 믹서 (노면·차체·엔진·이벤트)
- **실시간 GUI / Real-time GUI** — 라이브 계기판, 슬라이더 튜닝, 프리셋 관리
- **HID 직접 통신 / Direct HID** — 외부 드라이버 불필요, USB/BT 자동 감지 + 재연결

---

## 요구사항 / Requirements

- Windows 10/11 (x64)
- Python 3.13 x64 권장 / recommended (소스 실행 시 3.10+)
- DualSense 컨트롤러 (USB 또는 BT)
- Forza Horizon 4/5/6 — Data Out 활성화 (UDP)

---

## 빠른 시작 / Quick Start (릴리스 zip)

1. [Releases](../../releases)에서 최신 zip 다운로드 / Download latest zip
2. 압축 해제 → `DHE.exe` 실행 / Extract → run `DHE.exe`
3. Forza: Settings → HUD → Data Out `ON`, IP `127.0.0.1`, Port `5300`
4. 주행 시작 — 트리거 피드백 즉시 활성화 / Start driving — feedback activates immediately

---

## 소스 실행 / Run from Source

```bash
setup_vendor.bat   # 의존성 설치 / install dependencies
run_dhe.bat        # 실행 / run
```

---

## 빌드 / Build (PyInstaller)

```bash
pip install pyinstaller
build.bat          # → dist/DHE/DHE.exe
release.bat        # → DHE_v1.02.zip
```

---

## 프로젝트 구조 / Project Structure

```
app.py              진입점 / entry point
config/             설정, 프리셋 / settings, presets
dsio/               HID 출력, 트리거 코덱 / HID output, trigger codec
telemetry/          UDP 수신, 차량 모델 / UDP receiver, vehicle model
runtime/            이벤트 루프, 진단 / event loop, diagnostics
ui/                 PySide6 대시보드 / dashboard
vendor/             번들 의존성 / bundled deps (not in git)
```

---

## Forza Data Out 설정 / Setup

| 항목 / Setting | 값 / Value |
|----------------|------------|
| Data Out | ON |
| IP Address | 127.0.0.1 |
| Port | 5300 |
| 컨트롤러 진동 / Controller vibration | OFF (중복 방지 / avoid duplicate) |

Forza: **Settings → HUD → Data Out**
포트는 앱 내에서 변경 가능 / Port is configurable in the app

---

## 문제 해결 / Troubleshooting

### 텔레메트리 수신 안 될 때 / No telemetry received

1. Forza에서 Data Out **ON** 확인 / Confirm Data Out is ON
2. IP `127.0.0.1`, Port `5300` 확인 / Verify IP and Port
3. Windows 방화벽 확인 / Check firewall is not blocking UDP 5300
4. `127.0.0.1` 대신 PC의 실제 IPv4 주소 시도 / Try your PC's actual IPv4 address
5. **Game Pass / Microsoft Store** — UDP 루프백 예외 필요할 수 있음:
   May need loopback exemption (run as admin PowerShell):
   ```
   CheckNetIsolation LoopbackExempt -a -n="Microsoft.SunriseBaseGame_8wekyb3d8bbwe"
   ```
6. 다른 앱이 포트 5300 사용 중인지 확인 / Check no other app is using port 5300

### DualSense 감지 안 될 때 / DualSense not detected

- USB 케이블 또는 BT 연결 확인 / Check USB or Bluetooth connection
- Steam Input 비활성화 / Disable Steam Input for DualSense
- HidHide 등 클로킹 도구 확인 / Check if cloaking tools are hiding the device
- 컨트롤러 재연결 시도 / Try reconnecting the controller

---

## 진단 도구 / Diagnostics

**일반 사용자** — 배치 파일 더블클릭 (명령줄 불필요):
**Normal users** — double-click batch files (no command line needed):

- `DHE_SelfTest.bat` — 컨트롤러, HID, 트리거, UDP 테스트 / controller & port test
- `DHE_ExportDiagnostics.bat` — GitHub Issue용 진단 파일 생성 / create diagnostic bundle

**고급 사용자 / Advanced** — 명령줄 / command line:

```
DHE.exe --self-test            자가 진단 / run self-test
DHE.exe --export-diagnostics   진단 내보내기 / export diagnostic bundle
DHE.exe --help                 사용법 / show help
```

---

## 이 도구가 하지 않는 것 / What DHE does NOT do

- 게임 파일 수정 안 함 / Does not modify game files
- 코드 주입 안 함 / Does not inject code
- 콘텐츠 잠금 해제 안 함 / Does not unlock content
- 공식 Forza Data Out UDP만 읽음 / Reads official UDP telemetry only
- 표준 HID 프로토콜만 사용 / Uses standard HID protocol only

---

## 라이선스 / License

[Apache-2.0](LICENSE)
