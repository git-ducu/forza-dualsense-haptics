# DHE 사용 가이드 / User Guide

---

## 1. 빠른 시작 / Quick Start

1. `DHE.exe` 실행 / Run `DHE.exe`
2. DualSense를 USB 또는 블루투스로 연결 / Connect DualSense via USB or Bluetooth
3. Forza 게임 내 설정 / In-game settings:
   - **Settings → HUD → Data Out** → `ON`
   - **IP Address** → `127.0.0.1`
   - **Port** → `5300`
   - **Settings → Controller → Vibration** → `OFF` (DHE와 중복 방지 / prevents double feedback)
4. 주행 시작 — 즉시 트리거와 햅틱이 반응합니다 / Start driving — triggers and haptics activate immediately

> **참고 / Note**: Forza의 기본 진동과 DHE 햅틱이 동시에 작동하면 느낌이 겹치고 혼란스러워집니다.
> 반드시 게임 내 컨트롤러 진동을 꺼주세요.
> If both Forza's built-in vibration and DHE are active, feedback will conflict.
> Always disable in-game controller vibration.

---

## 2. 대시보드 / Dashboard

DHE를 실행하면 메인 화면에 실시간 계기판이 표시됩니다.
When DHE starts, the main screen shows a live dashboard.

| 표시 항목 / Indicator | 의미 / Meaning |
|----------------------|----------------|
| 컨트롤러 상태 / Controller | 연결됨(USB/BT) 또는 미연결 / Connected (USB/BT) or disconnected |
| 텔레메트리 상태 / Telemetry | 수신 중 또는 대기 / Receiving or waiting |
| RPM / Speed | 현재 차량 정보 / Current vehicle info |

주행 중이 아닐 때(메뉴, 로딩)는 텔레메트리가 멈추며, DHE도 자동으로 대기 상태가 됩니다.
When not driving (menus, loading), telemetry stops and DHE idles automatically.

---

## 3. 트리거 피드백 / Trigger Feedback

DualSense의 L2/R2 적응형 트리거를 이용해 페달 느낌을 전달합니다.
Uses DualSense adaptive triggers on L2/R2 to simulate pedal feel.

### L2 (브레이크 / Brake)

| 기능 / Feature | 느낌 / Feel |
|----------------|------------|
| 브레이크 저항 / Brake resistance | 밟을수록 무거워짐 / Heavier as you press deeper |
| ABS 펄스 / ABS pulse | 잠김 방지 시 떨림 / Rapid vibration during ABS activation |
| 노면 질감 / Road texture | 도로 표면의 미세한 떨림 / Subtle surface texture feedback |
| 기어 변속 / Gear shift | 변속 시 순간 충격 / Momentary thump on shift |

### R2 (스로틀 / Throttle)

| 기능 / Feature | 느낌 / Feel |
|----------------|------------|
| 스로틀 저항 / Throttle resistance | 가속 시 적절한 무게감 / Weighted feel on acceleration |
| 레드라인 경고 / Redline warning | RPM 한계 근처에서 떨림 / Vibration near rev limit |
| 레브 리미터 / Rev limiter | RPM 한계에서 강한 진동 / Strong buzz at rev limit |
| 휠스핀 / Wheelspin | 뒷바퀴 헛도는 느낌 / Buzz when rear wheels lose grip |
| 기어 변속 / Gear shift | 변속 시 순간 충격 / Momentary thump on shift |

---

## 4. 햅틱 오디오 / Haptic Audio

DualSense의 내장 햅틱 모터를 4-bus 오디오 엔진으로 구동합니다.
Drives the DualSense built-in haptic motor via a 4-bus audio engine.

| 버스 / Bus | 내용 / Content |
|------------|----------------|
| 🛣️ 노면 / Surface | 아스팔트, 자갈, 연석, 도로 질감 / Asphalt, gravel, kerbs, road texture |
| ⚙️ 엔진 / Engine | RPM 텍스처, 터보, 레드라인, 엔진 브레이킹 / RPM texture, turbo, redline, engine braking |
| 🏎️ 차체 / Vehicle | 하중이동, 드리프트, 그립 한계, 타이어 / Weight transfer, drift, grip edge, tires |
| 💥 이벤트 / Event | 변속 충격, 충돌, 범프, 가감속 / Shift impact, collision, bumps, accel/decel |

각 버스는 독립적으로 볼륨 조절이 가능하며, 마스터 게인으로 전체 세기를 한 번에 조절할 수 있습니다.
Each bus has independent volume control, and a master gain adjusts overall intensity.

---

## 5. 튜닝 / Tuning

Settings 탭에서 모든 파라미터를 슬라이더로 조절할 수 있습니다.
All parameters are adjustable via sliders in the Settings tab.

### 섹션 구성 / Section Layout

| 섹션 / Section | 내용 / What it controls |
|----------------|------------------------|
| 🕹️ 트리거 / Trigger | L2/R2 저항, 진동, 스위치 ON/OFF |
| 🎮 햅틱 마스터 / Haptic Master | 전체 세기 + 버스별 비율 |
| 🛣️ 노면 / Surface | 도로 질감 세부 조절 |
| ⚙️ 엔진 / Engine | RPM, 레드라인, 터보 등 |
| 💥 이벤트 / Event | 변속, 충돌, 가감속 |
| 🏎️ 차체 / Vehicle | 드리프트, 그립, 하중이동 |
| 🔈 공간감 / Spatial | 좌우 분리, 전후 대비 |
| 🎛️ 고급 / Advanced | 내부 오디오 마스터링 |

### 슬라이더 조작 팁 / Slider Tips

- **왼쪽 = 약하게, 오른쪽 = 강하게** / Left = subtle, Right = intense
- 변경 즉시 반영됩니다 (재시작 불필요) / Changes apply instantly (no restart needed)
- 스위치를 OFF로 끄면 하위 슬라이더가 숨겨집니다 / Turning a switch OFF hides its detail sliders
- 퍼센트(%)로 표시되는 항목은 비율 설정입니다 / Items shown as % are ratio settings
- 아래 표에서 `json`는 설정 파일을 직접 수정할 때 참고용입니다. 앱에서는 한글/영어 라벨로 표시됩니다.
- The `json` column is for manual config file editing. The app displays Korean/English labels.

---

## 5-1. 🕹️ 트리거 상세 / Trigger Detail

트리거는 DualSense L2/R2 버튼의 **물리적 저항감**과 **진동**을 제어합니다.
실제 레이싱카 페달처럼 밟는 힘에 따라 반응이 달라집니다.

Controls the **physical resistance** and **vibration** of the DualSense L2/R2 buttons.
Responds to your press force like real racing car pedals.

### 마스터 게인 / Master Gains

전체 트리거의 세기를 한 번에 조절하거나, L2/R2를 따로 조절합니다.
Adjust overall trigger intensity at once, or tune L2/R2 independently.

| UI 라벨 | json | 범위 | 설명 / Description |
|---------|--------|------|------|
| 트리거 전체 세기 | `trigger_master_gain` | 0.0–1.80 | 모든 트리거 피드백의 볼륨 노브. 0이면 모든 트리거 효과가 꺼짐. 처음엔 1.0(기본값)에서 시작해서 취향에 맞게 올리거나 내리세요<br>Volume knob for all trigger feedback. 0 = all effects off. Start at 1.0 and adjust to taste |
| L2 (브레이크) 세기 | `trigger_l2_gain` | 0.0–2.00 | L2만 따로 세기 조절. 브레이크가 너무 무겁거나 가벼우면 여기서 조절<br>L2-only intensity. Adjust here if braking feels too heavy or too light |
| R2 (가속) 세기 | `trigger_r2_gain` | 0.0–2.00 | R2만 따로 세기 조절. 가속 페달 느낌이 안 맞으면 여기서 조절<br>R2-only intensity. Adjust here if throttle feel is off |

### 브레이크 (L2) / Brake

L2를 밟으면 실제 브레이크 페달처럼 저항이 생기고, 상황에 따라 진동이 옵니다.
Pressing L2 creates resistance like a real brake pedal, with situational vibrations.

| UI 라벨 | json | 범위 | 설명 / Description |
|---------|--------|------|------|
| 브레이크 저항 | `enable_brake_resistance` | ON/OFF | 켜면 브레이크를 밟을수록 L2가 점점 무거워집니다. 실제 브레이크 페달의 유압 저항과 비슷한 느낌. 끄면 L2가 항상 가볍습니다<br>ON = L2 gets heavier as you press deeper, like hydraulic brake resistance. OFF = always light |
| 브레이크 저항 세기 | `trigger_brake_gain` | 0.0–2.00 | 저항의 세기. 0.5면 가볍고, 1.5면 상당히 뻑뻑합니다. 손가락이 피로하면 낮추세요<br>Resistance strength. 0.5 = light, 1.5 = quite stiff. Lower if your fingers fatigue |
| 브레이크 최대 저항 | `brake_max_force` | 1–8 | L2를 끝까지 눌렀을 때 최대로 버티는 힘의 단계. 8이면 매우 단단하고, 1이면 거의 안 버팀<br>Max resistance at full press. 8 = very stiff, 1 = barely resists |
| 브레이크 데드존 | `brake_deadzone` | 0–120 | L2를 이 정도까지는 아무 저항 없이 가볍게 움직입니다. 높이면 초반 터치가 부드러워지고, 0이면 처음부터 바로 저항 시작<br>Free travel before resistance begins. Higher = softer initial touch, 0 = resistance from the start |
| 브레이크 스태틱월 | `enable_brake_static_wall` | ON/OFF | L2 중간에 "딱" 걸리는 벽을 만듭니다. 실제 브레이크 페달의 딱딱한 지점처럼 느껴짐. 브레이크 밟는 감각을 더 실감나게 해줍니다<br>Creates a hard "wall" mid-press. Simulates the firm point on a real brake pedal |
| 스태틱월 위치 | `brake_static_wall_at` | 80–220 | 벽이 걸리는 위치. 숫자가 낮으면 얕은 곳에서 일찍 걸리고, 높으면 깊이 눌러야 걸림<br>Where the wall engages. Lower = catches early (shallow), higher = catches late (deep) |
| 스태틱월 강도 | `brake_static_wall_force` | 50–255 | 벽의 단단함. 255면 매우 딱딱하게 버티고, 50이면 살짝 걸리는 느낌<br>Wall hardness. 255 = rock-solid, 50 = slight bump |
| L2 ABS 반복감 | `enable_abs` | ON/OFF | 급브레이크로 바퀴가 잠기려 할 때 ABS가 작동하면서 L2가 "두두두두" 빠르게 떨립니다. 실제 ABS 페달 반동과 같은 느낌<br>Rapid L2 pulsing when ABS activates during hard braking — feels like real ABS pedal kickback |
| L2 ABS 떨림 | `trigger_abs_gain` | 0.0–1.80 | ABS 떨림의 세기. 올리면 더 강하게 떨리고, 낮추면 은은하게<br>ABS vibration intensity. Higher = stronger pulses |
| L2 노면 질감 | `enable_left_road_texture` | ON/OFF | 브레이킹 중 도로 표면의 미세한 울퉁불퉁함이 L2에 전달됩니다. 아스팔트와 자갈의 차이를 손끝으로 느낄 수 있음<br>Road texture transmitted through L2 while braking. Feel the difference between asphalt and gravel |
| L2 변속 충격 | `enable_gear_shift_brake` | ON/OFF | 기어가 바뀔 때 L2에도 살짝 '톡' 충격이 옵니다. 브레이킹 중 다운시프트 느낌<br>Brief tap on L2 during gear changes — downshift feel while braking |
| L2 엔진 브레이크 저항 | `enable_trigger_engine_brake` | ON/OFF | 고RPM에서 가속 페달을 뗐을 때 엔진이 감속을 돕는 느낌. L2가 살짝 무거워짐<br>Engine braking feel — L2 gets slightly heavier when lifting off at high RPM |
| 엔진브레이크 트리거 세기 | `trigger_engine_brake_strength` | 0.3–2.0 | 엔진 브레이크 시 L2 저항의 세기<br>Engine brake resistance intensity on L2 |

### 스로틀 (R2) / Throttle

R2를 밟으면 가속 페달 느낌이 나고, 레드라인/변속/휠스핀 등 다양한 상황 피드백이 옵니다.
Pressing R2 gives throttle pedal feel with feedback for redline, shifts, wheelspin, and more.

| UI 라벨 | json | 범위 | 설명 / Description |
|---------|--------|------|------|
| 가속 저항 | `enable_throttle_resistance` | ON/OFF | 켜면 R2를 밟을수록 약간의 저항이 생깁니다. 가속 페달의 스프링 느낌. 끄면 항상 가벼움<br>ON = slight spring resistance as you press R2, like a throttle pedal. OFF = always light |
| 가속 최대 저항 | `throttle_max_force` | 1–15 | R2를 끝까지 밟았을 때 최대 저항. 브레이크보다는 보통 가볍게 설정합니다<br>Max resistance at full R2 press. Usually set lighter than brake |
| 가속 데드존 | `accel_deadzone` | 0–120 | R2를 이 정도까지는 저항 없이 자유롭게 움직임. 미세한 스로틀 조작이 필요하면 높이세요<br>Free travel before resistance. Higher = more room for fine throttle modulation |
| 저항 깊이 | `adaptive_acceleration_depth` | 0.0–1.50 | 저항이 시작되는 깊이. 올리면 R2를 더 깊이 눌러야 저항을 느낌. 내리면 초반부터 바로 저항<br>Where resistance starts. Higher = must press deeper before feeling resistance |
| R2 변속 충격 | `enable_gear_shift` | ON/OFF | 기어가 바뀔 때 R2에 '탁' 하고 순간적인 충격이 옵니다. 변속 타이밍을 손끝으로 느낄 수 있음<br>Brief "tap" on R2 during gear shifts — feel shift timing through your fingertip |
| 변속 트리거 킥 | `trigger_shift_kick_gain` | 0.0–2.50 | 변속 순간 R2가 '탁' 차는 힘. 올리면 더 확실하게 느껴지고, 0이면 킥 꺼짐<br>Shift kick strength on R2. Higher = more pronounced kick, 0 = disabled |
| 변속 트리거 철컥 | `trigger_shift_clack_gain` | 0.0–2.50 | 변속 후 기어가 '철컥' 물리는 느낌. 킥과 함께 변속의 기계적 감각을 만듦<br>Mechanical "clack" after shift — combined with kick creates a gearbox feel |
| R2 레드라인 진동 | `enable_rev_limiter` | ON/OFF | RPM이 최대치에 도달하면 R2가 "부르르르" 강하게 떨립니다. "지금 변속해!" 라는 신호<br>Strong R2 buzz at max RPM — a "shift now!" signal |
| R2 리미터 패턴 | `enable_rev_limiter_pattern` | ON/OFF | 레드라인 진동의 패턴 변화. 켜면 단조로운 진동 대신 리듬감 있는 패턴으로 떨림<br>Rhythmic pattern for redline buzz instead of a flat vibration |
| 레드라인 작동 시점 | `rev_limit_ratio` | 50%–99% | RPM이 최대의 몇 %에 도달하면 레드라인 피드백 시작. 기본 92~93%. 낮추면 더 일찍 경고<br>RPM threshold for redline feedback. Default ~92-93%. Lower = earlier warning |
| R2 레드라인 저항 | `enable_trigger_redline_pulse` | ON/OFF | 레드라인 근처에서 R2가 딱딱해지며 밀어내는 느낌. 진동(부르르)과 다른 "저항으로 밀어냄" 느낌<br>R2 stiffens and pushes back near redline — a resistance-based signal, different from buzz |
| 레드라인 트리거 세기 | `trigger_redline_strength` | 0.3–2.0 | R2 레드라인 저항 펄스의 세기<br>R2 redline resistance pulse intensity |
| 레드라인 경고 구간 폭 | `redline_warning_width` | 3%–20% | 레드라인 경고가 시작되는 범위. 넓으면 저회전 차(경차, NA 차)에서도 충분히 일찍 경고가 옴. 좁으면 정말 한계 직전에만 경고<br>Warning start range. Wider = warning begins earlier (helps low-rev cars). Narrower = only right before limit |
| R2 휠스핀 진동 | `enable_wheelspin_buzz` | ON/OFF | 뒷바퀴(또는 구동 바퀴)가 헛돌 때 R2가 지지직 떨립니다. 가속 중 그립을 잃고 있다는 신호<br>R2 buzzes when drive wheels spin — "losing traction" warning |
| R2 휠스핀 떨림 | `trigger_wheelspin_gain` | 0.0–1.80 | 휠스핀 떨림의 세기<br>Wheelspin vibration intensity |
| R2 노면 질감 | `enable_right_road_texture` | ON/OFF | 가속 중 도로 표면의 질감이 R2에 전달됨<br>Road surface texture transmitted through R2 while accelerating |
| R2 타이어 스크럽 | `enable_tire_scrub_buzz` | ON/OFF | 타이어가 노면에 긁히는 느낌. 코너링 중 미세한 미끄러짐<br>Tire scrubbing buzz — subtle slip during cornering |
| 기어 위치 기반 진동 | `enable_trigger_positioned_vibration` | ON/OFF | 현재 기어와 엔진 부하에 따라 R2의 진동 위치가 바뀜. 저단 기어에서는 아래쪽, 고단에서는 위쪽에서 떨리는 느낌<br>Vibration position shifts with gear/load. Low gear = lower zone, high gear = upper zone |
| R2 아이들 진동 | `enable_idle_buzz` | ON/OFF | 정차 중 엔진이 돌아가고 있으면 R2에 미세한 공회전 진동. 차가 살아있다는 느낌<br>Subtle idle buzz on R2 while stationary — the car feels alive |

---

## 5-2. 🎮 햅틱 마스터 / Haptic Master

DualSense 본체 진동의 전체 볼륨과 4개 버스의 비율을 조절합니다.
트리거(L2/R2)와 별개로, 컨트롤러 몸체 전체가 진동하는 것이 햅틱입니다.

Controls the overall volume and bus mix of the DualSense body haptics.
Haptics are the vibrations felt through the controller body, separate from L2/R2 triggers.

| UI 라벨 | json | 범위 | 설명 / Description |
|---------|--------|------|------|
| 듀얼센스 햅틱 오디오 | `enable_haptic_audio` | ON/OFF | 햅틱 시스템 전체를 켜고 끕니다. OFF면 본체 진동 없음 (트리거만 작동)<br>Master ON/OFF for the haptic system. OFF = no body vibration (triggers still work) |
| 전체 진동 세기 | `haptic_master_gain` | 0.10–0.80 | 모든 햅틱 진동의 마스터 볼륨. 올리면 전부 강해지고, 내리면 전부 약해짐. 손이 피로하면 여기서 낮추세요<br>Master volume for all haptic vibrations. Lower this if your hands feel fatigued |
| 진동 유지량 | `haptic_fatigue_control` | 0.0–1.0 | 진동을 얼마나 오래 유지할지. 1.0이면 디테일 꼼꼼하게 유지, 0에 가까우면 진동 빨리 줄어서 손이 편함. 장시간 플레이 시 낮추세요<br>How long vibrations sustain. 1.0 = full detail, lower = vibrations decay faster (less fatigue for long sessions) |
| 🛣️ 노면 버스 | `haptic_surface_bus_gain` | 0.0–1.5 | 도로/타이어 관련 진동 전체 볼륨<br>Overall volume for road/tire-related vibrations |
| ⚙️ 엔진 버스 | `haptic_engine_bus_gain` | 0.0–1.5 | 엔진/터보/RPM 관련 진동 전체 볼륨<br>Overall volume for engine/turbo/RPM vibrations |
| 🏎️ 차체 버스 | `haptic_vehicle_bus_gain` | 0.0–1.5 | 하중이동/드리프트/그립 관련 진동 전체 볼륨<br>Overall volume for weight transfer/drift/grip vibrations |
| 💥 이벤트 버스 | `haptic_event_bus_gain` | 0.0–1.5 | 변속/충돌/범프 관련 진동 전체 볼륨<br>Overall volume for gear shift/collision/bump vibrations |

---

## 5-3. 🛣️ 노면 / Surface

주행 중 도로 표면의 질감을 손바닥으로 느끼는 진동입니다.
아스팔트, 자갈, 잔디, 연석 등 각 노면의 차이가 진동으로 전달됩니다.

Feel the road surface texture through your palms while driving.
Different surfaces (asphalt, gravel, grass, curbs) each have a distinct vibration character.

| UI 라벨 | json | 범위 | 설명 / Description |
|---------|--------|------|------|
| 노면 느낌 | `haptic_road_gain` | 0.0–1.2 | 일반 아스팔트 도로의 질감 강도. 올리면 노면의 거칠기가 선명하게 느껴지고, 내리면 매끄러운 느낌<br>Asphalt road texture intensity. Higher = rougher feel, lower = smoother |
| 노면 종류 구분 | `haptic_texture_palette_strength` | 0.0–1.8 | 노면 종류별 차이의 선명도. 올리면 아스팔트↔자갈↔잔디↔흙 각각 확실히 다르게 느껴짐. 낮추면 전부 비슷한 느낌<br>How distinct each surface type feels. Higher = clear difference between asphalt/gravel/grass/dirt. Lower = all feel similar |
| 오프로드 강도 | `haptic_gravel_gain` | 0.0–1.8 | 자갈/흙/비포장 구간의 덜컹거림 강도. 올리면 오프로드에서 팔이 흔들리고, 낮추면 부드럽게 지나감<br>Gravel/dirt/off-road rumble intensity. Higher = aggressive shaking on unpaved roads |

---

## 5-4. ⚙️ 엔진 / Engine

엔진 회전, 터보, 레드라인 경고, 시동 등 파워트레인 관련 진동입니다.
차의 심장이 뛰는 것을 손으로 느끼는 느낌입니다.

Engine rotation, turbo spool, redline warning, startup — powertrain vibrations.
Feel the heartbeat of the car through your hands.

| UI 라벨 | json | 범위 | 설명 / Description |
|---------|--------|------|------|
| 레드라인 경고 | `haptic_redline_warning_strength` | 0.0–2.0 | RPM이 한계에 가까워지면 본체가 강하게 펄스를 줍니다. "지금 변속하세요!" 신호. 올리면 더 급하게 경고<br>Strong pulse when RPM approaches redline. A "shift now!" signal. Higher = more urgent |
| 레드라인 햅틱 구간폭 | `haptic_redline_warning_width` | 3%–20% | 경고가 시작되는 범위. 넓으면 RPM이 높아지기 시작할 때부터 서서히 경고. 좁으면 진짜 한계 직전에만<br>How early the warning begins. Wider = gradual warning from lower RPM. Narrower = only right before redline |
| RPM 바디 텍스처 | `haptic_rpm_texture_enabled` | ON/OFF | RPM에 따라 본체가 미세하게 떨립니다. 저RPM에서는 느릿하게, 고RPM에서는 빠르게. 엔진이 돌아가는 느낌<br>Subtle body vibration following RPM. Slow at low RPM, fast at high RPM — feels like a running engine |
| RPM 진동 | `haptic_rpm_texture_gain` | 0.0–1.0 | RPM 텍스처 진동의 세기<br>RPM texture vibration intensity |
| 실린더 배음 | `haptic_rpm_harmonics_strength` | 0.0–1.5 | 실린더 수에 따른 진동 패턴. 올리면 4기통은 떨떨떨, 6기통은 부드럽게, V8은 둥둥둥 차이가 남<br>Cylinder-count character. Higher = 4-cyl buzzy, V6 smooth, V8 thumpy differences become clear |
| 터보 스풀업 | `haptic_turbo_spool_strength` | 0.0–1.5 | 터보 부스트가 올라올 때 "위이이잉" 하는 느낌. 터보차에서만 작동. NA차는 해당 없음<br>Turbo spool-up whine as boost builds. Only active on turbo cars; N/A cars unaffected |
| 엔진 브레이킹 | `haptic_engine_braking_strength` | 0.0–1.5 | 가속 페달 뗐을 때 엔진이 차를 잡아당기는 저항감. 고RPM에서 코너 진입 시 느껴짐<br>Engine drag when lifting off throttle. Felt during high-RPM corner entry |
| 코너 출구 토크 | `haptic_corner_exit_strength` | 0.0–1.5 | 코너에서 빠져나오며 가속할 때 바퀴에 힘이 실리는 느낌. "파워가 먹힌다"는 감각<br>Torque delivery sensation when accelerating out of a corner. Feels like power biting the wheels |
| 시동 시퀀스 | `haptic_engine_start_strength` | 0.0–2.0 | 레이스 시작이나 리스폰 시 시동 걸리는 느낌. "두르르릉"<br>Engine startup rumble on race start or respawn |
| 아이들 엔진 진동 | `haptic_idle_haptics_enabled` | ON/OFF | 정차 중 엔진 공회전의 미세한 떨림. 머슬카는 둥둥둥, 4기통은 덜덜덜<br>Idle engine vibration while stationary. Muscle cars thump, 4-cyls buzz |
| 아이들 럼블 | `haptic_idle_strength` | 0.0–1.0 | 공회전 떨림 세기. 올리면 정차 중에도 엔진이 살아있는 느낌 강함<br>Idle rumble intensity. Higher = the engine feels alive even when parked |

---

## 5-5. 💥 이벤트 / Event

기어 변속, 벽/차 충돌, 급가감속 등 순간적인 충격입니다.
"탁", "쿵", "퍽" 같은 짧고 강한 피드백입니다.

Instantaneous impacts — gear shifts, wall/car collisions, sudden acceleration/deceleration.
Short, punchy feedback like "thud", "clunk", "crack".

### 변속 / Gear Shift

| UI 라벨 | json | 범위 | 설명 / Description |
|---------|--------|------|------|
| 기어변속 전체 | `haptic_shift_master_gain` | 0.0–2.2 | 변속 관련 진동 전체 세기. 올리면 기어 체인지가 확실하게 느껴짐<br>Overall gear shift haptic intensity. Higher = shifts feel more pronounced |
| 변속 클릭 | `haptic_shift_click_strength` | 0.0–2.0 | 기어가 '철컥' 물리는 순간의 날카로운 느낌<br>Sharp "click" as the gear engages — the metallic snap of a shift |
| 변속 쿵 | `haptic_shift_clunk_strength` | 0.0–2.0 | 기어가 맞물리며 차체로 전달되는 묵직한 진동<br>Heavy "clunk" transmitted through the chassis as gears mesh |
| 변속 토크 전달 | `haptic_shift_engagement_strength` | 0.0–2.0 | 변속 후 새 기어에 힘이 '쿵' 실리는 순간. 가속이 다시 시작되는 느낌<br>Torque re-engagement after shift — the moment power reconnects to the wheels |
| 급가속 시작 충격 | `haptic_accel_onset_strength` | 0.0–2.0 | 가속 페달을 확 밟는 순간 '훅' 하고 오는 충격. 런치 느낌<br>Initial kick when stomping the throttle — launch sensation |
| 급감속 시작 충격 | `haptic_decel_onset_strength` | 0.0–2.0 | 브레이크를 확 밟는 순간 '쿵' 하고 오는 충격. 하드 브레이킹 진입<br>Jolt when slamming the brakes — hard braking onset |

### 충돌 / Collision

| UI 라벨 | json | 범위 | 설명 / Description |
|---------|--------|------|------|
| 충돌 전체 | `haptic_impact_master_gain` | 0.0–2.2 | 벽/차 충돌 전체 세기<br>Overall wall/car collision intensity |
| 충격 저음 | `haptic_impact_sub_strength` | 0.0–2.0 | 충돌 시 깊은 '쿵'. 묵직한 임팩트<br>Deep bass thud on impact — heavy, bone-rattling hit |
| 충격 날카로움 | `haptic_impact_crack_high_strength` | 0.0–2.0 | 충돌 시 '찍' 하는 날카로운 크랙. 금속끼리 부딪히는 느낌<br>Sharp metallic crack on collision — metal-on-metal impact |

---

## 5-6. 🏎️ 차체 / Vehicle

차체의 움직임(하중이동, 드리프트, 그립 한계)을 손으로 느끼는 진동입니다.
차가 어떻게 움직이고 있는지 시각 없이도 감으로 알 수 있게 해줍니다.

Vehicle dynamics — weight transfer, drift, grip limit — felt through vibration.
Know how the car is behaving by feel alone, without looking at the screen.

| UI 라벨 | json | 범위 | 설명 / Description |
|---------|--------|------|------|
| 뒷바퀴 이탈 | `haptic_drift_breakaway_strength` | 0.0–2.0 | 뒷바퀴가 빠지면서 드리프트가 시작되는 순간의 신호. "리어가 나간다!"<br>Rear breakaway signal — the moment the tail steps out into a drift |
| 타이어 긁힘 | `haptic_tire_scrub_texture_strength` | 0.0–2.0 | 코너링 중 타이어가 노면에 긁히는 마찰 느낌. 미세한 슬립의 감각<br>Tire scrubbing friction during cornering — the feel of subtle slip angles |
| 그립 한계 경고 | `haptic_grip_edge_high_strength` | 0.0–2.0 | 타이어가 곧 그립을 잃을 것 같은 순간의 경고. "여기가 한계야" 신호<br>Warning when tires are about to lose grip — "you're at the limit" signal |
| 슬립 지직거림 | `haptic_slip_sizzle_strength` | 0.0–2.0 | 타이어가 미끄러지면서 나는 지직거리는 느낌. 젖은 노면에서 특히 뚜렷<br>Sizzling sensation from sliding tires — especially noticeable on wet surfaces |
| 차체 모션 (피칭/롤) | `haptic_body_motion_enabled` | ON/OFF | 브레이킹 시 앞으로 쏠리고(다이브), 코너에서 기울어지는(롤) 차체 움직임<br>Body pitch (dive under braking) and roll (lean in corners) |
| 피칭/롤 모션 | `haptic_body_motion_gain` | 0.0–0.90 | 차체 모션 세기. 올리면 급브레이크 다이브와 코너 기울기가 확실히 느껴짐<br>Body motion intensity. Higher = clearly feel braking dive and cornering lean |
| 트랙션 펄스 | `haptic_traction_pulse_enabled` | ON/OFF | 구동 바퀴와 비구동 바퀴의 속도 차이로 인한 펄스. AWD/RWD 차이를 느낄 수 있음<br>Pulse from speed difference between driven and undriven wheels — feel AWD vs RWD |
| 트랙션 펄스 세기 | `haptic_traction_pulse_gain` | 0.0–0.80 | 트랙션 펄스의 강도<br>Traction pulse intensity |

---

## 5-7. 🔈 공간감 / Spatial

진동의 좌우 분리와 전후 구분입니다.
DualSense의 좌우 햅틱 모터를 다르게 구동해서 방향감을 만듭니다.

Left/right separation and front/rear distinction.
Drives the DualSense's two haptic motors independently to create directional awareness.

| UI 라벨 | json | 범위 | 설명 / Description |
|---------|--------|------|------|
| 공간감 햅틱 | `haptic_spatial_haptics_enabled` | ON/OFF | 좌우 분리 시스템 전체 ON/OFF. 끄면 양쪽이 항상 동일하게 울림<br>Master ON/OFF for spatial separation. OFF = both sides always vibrate equally |
| 좌우 분리 | `haptic_spatial_width` | 0.60–1.80 | 스티어링 방향에 따라 진동이 좌우로 치우침. 올리면 오른쪽 코너에서 오른손이 더 떨리고, 왼쪽 코너에서 왼손이 더 떨림<br>Steering-linked left/right bias. Higher = right hand vibrates more in right turns, left in left turns |
| 전후 구분 | `haptic_front_rear_contrast` | 0.0–1.8 | 앞바퀴와 뒷바퀴의 상태 차이를 느끼게 함. 올리면 앞바퀴 그립 상실과 뒷바퀴 이탈이 확실히 다르게 느껴짐<br>Front/rear tire state contrast. Higher = clearly distinguish front grip loss from rear breakaway |
| 방향성 강조 | `haptic_final_side_boost` | 0.0–1.2 | 좌우 방향 신호를 과장. 올리면 방향감이 더 극적이지만 자연스러움은 줄어들 수 있음<br>Exaggerates directional signals. Higher = more dramatic but potentially less natural |

---

## 5-8. 🎛️ 고급 마스터링 / Advanced Mastering

내부 오디오 후처리 설정입니다. 잘 모르면 기본값 그대로 두세요.
모든 햅틱 신호가 최종 출력되기 전에 거치는 음색/밸런스 조정입니다.

Internal audio post-processing. Leave at defaults if unsure.
These are tonal/balance adjustments applied to all haptic signals before final output.

| UI 라벨 | json | 범위 | 설명 / Description |
|---------|--------|------|------|
| 마스터링 활성화 | `haptic_mastering_enabled` | ON/OFF | 마스터링 후처리 전체 ON/OFF. 끄면 원본 신호 그대로 출력 (음 찢어짐 주의)<br>Master ON/OFF for post-processing. OFF = raw signal output (may clip) |
| 저음 기초 | `haptic_bass_foundation_gain` | 0.0–3.0 | 차체가 울리는 깊은 떨림. 올리면 엔진/충돌의 묵직함이 강화<br>Deep bass foundation. Higher = heavier engine/collision rumble |
| 서브 베이스 | `haptic_sub_bass_boost` | 0.0–0.54 | 아주 깊은 저음. 올리면 공회전이나 저RPM에서 "웅웅" 하는 울림<br>Sub-bass boost. Higher = more "hum" at idle or low RPM |
| 미드 텍스처 | `haptic_mid_texture_balance` | 0.60–1.60 | 노면 디테일 대역. 올리면 아스팔트 질감이 선명하게 느껴짐<br>Mid-range texture band. Higher = clearer asphalt texture detail |
| 고음 엣지 | `haptic_high_edge_gain` | 0.0–3.0 | 날카로운 느낌의 세기. 올리면 연석, 요철, 금속 충돌이 쨍하게 들어옴<br>High-frequency edge. Higher = sharper curbs, bumps, and metal impacts |
| 고음 반짝임 | `haptic_high_shimmer_ratio` | 0.0–0.45 | 초고음 비율. 올리면 젖은 노면이나 슬립의 "치치치" 느낌 추가<br>Ultra-high shimmer ratio. Higher = more "sizzle" on wet roads and tire slip |
| 고음 한도 | `haptic_high_shimmer_cap` | 0.05–0.60 | 고음 최대 허용량. 너무 올리면 손 피로감. 적절히 제한하는 역할<br>High shimmer ceiling. Too high = hand fatigue. Keeps sparkle in check |
| 스펙트럼 접착 | `haptic_spectrum_glue_gain` | 0.50–1.50 | 각 대역을 하나로 뭉치는 정도. 올리면 진동이 자연스럽게 섞이고, 낮추면 각각 따로 노는 느낌<br>Spectral glue — blends frequency bands together. Higher = cohesive feel, lower = each band distinct |
| 미드 최소값 | `haptic_mid_min_gain` | 0.30–0.85 | 충돌 같은 강한 이벤트 중에도 유지되는 최소 노면 디테일. 올리면 충격 중에도 도로 느낌 유지<br>Minimum mid-range floor. Ensures road texture persists even during strong impacts |
| 펀치 지속 | `haptic_punch_sustain_blend` | 0.0–1.0 | 충격 후 여운. 올리면 변속/충돌 느낌이 오래 남고, 낮추면 깔끔하게 끊김<br>Impact sustain tail. Higher = shifts/collisions linger, lower = clean cutoff |
| 사이드체인 | `haptic_mastering_sidechain_strength` | 0.0–0.45 | 충격 발생 시 배경 진동을 눌러줌. 올리면 충돌 순간 노면 진동이 빠져서 충격만 부각<br>Ducks background vibration during impacts. Higher = impacts pop out more clearly |
| 소프트 새츄레이션 | `haptic_mastering_soft_saturation` | 0.0–0.45 | 아날로그 따뜻한 느낌. 올리면 전체적으로 부드럽고 둥근 진동. 내리면 디지털적이고 깨끗<br>Analog warmth. Higher = softer, rounder vibrations. Lower = clean and digital |

---

## 6. 문제 해결 / Troubleshooting

### 텔레메트리가 안 들어올 때 / No telemetry

1. Forza: Settings → HUD → Data Out이 **ON**인지 확인
2. IP `127.0.0.1`, Port `5300` 확인
3. Windows 방화벽이 UDP 5300을 차단하고 있지 않은지 확인
4. **Game Pass/MS Store 버전**: 루프백 예외가 필요할 수 있습니다.
   관리자 PowerShell에서 실행:
   ```
   CheckNetIsolation LoopbackExempt -a -n="Microsoft.SunriseBaseGame_8wekyb3d8bbwe"
   ```

1. Confirm Data Out is **ON** in Forza: Settings → HUD
2. Verify IP `127.0.0.1`, Port `5300`
3. Check Windows Firewall is not blocking UDP 5300
4. **Game Pass/MS Store**: May need loopback exemption.
   Run in admin PowerShell:
   ```
   CheckNetIsolation LoopbackExempt -a -n="Microsoft.SunriseBaseGame_8wekyb3d8bbwe"
   ```

### 컨트롤러가 감지 안 될 때 / Controller not detected

- USB 케이블 또는 블루투스 연결 상태 확인 / Check USB or Bluetooth connection
- Steam이 DualSense를 가로채고 있는지 확인 (아래 참조) / Check if Steam is intercepting (see below)
- HidHide 등 클로킹 소프트웨어 확인 / Check cloaking software like HidHide
- 컨트롤러를 뽑았다 다시 연결 / Unplug and reconnect the controller

### Steam에서 DualSense 설정 / Steam DualSense Configuration

Steam 버전 Forza는 **Steam Input이 켜져 있어야** DualSense를 컨트롤러로 인식합니다.
The Steam version of Forza requires **Steam Input enabled** to recognize DualSense.

1. Steam → 설정 → 컨트롤러 → "PlayStation 컨트롤러 지원" **체크**
   Steam → Settings → Controller → **Check** "PlayStation Controller Support"
2. Forza 속성 → 컨트롤러 → Steam Input 활성화: **기본값 사용** 또는 **강제 켜기**
   Forza Properties → Controller → Steam Input: **Use default** or **Force on**

### Game Pass / MS Store에서 컨트롤러 인식 문제 / Controller not recognized in Game Pass

Game Pass판 Forza에서 DualSense가 컨트롤러로 인식되지 않으면 XInput 매퍼를 사용하세요.
If Game Pass Forza doesn't recognize your DualSense, use an XInput mapper.

- DSX, DS4Windows, DualSenseY 등을 사용하면 DualSense를 Xbox 컨트롤러로 인식시킬 수 있습니다.
  Use tools like DSX, DS4Windows, or DualSenseY to map DualSense as an Xbox controller.

### 햅틱 오디오가 작동하지 않을 때 / Haptic audio not working

DualSense 햅틱은 컨트롤러가 **Windows 오디오 출력 장치**로 인식되어야 작동합니다.
DualSense haptics require the controller to appear as a **Windows audio output device**.

1. DualSense를 **USB**로 연결합니다 (BT도 가능하지만 USB가 안정적)
   Connect via **USB** (BT works but USB is more stable)
2. Windows: 설정 → 시스템 → 소리 → 출력 장치 목록에서 "Wireless Controller" 또는 "DualSense"가 보이는지 확인합니다
   Windows: Settings → System → Sound → verify "Wireless Controller" or "DualSense" in output list
3. **기본 출력 장치를 바꿀 필요 없습니다** — DHE가 자동으로 DualSense를 찾아서 전용으로 출력합니다
   **No need to change your default output** — DHE auto-detects and outputs exclusively to the DualSense
4. 장치가 목록에 안 보이면: 장치 관리자 → "사운드, 비디오 및 게임 컨트롤러"에서 비활성화된 항목 확인
   If not listed: Device Manager → Sound controllers → check for disabled entries
5. 그래도 안 되면: USB 케이블을 교체하거나 다른 USB 포트 시도
   Still not working: try a different USB cable or USB port

> **참고 / Note**: DHE는 WASAPI 4ch @ 48kHz로 DualSense에만 출력합니다.
> 일반 스피커나 헤드폰 출력에는 영향을 주지 않습니다.
> DHE outputs WASAPI 4ch @ 48kHz exclusively to the DualSense.
> Your normal speakers/headphones are completely unaffected.

### 피드백이 너무 약하거나 안 느껴질 때 / Feedback too weak or absent

- Settings 탭에서 Master Gain을 올려보세요 / Increase Master Gain in Settings
- 트리거: `trigger_master_gain` 확인 / Check `trigger_master_gain`
- 햅틱: `haptic_master_gain` 확인 / Check `haptic_master_gain`
- 특정 기능의 스위치가 OFF인지 확인 / Check if a specific feature switch is OFF
- 게임 내 컨트롤러 진동이 OFF인지 확인 (ON이면 충돌) / Confirm in-game vibration is OFF

---

## 7. 진단 도구 / Diagnostics

문제가 해결되지 않을 때, 진단 도구를 사용하세요.
If issues persist, use the diagnostic tools.

### 자가 진단 / Self-Test

컨트롤러, HID 통신, 트리거 저항, UDP 포트를 순서대로 점검합니다.
Tests controller, HID, trigger resistance, and UDP port in sequence.

| 방법 / Method | 실행 / Run |
|---------------|-----------|
| 배치 파일 / Batch file | `DHE_SelfTest.bat` 더블클릭 / double-click |
| 명령줄 / Command line | `DHE.exe --self-test` |

### 진단 내보내기 / Export Diagnostics

GitHub Issue 제출 시 첨부할 진단 번들을 생성합니다.
Creates a diagnostic bundle to attach when filing a GitHub Issue.

| 방법 / Method | 실행 / Run |
|---------------|-----------|
| 배치 파일 / Batch file | `DHE_ExportDiagnostics.bat` 더블클릭 / double-click |
| 명령줄 / Command line | `DHE.exe --export-diagnostics` |

---

## 8. FAQ

**Q: DHE를 켠 채로 Forza를 재시작해도 되나요?**
A: 네. DHE는 텔레메트리가 끊기면 자동 대기, 다시 들어오면 자동 재개합니다.

**Q: Can I restart Forza while DHE is running?**
A: Yes. DHE auto-idles when telemetry stops, and resumes when it returns.

---

**Q: USB와 블루투스 중 뭐가 좋나요?**
A: **USB를 사용하세요.** 블루투스는 현재 검증되지 않았으며, 햅틱 오디오 출력이 불안정하거나 작동하지 않을 수 있습니다.

**Q: USB or Bluetooth — which is better?**
A: **Use USB.** Bluetooth is currently unverified — haptic audio output may be unstable or not work at all.

---

**Q: 다른 레이싱 게임에도 되나요?**
A: Forza Horizon 6 의 Data Out 프로토콜에 맞춰 개발되었습니다. 동일 포맷을 사용하는 게임이라면 작동할 수 있습니다.

**Q: Does it work with other racing games?**
A: DHE is built for the Forza Horizon 6 Data Out protocol. It may work with games that use the same UDP format.

---

**Q: 세팅을 망쳤어요. 초기화하려면?**
A: Settings 탭 하단의 "Reset to defaults" 버튼을 누르세요.

**Q: I messed up my settings. How to reset?**
A: Press "Reset to defaults" at the bottom of the Settings tab.

---

**Q: 여러 컨트롤러를 동시에 쓸 수 있나요?**
A: 아니요. DHE는 첫 번째로 감지된 DualSense 1개만 지원합니다.

**Q: Can I use multiple controllers at once?**
A: No. DHE supports only the first detected DualSense.

---

**Q: DHE가 CPU를 많이 먹나요?**
A: 아닙니다. 오디오 엔진은 48kHz 실시간 처리지만 CPU 점유율은 1~3% 수준입니다.

**Q: Does DHE use a lot of CPU?**
A: No. The audio engine runs at 48kHz real-time but typically uses only 1–3% CPU.

---

**Q: 설정을 친구에게 공유하려면?**
A: `data/user_preferences.json` 파일을 복사해서 전달하면 됩니다. 상대방이 같은 경로에 넣으면 그대로 적용됩니다.

**Q: How do I share my settings with a friend?**
A: Copy `data/user_preferences.json` and send it. They place it in the same path and it applies directly.

---

**Q: DHE 실행 중에 컨트롤러를 뽑으면?**
A: DHE가 연결 끊김을 감지하고 대기 상태로 전환됩니다. 다시 꽂으면 자동 재연결됩니다.

**Q: What if I unplug the controller while DHE is running?**
A: DHE detects the disconnection and enters standby. Reconnecting resumes automatically.

---

**Q: 게임 소리가 DualSense에서 나와요**
A: Windows 기본 출력 장치가 DualSense로 바뀌어 있을 수 있습니다. Windows 소리 설정에서 기본 출력을 스피커/헤드폰으로 되돌리세요. DHE는 기본 출력과 관계없이 DualSense에 직접 출력합니다.

**Q: Game audio is coming out of my DualSense**
A: Your Windows default output may have switched to DualSense. Set your default output back to speakers/headphones in Windows Sound settings. DHE outputs directly to the DualSense regardless of the default device.
