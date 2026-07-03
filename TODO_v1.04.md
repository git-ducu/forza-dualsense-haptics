# TODO v1.04 — TIRE Bus + Per-Bus Diagnostics

---

## 목표

TIRE bus를 내부적으로 추가하여 타이어 관련 햅틱 소스를 독립 bus로 분리.
UI 미노출, gain 1.0 고정, 기존 haptic balance 인식 가능 수준 유지.
진단에서 TIRE bus 활동 확인 가능하게.

---

## 배경

- 현재 4-bus: SURFACE / VEHICLE / ENGINE / EVENT
- 제안 5-bus: SURFACE / **TIRE** / VEHICLE / ENGINE / EVENT
- 타이어 소스 (wheelspin, tire_scrub, asphalt_grip)가 현재 VEHICLE bus에 혼합
- 독립 제어 불가 → 드리프트 시 road texture를 살리면서 tire noise만 줄이기 어려움
- v1.03의 trigger drift fade와 동일 개념을 haptic engine에도 적용 가능한 인프라

### Bus 의미 정의

| Bus | 담당 영역 | 소스 예시 |
|-----|-----------|-----------|
| SURFACE | 노면 물리 텍스처 | road_texture, kerb, gravel, dirt, wet_surface |
| TIRE | 타이어 동적 피드백 | wheelspin, tire_scrub, asphalt_grip (traction edge) |
| VEHICLE | 차체 동역학/관성 | weight_transfer, slide, drift, rear_breakaway |
| ENGINE | 파워트레인 | RPM, redline, turbo, drivetrain |
| EVENT | 일회성 임팩트 | gear shift, collision, bump, landing |

구분 원칙: SURFACE = 노면이 타이어에 주는 것, TIRE = 타이어가 한계에서 내는 것, VEHICLE = 차체가 관성으로 보여주는 것.

---

## 아키텍처 분석 결과 (코드 검증 완료)

### 자동 확장되는 부분 (하드코딩 없음)
- `HapticBus` enum → `TIRE = "tire"` 한 줄이면 확장
- `bus_mixer.py` → `{bus: [] for bus in HapticBus}`, `MixerState.__post_init__` → 자동 확장
- `renderer.py` → 추상 `bus` 파라미터, `HapticBus.TIRE` 넘기면 됨
- `HapticCategory.TIRE_FEEDBACK` 이미 정의됨 (카테고리는 이미 인식)

### 수동 수정 필요한 부분 (하드코딩 확인됨)
| 위치 | 하드코딩 내용 | 작업 |
|------|---------------|------|
| `mastering.py` `.process()` | 4-bus 명시 파라미터 (continuous/vehicle/engine/event) | tire_l/r 파라미터 추가 |
| `mastering.py` return | 8-tuple (4 bus × L/R) | 10-tuple로 확장 |
| `mastering.py` `other_rms` | `veh_rms + event_rms + eng_rms` | `+ tire_rms` |
| `bus.py` `HapticBusState` | `surface/vehicle/event/engine/master` 명시 필드 | `tire: BusLevel` 추가 |
| `audioEngine.py` `_bus_*` | `_bus_cont/veh/evt/eng` 4쌍 pre-alloc | `_bus_tire_l/r` 추가 |
| `audioEngine.py` `bus_arrays()` | `vehicle_names` set에 wheelspin/scrub/asphalt_grip 포함 | tire_names set 분리 |
| `audioEngine.py` final mix | `left = continuous + vehicle + engine + event` | `+ tire` |
| `audioEngine.py` mastering call | 4-bus kwargs | tire_l/r kwargs 추가 |
| `diagnostics.py` | `bus_engine/surface/event_gain` 명시 | `bus_tire_gain` 추가 |
| `diagnostics.py` `_summarize_records` | RMS key 목록 | `mix_tire_rms` 추가 |

---

## 작업 범위 (현실적 추정)

> **주의**: 줄 수 추정은 참고용. 정확한 구현은 코드 문맥에 따라 달라짐.

### A. 내부 TIRE bus 추가 (핵심)

| 파일 | 변경 | 예상 |
|------|------|------|
| `dsio/haptics/bus.py` | `TIRE = "tire"` enum + `HapticBusState.tire` 필드 | 2–3줄 |
| `telemetry/haptics/sourceRegistry.py` | wheelspin, tire_scrub, asphalt_grip → `HapticBus.TIRE` | 3줄 |
| `dsio/haptics/mastering.py` | `tire_l/r` 파라미터 + tire_rms + saturation + return 확장 | 15–20줄 |
| `telemetry/haptics/audioEngine.py` | `_bus_tire_l/r` alloc + `tire_names` routing + mastering call + final mix | 12–16줄 |
| `runtime/diagnostics.py` | `mix_tire_rms`, `mix_tire_peak`, `bus_tire_gain` export | 4–5줄 |

**합계: 36–47줄** (이전 추정 22줄은 낙관적이었음)

### B. Config (최소한)

| 파일 | 변경 | 예상 |
|------|------|------|
| `config/settings.py` | (추가하지 않음 — 내부 상수 사용) | 0줄 |
| `config/option_registry.py` | (미등록 — UI 미노출) | 0줄 |

### C. Per-bus 진단 (A에 포함)

`HapticMasteringDiagnostics`에 `tire_rms` + `tire_peak` 필드 추가 → `render_stats()`에 자동 포함.

---

## TIRE mastering 설계

### Sidechain ducking 정책

기존 동작 분석:
- SURFACE (continuous): EVENT에 의해 sidechain duck 됨 (mid protection으로 floor 보장)
- VEHICLE: ducking 없음 (vehicle 관련 duck 코드는 이미 비활성화됨)
- ENGINE: ducking 없음
- EVENT: 제한 없음 (다만 punch_to_mid_ratio guard 있음)

**TIRE ducking 정책:**
- TIRE는 기본적으로 ducking 대상 아님 (VEHICLE과 동일 취급)
- 이유: 이전에 VEHICLE에 있었으므로 duck 안 됨이 기존 동작
- EVENT 발생 시 TIRE 자체는 duck되지 않으나, TIRE가 EVENT를 묻히게 할 정도로 강하면 HF shimmer cap에 의해 간접 제한됨
- 미래: v1.05+에서 필요하면 경량 limiter interaction 추가 가능

정리:
- ✅ TIRE는 EVENT sidechain에서 제외 (VEHICLE과 동일)
- ✅ TIRE는 mid protection 대상 아님 (continuous만 해당)
- ✅ `other_rms`에 tire_rms 포함 → HF shimmer cap 계산에 참여
- ✅ EVENT가 매우 강할 때 tire가 간접적으로 제한될 수 있음 (설계 의도)

### Soft saturation
- `tire_rms > 0.45` → `k_tire = 1.0 + drive * 0.8` (VEHICLE 수준)
- 타이어는 짧은 피크가 많으므로 VEHICLE보다 약간 관대한 임계값 적용

### HF shimmer cap
- `other_rms = veh_rms + event_rms + eng_rms + tire_rms` (tire 포함)
- TIRE 활성 시 continuous(surface) bus가 과도하게 지배하지 않도록 보장

---

## 소스 이동 계획

### TIRE bus로 이동 (VEHICLE에서)
- `wheelspin` — 타이어 스핀 진동 (명확히 타이어)
- `tire_scrub` — 횡방향 타이어 마찰 (명확히 타이어)
- `asphalt_grip` — **타이어 그립 한계 경고** (코드 검증: slip_angle + combined_slip + lateral_g 기반 계산 → 노면 텍스처가 아닌 타이어 트랙션 엣지 신호임을 확인)

### VEHICLE에 유지
- `weight_transfer` — 차체 하중 이동 (관성/역학)
- `slide` — 차체 슬라이드 (차체 모션)
- `drift` — 차체 드리프트 움직임 (차체 모션)
- `rear_breakaway` — 후방 이탈 동역학 (차체 모션)

이동 판단 근거:
- TIRE: 타이어 물리적 한계에서 발생하는 진동/마찰/경고 → 타이어가 "주체"
- VEHICLE: 차체가 관성이나 무게로 움직이는 느낌 → 차체가 "주체"
- `rear_breakaway`는 "후륜이 그립을 잃을 때"이지만, 느낌 자체는 차체 회전/이탈감이므로 VEHICLE 유지

### SURFACE에 유지
- road texture, kerb, rumble strip, 노면 종류별 텍스처 (모두 노면 기원)

### ENGINE에 유지
- RPM, redline, turbo spool, drivetrain (파워트레인 기원)

### EVENT에 유지
- gear shift, collision, impact, bump, landing (일회성 임팩트)

---

## Balance preservation (RMS 보존 정책)

### 이전 TODO의 문제점
"소스 이동 전후 total RMS 동일해야 함" → **너무 엄격함**.

이유:
- VEHICLE bus 경로와 TIRE bus 경로는 saturation 임계가 독립적
- 소스가 VEHICLE에서 빠지면 VEHICLE saturation이 덜 걸리고, TIRE에서 독립적으로 saturation이 걸림
- gain 1.0이어도 saturation path 차이로 수학적 동일은 불가능

### 현실적 수용 기준
- [ ] 기존 haptic balance가 **인식 가능 수준으로 유지**됨 (feel이 크게 다르지 않음)
- [ ] VEHICLE RMS 감소 + TIRE RMS 증가 = 합산 유사 수준
- [ ] 기존에 눌리던 타이어 소스가 더 명확해질 수 있음 (의도적 개선)
- [ ] saturation 임계 차이로 인한 미세 변화는 수용 (peak 기준 ±10% 이내)
- [ ] EVENT/SURFACE/ENGINE은 변경 없음

검증 방법: 진단 export에서 `mix_vehicle_rms` + `mix_tire_rms` 합산이 이전 `mix_vehicle_rms`와 유사한지 확인.

---

## Config 호환

### 결정: 내부 상수 사용 (settings.py 필드 추가 안 함)

이유:
- v1.04에서 TIRE gain은 1.0 고정, 사용자 조절 불가
- config 필드를 추가하면 migration complexity만 생김 (user_preferences.json에 기본값 자동 생성 등)
- audioEngine.py 내부에서 `_TIRE_BUS_GAIN = 1.0` 상수로 충분
- v1.10에서 UI 노출 결정 시 그때 settings.py + option_registry에 추가

호환:
- 기존 SURFACE/VEHICLE/ENGINE/EVENT gain 동작 불변
- 이전 사용자 환경에서 업데이트 시 설정 파일 변경 없음
- `bus_tire_gain`은 진단 export에서 상수값(1.0)으로 표시

---

## 안전장치

- [ ] TIRE bus gain = 1.0 고정 (v1.04에서 조절 불가)
- [ ] UI 미노출 (option_registry에 추가하지 않음)
- [ ] settings.py 필드 추가 안 함 (내부 상수만 사용)
- [ ] EVENT sidechain에서 TIRE 제외 (VEHICLE과 동일 정책)
- [ ] HF shimmer cap에 tire_rms 참여 (EVENT 명확성 간접 보호)
- [ ] `isRacing=False` 시 TIRE bus도 자동 해제 (bus_arrays가 zero 유지)
- [ ] Balance 인식 가능 수준 유지 (수학적 동일은 요구하지 않음)

---

## 구현 전 확인 (pre-flight checklist)

모든 `HapticBus` 사용 위치를 확인하여 hidden 4-bus assumption 누락 없는지 검증:

- [ ] `dsio/haptics/bus.py` → HapticBus enum, HapticBusState (필드 추가 필요)
- [ ] `dsio/haptics/bus_mixer.py` → enum-driven (자동 확장 확인)
- [ ] `dsio/haptics/mastering.py` → process() 시그니처 + return tuple (수동 확장)
- [ ] `dsio/haptics/renderer.py` → bus 파라미터만 전달 (변경 불필요 확인)
- [ ] `telemetry/haptics/audioEngine.py` → _bus_* alloc, bus_arrays(), final mix, mastering call
- [ ] `telemetry/haptics/sourceRegistry.py` → 소스 bus 값 변경
- [ ] `telemetry/haptics/musicalMixer.py` → extract_features (tire_edge 이미 있음, bus와 무관)
- [ ] `runtime/diagnostics.py` → bus gain export, _summarize_records keys
- [ ] `runtime/loop.py` → 로그 출력 (변경 불필요 확인)
- [ ] `ui/` → BusLevel 표시 (HapticBusState 필드 추가로 자동 반영되는지 확인)

---

## 미포함 (v1.05+)

- ❌ Spatial L/R tire biasing (per-wheel 좌우 분리) → v1.05
- ❌ Cornering lateral force haptic → v1.05
- ❌ Haptic drift fade (bus-level) → v1.05+
- ❌ TIRE bus gain UI 노출 → v1.10
- ❌ Redline pulse 개선 → v1.05
- ❌ Surface transition smoothing → v1.05
- ❌ Per-source limiter / loudness normalization → v1.10+

---

## 진단 (Diagnostics)

### 추가 필드

| 필드 | 의미 | 이유 |
|------|------|------|
| `tire_rms: float` | TIRE bus RMS | 기본 활동 지표 |
| `tire_peak: float` | TIRE bus peak | 타이어 피크가 짧으므로 RMS만으로는 놓칠 수 있음 |

### Export keys (diagnostics.py)
- `mix_tire_rms` — HapticMasteringDiagnostics.tire_rms
- `mix_tire_peak` — HapticMasteringDiagnostics.tire_peak
- `bus_tire_gain` — 상수 1.0 (v1.04)

### _summarize_records 추가 keys
- `mix_tire_rms` (avg/max/p95 통계)

### 선택적 (구현이 간단하면)
- `active_tire_sources` 리스트 → 복잡도가 높으면 v1.05 이후로 연기

---

## 검증 계획

- [ ] py_compile 모든 수정 파일
- [ ] 기존 haptic balance 인식 가능 수준 유지 확인
- [ ] 진단 export에 `mix_tire_rms`, `mix_tire_peak`, `bus_tire_gain` 출력 확인
- [ ] 일반 주행: road texture 정상 (SURFACE 불변)
- [ ] 휠스핀 출발: tire_rms/tire_peak 상승 확인
- [ ] RWD 드리프트: tire_rms 활성 + surface_rms 독립 유지 + vehicle slide 유지
- [ ] 충돌/기어 시프트: EVENT 정상, TIRE 간섭 없음
- [ ] 텔레메트리 유실: 모든 bus 해제 확인
- [ ] ENGINE/EVENT/SURFACE bus RMS 이전과 동일 (이 버스들은 변경 없으므로)

---

## 리스크

| 리스크 | 심각도 | 완화 |
|--------|--------|------|
| VEHICLE→TIRE 소스 이동 시 saturation 경로 변경으로 미세 밸런스 차이 | 낮음 | TIRE saturation을 VEHICLE과 동일 파라미터로 설정; peak ±10% 이내 허용 |
| HapticBusState 필드 추가 시 UI 코드가 새 필드를 무시할 가능성 | 낮음 | dataclass default=BusLevel() → 기존 UI 코드 호환; tire meter 추가는 선택 |
| mastering return tuple 확장 시 unpack 실패 | 중간 | audioEngine.py 호출부 동시 수정; py_compile로 검증 |
| audioEngine.py bus_arrays() routing 변경 시 기존 소스가 wrong bus로 갈 위험 | 낮음 | tire_names set을 vehicle_names에서 정확히 분리; 나머지 fallback 유지 |
| 미래 UI 노출 시 옵션 과잉 | 낮음 | v1.04는 내부 전용, v1.10에서 판단 |
| 기존 config 호환 | 없음 | settings.py 변경 없음, additive only |

---

## 버전 로드맵

| 버전 | 내용 | 성격 |
|------|------|------|
| v1.03 | 트리거 3기능 (Predictive ABS, Throttle Traction, Drift Fade) + hotfix | 기능 릴리즈 |
| **v1.04** | **TIRE bus 내부 추가 + per-bus 진단** | 인프라 / 내부 구조 |
| v1.05 | Spatial L/R tire bias + cornering lateral haptic + redline polish | 햅틱 공간감 |
| v1.10 | TIRE gain UI 노출 + bus-level drift fade + loudness normalization | 마스터링 고도화 |

v1.04는 **소규모 인프라 릴리즈**로 유지:
- 유저 체감: 거의 동일 (미세 개선 가능)
- 개발자 이점: tire 소스 독립 제어 인프라 확보
- 리스크: 낮음 (소스 이동만, 새 기능 없음)

---

## 설계 리뷰 결론 (2026-07-04)

### 전체 평가: ✅ 진행 가능

TIRE bus 추가는 아키텍처적으로 자연스럽고, 이미 `HapticCategory.TIRE_FEEDBACK`으로 의미 분리가 되어 있음.
코드 변경량은 이전 추정보다 크지만 (36–47줄), 여전히 관리 가능한 수준.

### 핵심 수정사항 (이전 TODO 대비)
1. **줄 수 추정 상향** — 22줄 → 36–47줄 (현실적)
2. **RMS 보존 완화** — "동일" → "인식 가능 수준 유지, ±10% peak 허용"
3. **Config 방식 변경** — settings.py 필드 → 내부 상수 (`_TIRE_BUS_GAIN = 1.0`)
4. **Ducking 정책 명확화** — "완전 제외" → "VEHICLE과 동일 (duck 안 됨, HF cap에만 참여)"
5. **HapticBusState 하드코딩 식별** — 이전 TODO에서 누락됨
6. **asphalt_grip 검증 완료** — 코드 확인 결과 traction edge 신호 (TIRE 적합)
7. **진단 보강** — tire_peak 추가 (짧은 피크 캡처용)
8. **pre-flight checklist 추가** — hidden assumption 검증 목록
