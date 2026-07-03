"""Central option metadata for DHE 1.1.

Dashboard is the driver-facing status/test screen. Settings is the full tuning room.
Developer is the raw/debug room. This registry is the single source for labels,
ranges, risk hints and UI exposure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Iterable


@dataclass(frozen=True)
class OptionSpec:
    key: str
    label_en: str
    label_ko: str
    category: str
    ui_min: Optional[float] = None
    ui_max: Optional[float] = None
    step: Optional[float] = None
    ui_level: str = "advanced"   # basic / advanced / developer
    risk: str = "safe"           # safe / can_mute_detail / can_clip / can_fatigue
    affects: str = "haptic"      # trigger / haptic / telemetry / debug / system
    description_en: str = ""
    description_ko: str = ""
    dev_min: Optional[float] = None
    dev_max: Optional[float] = None
    curve: str = "linear"
    sensitivity: str = "medium"

    @property
    def min_value(self):
        return self.ui_min

    @property
    def max_value(self):
        return self.ui_max


ADVANCED_SECTIONS = [
    ("Trigger feature switches", [
        OptionSpec("enable_gear_shift_brake", "L2 shift thump", "L2 변속 충격", "Trigger", None, None, None, "advanced", "safe", "trigger"),
        OptionSpec("enable_abs", "L2 ABS pulse", "L2 ABS 반복감", "Trigger", None, None, None, "advanced", "safe", "trigger"),
        OptionSpec("enable_left_road_texture", "L2 road texture", "L2 노면 질감", "Trigger", None, None, None, "advanced", "safe", "trigger"),
        OptionSpec("enable_gear_shift", "R2 shift thump", "R2 변속 충격", "Trigger", None, None, None, "advanced", "safe", "trigger"),
        OptionSpec("enable_rev_limiter", "R2 redline buzz", "R2 레드라인 진동", "Trigger", None, None, None, "advanced", "safe", "trigger",
                   "레드라인에 다다르면 R2가 부르르 떨림. 손끝으로 변속 타이밍을 느낄 수 있음.",
                   "레드라인에 다다르면 R2가 부르르 떨림. 손끝으로 변속 타이밍을 느낄 수 있음."),
        OptionSpec("enable_rev_limiter_pattern", "R2 rev limiter pattern", "R2 리미터 패턴", "Trigger", None, None, None, "advanced", "safe", "trigger"),
        OptionSpec("enable_wheelspin_buzz", "R2 wheelspin buzz", "R2 휠스핀 진동", "Trigger", None, None, None, "advanced", "safe", "trigger"),
        OptionSpec("enable_right_road_texture", "R2 road texture", "R2 노면 질감", "Trigger", None, None, None, "advanced", "safe", "trigger"),
        OptionSpec("enable_trigger_positioned_vibration", "Gear-positioned vibration", "기어 위치 기반 진동", "Trigger", None, None, None, "advanced", "safe", "trigger",
                   "현재 기어/부하에 따라 R2 트리거의 진동 위치가 이동함.",
                   "현재 기어/부하에 따라 R2 트리거의 진동 위치가 이동함."),
        OptionSpec("enable_tire_scrub_buzz", "R2 tire scrub", "R2 타이어 스크럽", "Trigger", None, None, None, "advanced", "safe", "trigger"),
        OptionSpec("enable_idle_buzz", "R2 idle buzz", "R2 아이들 진동", "Trigger", None, None, None, "advanced", "safe", "trigger"),
    ]),
    ("Driving feedback", [
        OptionSpec("predictive_abs_enabled", "Predictive ABS (L2)", "예측형 ABS (L2)", "Trigger", None, None, None, "advanced", "safe", "trigger",
                   "강한 브레이킹 중 슬립 접근 시 L2 저항 증가, 슬립 발생 시 펄스",
                   "Increases L2 resistance as tires approach lockup, pulses when slipping"),
        OptionSpec("predictive_abs_strength", "Predictive ABS strength", "예측형 ABS 세기", "Trigger", 0.0, 1.5, 0.05, "advanced", "safe", "trigger"),
        OptionSpec("predictive_abs_slip_threshold", "Predictive ABS threshold", "예측형 ABS 임계값", "Trigger", 0.1, 0.8, 0.05, "advanced", "safe", "trigger"),
        OptionSpec("throttle_traction_enabled", "Throttle traction (R2)", "스로틀 트랙션 (R2)", "Trigger", None, None, None, "advanced", "safe", "trigger",
                   "구동 바퀴 슬립 시 R2 저항 변화로 그립 상실 전달",
                   "R2 resistance changes when driven wheels lose grip under throttle"),
        OptionSpec("throttle_traction_strength", "Traction strength", "트랙션 세기", "Trigger", 0.0, 1.5, 0.05, "advanced", "safe", "trigger"),
        OptionSpec("throttle_traction_slip_threshold", "Traction threshold", "트랙션 임계값", "Trigger", 0.1, 0.8, 0.05, "advanced", "safe", "trigger"),
        OptionSpec("drift_fade_enabled", "Drift fade", "드리프트 페이드", "Trigger", None, None, None, "advanced", "safe", "trigger",
                   "지속 드리프트 중 트랙션/휠스핀 노이즈 감쇄",
                   "Attenuates traction/wheelspin noise during sustained drift"),
        OptionSpec("drift_fade_strength", "Drift fade amount", "드리프트 감쇄량", "Trigger", 0.0, 1.0, 0.05, "advanced", "safe", "trigger"),
        OptionSpec("drift_fade_min_speed_kmh", "Drift min speed", "드리프트 최소 속도", "Trigger", 20.0, 100.0, 5.0, "advanced", "safe", "trigger"),
    ]),
    ("Haptic feature switches", [
        OptionSpec("enable_haptic_audio", "DualSense haptic audio", "듀얼센스 햅틱 오디오", "Haptic", None, None, None, "advanced", "safe", "haptic"),
        OptionSpec("haptic_idle_haptics_enabled", "Idle engine vibration", "아이들 엔진 진동", "Haptic", None, None, None, "advanced", "safe", "haptic",
                   "정차 시 엔진 공회전 진동. 끄면 정차 시 조용함.",
                   "정차 시 엔진 공회전 진동. 끄면 정차 시 조용함."),
        OptionSpec("haptic_vehicle_flavor_enabled", "Vehicle body cues", "차체 반응 햅틱", "Haptic", None, None, None, "advanced", "safe", "haptic",
                   "브레이크 수반, ABS 진동, 부스트/토크 서지, 구동계 느낌. 끄면 노면+이벤트만 남음.",
                   "브레이크 수반, ABS 진동, 부스트/토크 서지, 구동계 느낌. 끄면 노면+이벤트만 남음."),
        OptionSpec("haptic_spatial_haptics_enabled", "Spatial haptics", "공간감 햅틱", "Haptic", None, None, None, "advanced", "safe", "haptic"),
        OptionSpec("haptic_rpm_texture_enabled", "RPM body texture", "RPM 바디 텍스처", "Haptic", None, None, None, "advanced", "safe", "haptic"),
        OptionSpec("haptic_body_motion_enabled", "Body motion (pitch/roll)", "차체 모션 (피칭/롤)", "Haptic", None, None, None, "advanced", "safe", "haptic"),
        OptionSpec("haptic_traction_pulse_enabled", "Traction pulse", "트랙션 펄스", "Haptic", None, None, None, "advanced", "safe", "haptic"),        OptionSpec("haptic_mastering_enabled", "Audio mastering", "오디오 마스터링", "Haptic", None, None, None, "advanced", "safe", "haptic",
                   "ON: 내부 마스터링 후처리 적용. OFF: 마스터링 없이 원본 출력.",
                   "ON: 내부 마스터링 후처리 적용. OFF: 마스터링 없이 원본 출력."),    ]),
    ("Trigger output", [
        OptionSpec("trigger_master_gain", "Trigger overall strength", "트리거 전체 세기", "Trigger", 0.0, 1.80, 0.01, "advanced", "safe", "trigger", "전체 트리거 피드백을 한번에 키우거나 줄입니다. 0으로 내리면 트리거 피드백 전부 꺼짐.", "전체 트리거 피드백을 한번에 키우거나 줄입니다. 0으로 내리면 트리거 피드백 전부 꺼짐.", 0.0, 2.5),
        OptionSpec("trigger_l2_gain", "L2 (brake) strength", "L2 (브레이크) 세기", "Trigger", 0.0, 2.00, 0.05, "advanced", "safe", "trigger",
                   "L2 브레이크 쪽 트리거만 따로 세기 조절. 0이면 L2 피드백 꺼짐.",
                   "L2 브레이크 쪽 트리거만 따로 세기 조절. 0이면 L2 피드백 꺼짐."),
        OptionSpec("trigger_r2_gain", "R2 (throttle) strength", "R2 (가속) 세기", "Trigger", 0.0, 2.00, 0.05, "advanced", "safe", "trigger",
                   "R2 가속 쪽 트리거만 따로 세기 조절. 0이면 R2 피드백 꺼짐.",
                   "R2 가속 쪽 트리거만 따로 세기 조절. 0이면 R2 피드백 꺼짐."),
        OptionSpec("trigger_shift_kick_gain", "Shift trigger kick", "변속 트리거 킥", "Trigger", 0.0, 2.50, 0.01, "advanced", "safe", "trigger",
                   "변속할 때 트리거가 '탁' 차는 느낌. 0이면 킥 꺼짐.",
                   "변속할 때 트리거가 '탁' 차는 느낌. 0이면 킥 꺼짐."),
        OptionSpec("trigger_shift_clack_gain", "Shift trigger engagement", "변속 트리거 철컥", "Trigger", 0.0, 2.50, 0.01, "advanced", "safe", "trigger",
                   "변속 후 기어가 '철컥' 물리는 느낌. 0이면 꺼짐.",
                   "변속 후 기어가 '철컥' 물리는 느낌. 0이면 꺼짐."),
        OptionSpec("trigger_wheelspin_gain", "R2 wheelspin chatter", "R2 휠스핀 떨림", "Trigger", 0.0, 1.80, 0.01, "advanced", "safe", "trigger",
                   "바퀴가 헛돌 때 R2에 오는 떨림. 0이면 꺼짐.",
                   "바퀴가 헛돌 때 R2에 오는 떨림. 0이면 꺼짐."),
        OptionSpec("trigger_abs_gain", "L2 ABS chatter", "L2 ABS 떨림", "Trigger", 0.0, 1.80, 0.01, "advanced", "safe", "trigger",
                   "급브레이크 시 ABS가 작동하면서 L2가 두두두 떨리는 느낌. 0이면 꺼짐.",
                   "급브레이크 시 ABS가 작동하면서 L2가 두두두 떨리는 느낌. 0이면 꺼짐."),
        OptionSpec("enable_brake_resistance", "Brake resistance", "브레이크 저항", "Trigger", None, None, None, "advanced", "safe", "trigger",
                   "브레이크를 밟으면 L2가 점점 묵직해짐.",
                   "브레이크를 밟으면 L2가 점점 묵직해짐."),
        OptionSpec("enable_throttle_resistance", "Throttle resistance", "가속 저항", "Trigger", None, None, None, "advanced", "safe", "trigger",
                   "가속을 밟으면 R2가 점점 묵직해짐.",
                   "가속을 밟으면 R2가 점점 묵직해짐."),
        OptionSpec("adaptive_acceleration_depth", "Resistance depth", "저항 깊이", "Trigger", 0.00, 1.50, 0.01, "advanced", "safe", "trigger",
                   "트리거를 누를 때 저항이 얼마나 깊은 곳에서 시작되는지. 올리면 더 깊이 눌러야 저항이 시작됨.",
                   "트리거를 누를 때 저항이 얼마나 깊은 곳에서 시작되는지. 올리면 더 깊이 눌러야 저항이 시작됨."),
        OptionSpec("trigger_brake_gain", "Brake resistance gain", "브레이크 저항 세기", "Trigger", 0.0, 2.00, 0.05, "advanced", "safe", "trigger",
                   "브레이크 밟을 때 L2가 뻑뻑해지는 정도. 올리면 더 단단하고, 0이면 저항 없음.",
                   "브레이크 밟을 때 L2가 뻑뻑해지는 정도. 올리면 더 단단하고, 0이면 저항 없음."),
        OptionSpec("brake_max_force", "Brake max resistance", "브레이크 최대 저항", "Trigger", 1, 8, 1, "advanced", "safe", "trigger",
                   "브레이크 꺼지 눌렀을 때 최대 저항. 단계가 높을수록 더 묵직함.",
                   "브레이크 꺼지 눌렀을 때 최대 저항. 단계가 높을수록 더 묵직함."),
        OptionSpec("throttle_max_force", "Throttle max resistance", "가속 최대 저항", "Trigger", 1, 15, 1, "advanced", "safe", "trigger",
                   "가속 꺼지 눌렀을 때 최대 저항. 단계가 높을수록 더 묵직함.",
                   "가속 꺼지 눌렀을 때 최대 저항. 단계가 높을수록 더 묵직함."),
        OptionSpec("brake_deadzone", "Brake deadzone", "브레이크 데드존", "Trigger", 0, 120, 5, "advanced", "safe", "trigger",
                   "브레이크를 이 정도 눌러야 저항이 시작됨. 높이면 살짝 눌렀을 때는 가벼움.",
                   "브레이크를 이 정도 눌러야 저항이 시작됨. 높이면 살짝 눌렀을 때는 가벼움."),
        OptionSpec("enable_brake_static_wall", "Brake static wall", "브레이크 스태틱월", "Trigger", None, None, None, "advanced", "safe", "trigger",
                   "트리거 중간에 딱딱한 벽이 걸려서 브레이크 밟는 느낌이 남. 위치와 강도 조절 가능.",
                   "트리거 중간에 딱딱한 벽이 걸려서 브레이크 밟는 느낌이 남. 위치와 강도 조절 가능."),
        OptionSpec("brake_static_wall_at", "Static wall position", "스태틱월 위치", "Trigger", 80, 220, 5, "advanced", "safe", "trigger",
                   "트리거를 얼마나 눌렀을 때 벽이 걸리는지. 낮추면 얼른 위치, 높이면 깊은 위치.",
                   "트리거를 얼마나 눌렀을 때 벽이 걸리는지. 낮추면 얼른 위치, 높이면 깊은 위치."),
        OptionSpec("brake_static_wall_force", "Static wall strength", "스태틱월 강도", "Trigger", 50, 255, 5, "advanced", "safe", "trigger",
                   "벽의 세기. 높이면 더 단단하게 버틴.",
                   "벽의 세기. 높이면 더 단단하게 버틴."),
        OptionSpec("accel_deadzone", "Throttle deadzone", "가속 데드존", "Trigger", 0, 120, 5, "advanced", "safe", "trigger",
                   "가속을 이 정도 눌러야 저항이 시작됨. 높이면 살짝 눌렀을 때는 가벼움.",
                   "가속을 이 정도 눌러야 저항이 시작됨. 높이면 살짝 눌렀을 때는 가벼움."),
        OptionSpec("rev_limit_ratio", "Rev limiter threshold", "레드라인 작동 시점", "Trigger", 0.50, 0.99, 0.01, "advanced", "safe", "trigger",
                   "RPM이 이 비율에 도달하면 레드라인 피드백이 시작됨. 낮추면 더 일찍 느껴짐.",
                   "RPM이 이 비율에 도달하면 레드라인 피드백이 시작됨. 낮추면 더 일찍 느껴짐."),
    ]),
    ("Haptic core balance", [
        OptionSpec("haptic_master_gain", "Overall haptics", "전체 진동 세기", "Haptic", 0.10, 0.80, 0.01, "advanced", "safe", "haptic",
                   "모든 진동의 전체 세기. 올리면 전부 강해지고, 내리면 전부 약해짐.", "모든 진동의 전체 세기. 올리면 전부 강해지고, 내리면 전부 약해짐.", dev_min=0.0, dev_max=1.2),
        OptionSpec("haptic_fatigue_control", "Vibration sustain", "진동 유지량", "Haptic", 0.0, 1.0, 0.01, "advanced", "safe", "haptic",
                   "진동을 얼마나 유지할지. 낮추면 진동이 줄어서 손이 편하고, 올리면 진동이 꼼꼼하게 유지됨.",
                   "진동을 얼마나 유지할지. 낮추면 진동이 줄어서 손이 편하고, 올리면 진동이 꼼꼼하게 유지됨."),
        OptionSpec("haptic_bass_foundation_gain", "Low rumble", "저음 울림", "Haptic", 0.0, 3.0, 0.01, "advanced", "can_mute_detail", "haptic",
                   "▼ Lower: less 'body shaking' feel. ▲ Higher: more bass thump.", "▼ 낮추면: 차체가 울리는 느낌 감소. ▲ 높이면: 쿵쿵거림 증가.", dev_min=0.0, dev_max=3.0),
        OptionSpec("haptic_sub_bass_boost", "Deep bass", "깊은 저음", "Haptic", 0.0, 0.54, 0.01, "advanced", "can_mute_detail", "haptic",
                   "▼ Lower: cleaner feel. ▲ Higher: more 'engine idle' type rumble.", "▼ 낮추면: 깔끔한 느낌. ▲ 높이면: 공회전 같은 웅웅거림.", 0.0, 0.54),
        OptionSpec("haptic_mid_texture_balance", "Road detail", "노면 디테일", "Haptic", 0.60, 1.60, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: smoother ride. ▲ Higher: more road texture detail.", "▼ 낮추면: 부드러운 승차감. ▲ 높이면: 노면 질감 선명.", dev_min=0.0, dev_max=2.5),
        OptionSpec("haptic_high_edge_gain", "Sharp edges", "날카로운 느낌", "Haptic", 0.0, 3.0, 0.01, "advanced", "can_fatigue", "haptic",
                   "▼ Lower: softer impacts. ▲ Higher: sharper kerb/bump feel.", "▼ 낮추면: 부드러운 충격. ▲ 높이면: 연석/요철 날카롭게.", dev_min=0.0, dev_max=3.0),
        OptionSpec("haptic_high_shimmer_ratio", "High-freq sparkle", "고음 반짝임", "Haptic", 0.0, 0.45, 0.005, "advanced", "can_fatigue", "haptic",
                   "▼ Lower: less tire slip buzz. ▲ Higher: more slip/wet 'sizzle'.", "▼ 낮추면: 타이어 미끄러짐 진동 감소. ▲ 높이면: 슬립/젖은 노면 지직거림.", 0.0, 0.45),
        OptionSpec("haptic_high_shimmer_cap", "High-freq allowance", "고음 허용량", "Haptic", 0.05, 0.60, 0.01, "advanced", "can_fatigue", "haptic",
                   "▼ Lower: softer, less fatiguing. ▲ Higher: more sharp/sizzly high-freq detail (can tire hands).",
                   "▼ 낮추면: 부드럽고 피로↓. ▲ 높이면: 날카로운 고음 디테일↑ (손 피로 주의).", 0.05, 0.60),
        OptionSpec("haptic_spectrum_glue_gain", "Cohesion", "조화감", "Haptic", 0.50, 1.50, 0.01, "advanced", "can_mute_detail", "haptic",
                   "▼ Lower: distinct layers. ▲ Higher: blended, unified feel.", "▼ 낮추면: 각 진동이 분리됨. ▲ 높이면: 하나로 뭉쳐진 느낌.", 0.0, 2.2),
        OptionSpec("haptic_mid_min_gain", "Detail floor", "디테일 바닥", "Haptic", 0.30, 0.85, 0.01, "advanced", "can_mute_detail", "haptic",
                   "Minimum road detail even when events are loud.", "충격 이벤트 중에도 유지되는 최소 노면 디테일.", dev_min=0.0, dev_max=1.0),
        OptionSpec("haptic_punch_sustain_blend", "Impact sustain", "충격 지속", "Haptic", 0.0, 1.0, 0.01, "advanced", "can_fatigue", "haptic",
                   "▼ Lower: quick hits. ▲ Higher: lingering impact feel.", "▼ 낮추면: 짧은 충격. ▲ 높이면: 충격이 오래 남음."),
        OptionSpec("haptic_mastering_sidechain_strength", "Impact texture ducking", "충격 시 노면 감쇄", "Haptic", 0.0, 0.45, 0.01, "advanced", "can_mute_detail", "haptic",
                   "▼ Lower: road texture stays during impacts. ▲ Higher: road fades when collisions/shifts hit.",
                   "▼ 낮추면: 충돌/변속 중에도 노면 유지. ▲ 높이면: 충격 시 노면 진동이 줄어듦."),
        OptionSpec("haptic_mastering_soft_saturation", "Warmth", "따뜻한 느낌", "Haptic", 0.0, 0.45, 0.01, "advanced", "can_clip", "haptic",
                   "▼ Lower: cleaner. ▲ Higher: warmer, more analog feel.", "▼ 낮추면: 깔끔함. ▲ 높이면: 따뜻하고 아날로그 느낌."),
    ]),
    ("Road / tire detail", [
        OptionSpec("haptic_road_gain", "Road surface feel", "노면 느낌", "Road", 0.0, 1.2, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: smoother roads. ▲ Higher: more asphalt texture.", "▼ 낮추면: 매끄러운 도로. ▲ 높이면: 아스팔트 질감 강조."),
        OptionSpec("haptic_texture_palette_strength", "Surface variety", "노면 종류 구분", "Road", 0.0, 1.8, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: all surfaces similar. ▲ Higher: gravel/dirt/grass distinct.", "▼ 낮추면: 모든 노면 비슷. ▲ 높이면: 자갈/흙/잔디 구분 선명."),
        OptionSpec("haptic_gravel_gain", "Offroad intensity", "오프로드 강도", "Road", 0.0, 1.8, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: gentler offroad. ▲ Higher: more gravel/dirt rumble.", "▼ 낮추면: 부드러운 오프로드. ▲ 높이면: 자갈/흙 덜컹거림 강조."),
        OptionSpec("haptic_tire_scrub_texture_strength", "Tire scrub", "타이어 긁힘", "Road", 0.0, 2.0, 0.01, "advanced", "can_fatigue", "haptic",
                   "▼ Lower: less tire friction feel. ▲ Higher: more scrubbing sensation.", "▼ 낮추면: 타이어 마찰감 감소. ▲ 높이면: 타이어 긁히는 느낌 강조."),
        OptionSpec("haptic_grip_edge_high_strength", "Grip limit warning", "그립 한계 경고", "Road", 0.0, 2.0, 0.01, "advanced", "can_fatigue", "haptic",
                   "▼ Lower: subtler warning. ▲ Higher: clearer 'about to slide' signal.", "▼ 낮추면: 은은한 경고. ▲ 높이면: '곧 미끄러짐' 신호 선명."),
        OptionSpec("haptic_slip_sizzle_strength", "Slip buzz", "슬립 지직거림", "Road", 0.0, 2.0, 0.01, "advanced", "can_fatigue", "haptic",
                   "▼ Lower: quieter slip. ▲ Higher: more tire slip 'sizzle'.", "▼ 낮추면: 조용한 슬립. ▲ 높이면: 타이어 미끄러짐 지직거림 강조."),
        OptionSpec("haptic_drift_breakaway_strength", "Rear breakaway", "뒷바퀴 이탈", "Road", 0.0, 2.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: subtle slide start. ▲ Higher: clear 'rear is breaking loose'.", "▼ 낮추면: 미묘한 슬라이드 시작. ▲ 높이면: '뒷바퀴 빠짐' 명확."),
    ]),
    ("Shift / drivetrain", [
        OptionSpec("haptic_shift_master_gain", "Gear shift overall", "기어변속 전체", "Shift", 0.0, 2.2, 0.01, "advanced", "can_clip", "haptic",
                   "▼ Lower: softer shifts. ▲ Higher: punchier gear changes.", "▼ 낮추면: 부드러운 변속. ▲ 높이면: 변속 충격 강조.", dev_min=0.0, dev_max=3.0),
        OptionSpec("haptic_shift_click_strength", "Shift click", "변속 클릭", "Shift", 0.0, 2.0, 0.01, "advanced", "can_fatigue", "haptic",
                   "▼ Lower: softer engagement. ▲ Higher: sharper 'click' feel.", "▼ 낮추면: 부드러운 체결. ▲ 높이면: 날카로운 '철컥' 느낌."),
        OptionSpec("haptic_shift_clunk_strength", "Shift thunk", "변속 쿵", "Shift", 0.0, 2.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: lighter. ▲ Higher: heavier mechanical feel.", "▼ 낮추면: 가벼움. ▲ 높이면: 묵직한 기계적 느낌."),
        OptionSpec("haptic_shift_body_kick_strength", "Shift body kick", "변속 차체 덜컥", "Shift", 0.0, 2.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: no body reaction. ▲ Higher: whole car 'lurches' on shift.", "▼ 낮추면: 차체 반응 없음. ▲ 높이면: 변속 시 차체가 덜컥."),
        OptionSpec("haptic_shift_bass_strength", "Shift bass", "변속 저음", "Shift", 0.0, 2.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: lighter shifts. ▲ Higher: deeper 'thump' on shift.", "▼ 낮추면: 가벼운 변속. ▲ 높이면: 변속 시 깊은 쿵."),
        OptionSpec("haptic_shift_engagement_strength", "Shift torque engagement", "변속 토크 전달", "Shift", 0.0, 2.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: no post-shift thump. ▲ Higher: feel torque hit after shift.", "▼ 낮추면: 변속 후 조용. ▲ 높이면: 변속 후 토크가 '쿵' 전달됨."),
        OptionSpec("haptic_accel_onset_strength", "Accel onset impact", "급가속 시작 충격", "Shift", 0.0, 2.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: no launch feel. ▲ Higher: 'thump' when stomping gas.", "▼ 낮추면: 가속 시작 조용. ▲ 높이면: 가속 시작 순간 '훅' 충격."),
        OptionSpec("haptic_decel_onset_strength", "Decel onset impact", "급감속 시작 충격", "Shift", 0.0, 2.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: no braking hit. ▲ Higher: 'thud' at hard brake entry.", "▼ 낮추면: 브레이킹 조용. ▲ 높이면: 급브레이크 시작 '쿵'."),
    ]),
    ("Impact / space", [
        OptionSpec("haptic_impact_master_gain", "Collisions overall", "충돌 전체", "Impact", 0.0, 2.2, 0.01, "advanced", "can_clip", "haptic",
                   "▼ Lower: softer crashes. ▲ Higher: harder collision impacts.", "▼ 낮추면: 약한 충돌. ▲ 높이면: 강한 충돌 충격.", dev_min=0.0, dev_max=3.0),
        OptionSpec("haptic_impact_sub_strength", "Impact bass", "충격 저음", "Impact", 0.0, 2.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: lighter hits. ▲ Higher: deeper 'thud' on impact.", "▼ 낮추면: 가벼운 충격. ▲ 높이면: 충돌 시 깊은 쿵."),
        OptionSpec("haptic_impact_crack_high_strength", "Impact crack", "충격 날카로움", "Impact", 0.0, 2.0, 0.01, "advanced", "can_fatigue", "haptic",
                   "▼ Lower: muffled. ▲ Higher: sharper 'crack' on collision.", "▼ 낮추면: 먹먹함. ▲ 높이면: 충돌 시 날카로운 크랙."),
        OptionSpec("haptic_spatial_width", "L/R separation", "좌우 분리", "Space", 0.60, 1.80, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: centered feel. ▲ Higher: wider L/R steering feedback.", "▼ 낮추면: 중앙 집중. ▲ 높이면: 좌우 핸들 피드백 분리.", dev_min=0.0, dev_max=2.5),
        OptionSpec("haptic_front_rear_contrast", "Front/rear clarity", "전후 구분", "Space", 0.0, 1.8, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: front=rear. ▲ Higher: clearer front wheel vs rear wheel.", "▼ 낮추면: 앞뒤 동일. ▲ 높이면: 앞바퀴/뒷바퀴 구분 선명."),
        OptionSpec("haptic_final_side_boost", "Directional boost", "방향성 강조", "Space", 0.0, 1.2, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: mono-like. ▲ Higher: exaggerated left/right cues.", "▼ 낮추면: 모노 느낌. ▲ 높이면: 좌우 방향 강조."),
    ]),
    ("Extended telemetry", [
        OptionSpec("haptic_rpm_texture_gain", "RPM vibration", "RPM 진동", "1.0", 0.0, 1.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: less engine rev feel. ▲ Higher: more RPM body shake. ⚠️ Separate from 'body motion'.",
                   "▼ 낮추면: 엔진 회전 진동 감소. ▲ 높이면: RPM 차체 떨림 강조. ⚠️ '차체 모션'과 별개.", 0.0, 1.5),
        OptionSpec("haptic_body_motion_gain", "Pitch/roll motion", "피칭/롤 모션", "1.0", 0.0, 0.90, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: less dive/lean. ▲ Higher: more braking dive & cornering lean.", "▼ 낮추면: 다이브/기울기 감소. ▲ 높이면: 브레이크 다이브 + 코너링 기울기.", 0.0, 1.2),
        OptionSpec("haptic_traction_pulse_gain", "Traction pulse", "트랙션 펄스", "1.0", 0.0, 0.80, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: less wheel speed diff feel. ▲ Higher: more AWD/RWD pulse.", "▼ 낮추면: 휠 속도 차이 감소. ▲ 높이면: AWD/RWD 구동력 차이 펄스.", 0.0, 1.0),
    ]),
    ("Engine enhancement", [
        OptionSpec("haptic_rpm_harmonics_strength", "Cylinder harmonics", "실린더 배음", "Engine", 0.0, 1.5, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: generic engine. ▲ Higher: feel 4/6/8-cyl character.", "▼ 낮추면: 엔진 느낌 일반. ▲ 높이면: 4/6/8기통 특성 느낌."),
        OptionSpec("haptic_redline_warning_strength", "Redline warning pulse", "레드라인 경고", "Engine", 0.0, 2.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: subtle warning. ▲ Higher: urgent shift-now pulse.", "▼ 낮추면: 은은한 경고. ▲ 높이면: 급히 변속하라는 강한 펄스."),
        OptionSpec("haptic_redline_warning_width", "Redline haptic width", "레드라인 햅틱 구간폭", "Engine", 0.03, 0.20, 0.01, "advanced", "safe", "haptic",
                   "▼ Narrower: late warning. ▲ Wider: earlier onset for low-rev cars.", "▼ 좁으면: 늦은 경고. ▲ 넓으면: 저회전 차에서 더 일찍 경고."),
        OptionSpec("haptic_turbo_spool_strength", "Turbo spool-up", "터보 스풀업", "Engine", 0.0, 1.5, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: quiet turbo. ▲ Higher: feel boost building.", "▼ 낮추면: 터보 조용. ▲ 높이면: 부스트 올라오는 느낌."),
        OptionSpec("haptic_engine_braking_strength", "Engine braking", "엔진 브레이킹", "Engine", 0.0, 1.5, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: coast freely. ▲ Higher: feel engine resistance on decel.", "▼ 낮추면: 자유롭게 코스팅. ▲ 높이면: 감속 시 엔진 저항감."),
        OptionSpec("haptic_corner_exit_strength", "Corner exit torque", "코너 출구 토크", "Engine", 0.0, 1.5, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: smooth power delivery. ▲ Higher: feel power hitting wheels out of turn.",
                   "▼ 낮추면: 부드러운 파워. ▲ 높이면: 코너 탈출 시 바퀴에 토크 전달됨."),
        OptionSpec("haptic_engine_start_strength", "Engine start", "시동 시퀀스", "Engine", 0.0, 2.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: silent start. ▲ Higher: feel engine crank on spawn.", "▼ 낮추면: 조용한 시동. ▲ 높이면: 리스폰 시 시동 느낌."),
        OptionSpec("haptic_idle_strength", "Idle rumble", "아이들 럼블", "Engine", 0.0, 1.0, 0.01, "advanced", "safe", "haptic",
                   "▼ Lower: quiet idle. ▲ Higher: muscle-car idle shake.", "▼ 낮추면: 조용한 공회전. ▲ 높이면: 머슬카 아이들 떨림."),
        OptionSpec("enable_trigger_redline_pulse", "R2 redline resistance", "R2 레드라인 저항", "Engine", None, None, None, "advanced", "safe", "trigger",
                   "R2 becomes stiff/pulsing near redline — push-back feel (differs from buzz).",
                   "레드라인 근처에서 R2가 딱딱해지며 펄스로 밀어냄 (진동과 다른 저항감)."),
        OptionSpec("trigger_redline_strength", "Redline trigger strength", "레드라인 트리거 세기", "Engine", 0.3, 2.0, 0.01, "advanced", "safe", "trigger",
                   "▼ Lower: subtle. ▲ Higher: stronger R2 redline pulse.", "▼ 낮추면: 약하게. ▲ 높이면: R2 레드라인 저항 강하게."),
        OptionSpec("redline_warning_width", "Redline warning zone width", "레드라인 경고 구간 폭", "Engine", 0.03, 0.20, 0.01, "advanced", "safe", "trigger",
                   "Fraction of usable RPM range for early warning. Higher = earlier warning for low-rev cars.",
                   "사용 가능 RPM 범위 대비 경고 구간 비율. 높이면 저출력 차에서 더 일찍 경고."),
        OptionSpec("enable_trigger_engine_brake", "L2 engine brake resistance", "L2 엔진 브레이크 저항", "Engine", None, None, None, "advanced", "safe", "trigger",
                   "L2 feels heavier when engine braking at high RPM.", "고RPM에서 스로틀 오프 시 L2가 약간 무거워짐."),
        OptionSpec("trigger_engine_brake_strength", "Engine brake trigger strength", "엔진브레이크 트리거 세기", "Engine", 0.3, 2.0, 0.01, "advanced", "safe", "trigger",
                   "▼ Lower: lighter feel. ▲ Higher: more L2 resistance on decel.", "▼ 낮추면: 가볍게. ▲ 높이면: 감속 시 L2 저항 강하게."),
    ]),
    ("Developer diagnostics", [
        OptionSpec("haptic_signal_boost", "Internal signal boost", "내부 신호 부스트", "Developer", 0.5, 3.0, 0.01, "developer", "can_clip", "haptic"),
        OptionSpec("haptic_limiter_strength", "Limiter strength", "리미터 강도", "Developer", 0.0, 1.0, 0.01, "developer", "can_mute_detail", "haptic"),
        OptionSpec("haptic_transient_limiter_relief", "Transient limiter relief", "트랜지언트 리미터 완화", "Developer", 0.0, 1.0, 0.01, "developer", "can_clip", "haptic"),
        OptionSpec("haptic_telemetry_recording_enabled", "Haptic telemetry recorder", "햅틱 텔레메트리 기록", "Developer", None, None, None, "developer", "safe", "debug"),
        OptionSpec("haptic_telemetry_record_hz", "Haptic recorder rate", "햅틱 기록 Hz", "Developer", 1.0, 60.0, 1.0, "developer", "safe", "debug"),
        OptionSpec("haptic_telemetry_record_path", "Haptic recorder path", "햅틱 기록 경로", "Developer", None, None, None, "developer", "safe", "debug"),
        OptionSpec("diagnostic_capture_seconds", "Diagnostic capture seconds", "진단 캡처 시간", "Developer", 10, 60, 1, "developer", "safe", "debug"),
        OptionSpec("diagnostic_sample_hz", "Diagnostic sample rate", "진단 샘플 Hz", "Developer", 5, 30, 1, "developer", "safe", "debug"),
        OptionSpec("diagnostic_max_size_mb", "Diagnostic max MB", "진단 최대 MB", "Developer", 3, 10, 1, "developer", "safe", "debug"),
    ]),
    ("Bus masters / 버스 밸런스", [
        OptionSpec("haptic_master_gain", "🔊 Master volume", "🔊 전체 볼륨", "Master", 0.0, 2.0, 0.01, "basic", "safe", "haptic",
                   "Layer 1: Overall haptic intensity.", "전체 진동 세기.", 0.0, 2.0),
        OptionSpec("haptic_surface_bus_gain", "🛣️ Surface bus", "🛣️ 노면", "Bus", 0.0, 1.5, 0.01, "standard", "safe", "haptic",
                   "Road texture, gravel, kerb, weather.", "도로, 자갈, 연석, 날씨.", 0.0, 2.0),
        OptionSpec("haptic_engine_bus_gain", "⚙️ Engine bus", "⚙️ 엔진", "Bus", 0.0, 1.5, 0.01, "standard", "safe", "haptic",
                   "RPM, idle, turbo, braking, torque.", "RPM, 아이들, 터보, 엔진브레이크, 토크.", 0.0, 2.0),
        OptionSpec("haptic_vehicle_bus_gain", "🏎️ Vehicle bus", "🏎️ 차체", "Bus", 0.0, 1.5, 0.01, "standard", "safe", "haptic",
                   "Weight transfer, slide, drift, wheelspin.", "하중이동, 슬라이드, 드리프트, 휠스핀.", 0.0, 2.0),
        OptionSpec("haptic_event_bus_gain", "💥 Event bus", "💥 이벤트", "Bus", 0.0, 1.5, 0.01, "standard", "safe", "haptic",
                   "Collision, shift, bump, landing.", "충돌, 변속, 범프, 착지.", 0.0, 2.0),
        OptionSpec("haptic_balance_lr", "↔️ L/R Balance", "↔️ 좌우 밸런스", "Channel", -1.0, 1.0, 0.01, "advanced", "safe", "haptic",
                   "-1.0=Left, 0=Center, +1.0=Right.", "-1.0=왼쪽, 0=중앙, +1.0=오른쪽."),
    ]),
]

# Settings groups: each group has a title, optional "always visible" fields,
# and switch→detail mappings (switch key → list of detail spec keys).
# This drives the collapsible UI in the Settings tab.
#
# ═══════════════════════════════════════════════════════════════════════════
# 설정 그룹 재구성 - 사용자 친화적 구조
# ═══════════════════════════════════════════════════════════════════════════
# 기존: 기술적 분류 (Haptic Core, Road/Tire, Impact/Space...)
# 개선: 기능별 분류 + "뭘 줄이면 뭐가 줄어드는지" 명확하게
# ═══════════════════════════════════════════════════════════════════════════

SETTINGS_GROUPS = [
    # ═══════════════════════════════════════════════════════════════════════════
    # 트리거 → 햅틱 → 고급 순서
    # ═══════════════════════════════════════════════════════════════════════════

    {
        "title": "🕹️ 트리거 / Trigger",
        "description": "[트리거] L2/R2 버튼의 저항감·진동",
        "always": [
            "trigger_master_gain",
            "trigger_l2_gain",
            "trigger_r2_gain",
            # L2 brake
            "trigger_brake_gain",
            "brake_max_force",
            "brake_deadzone",
            # R2 throttle
            "throttle_max_force",
            "accel_deadzone",
            "adaptive_acceleration_depth",
            "rev_limit_ratio",
        ],
        "switches": {
            # ── L2 (brake) ──
            "enable_brake_resistance": [],
            "enable_brake_static_wall": ["brake_static_wall_at", "brake_static_wall_force"],
            "enable_abs": ["trigger_abs_gain"],
            "enable_left_road_texture": [],
            "enable_trigger_engine_brake": ["trigger_engine_brake_strength"],
            # ── L2+R2 (both) ──
            "enable_gear_shift": ["trigger_shift_kick_gain", "trigger_shift_clack_gain"],
            "enable_gear_shift_brake": [],
            # ── R2 (throttle) ──
            "enable_throttle_resistance": [],
            "enable_rev_limiter": [],
            "enable_rev_limiter_pattern": [],
            "enable_trigger_redline_pulse": ["trigger_redline_strength", "redline_warning_width"],
            "enable_wheelspin_buzz": ["trigger_wheelspin_gain"],
            "enable_right_road_texture": [],
            "enable_tire_scrub_buzz": [],
            "enable_trigger_positioned_vibration": [],
            "enable_idle_buzz": [],
        },
    },
    {
        "title": "🎮 햅틱 마스터 / Haptic Master",
        "description": "[햅틱] 전체 세기 + 버스별 비율. 버스를 조절하면 하위 항목 전부에 영향.",
        "always": [
            "enable_haptic_audio",
            "haptic_master_gain",
            "haptic_fatigue_control",
            "haptic_surface_bus_gain",
            "haptic_engine_bus_gain",
            "haptic_vehicle_bus_gain",
            "haptic_event_bus_gain",
        ],
        "switches": {},
    },
    {
        "title": "🛣️ 노면 / Surface",
        "description": "[햅틱] 도로 질감·자갈·연석. → 🛣️노면 버스에 속함.",
        "always": [
            "haptic_road_gain",
            "haptic_gravel_gain",
            "haptic_texture_palette_strength",
        ],
        "switches": {},
    },
    {
        "title": "⚙️ 엔진 / Engine",
        "description": "[햅틱] RPM·터보·엔진브레이크·아이들. → ⚙️엔진 버스에 속함.",
        "always": [
            "haptic_redline_warning_strength",
            "haptic_redline_warning_width",
            "haptic_turbo_spool_strength",
            "haptic_engine_braking_strength",
            "haptic_corner_exit_strength",
            "haptic_engine_start_strength",
        ],
        "switches": {
            "haptic_rpm_texture_enabled": [
                "haptic_rpm_texture_gain",
                "haptic_rpm_harmonics_strength",
            ],
            "haptic_idle_haptics_enabled": [
                "haptic_idle_strength",
            ],
        },
    },
    {
        "title": "💥 이벤트 / Event",
        "description": "[햅틱] 변속·충돌·범프·가감속 충격. → 💥이벤트 버스에 속함.",
        "always": [
            "haptic_shift_master_gain",
            "haptic_shift_click_strength",
            "haptic_shift_clunk_strength",
            "haptic_shift_engagement_strength",
            "haptic_accel_onset_strength",
            "haptic_decel_onset_strength",
            "haptic_impact_master_gain",
            "haptic_impact_sub_strength",
            "haptic_impact_crack_high_strength",
        ],
        "switches": {},
    },
    {
        "title": "🏎️ 차체 / Vehicle",
        "description": "[햅틱] 하중이동·드리프트·그립 한계·타이어. → 🏎️차체 버스에 속함.",
        "always": [
            "haptic_drift_breakaway_strength",
            "haptic_tire_scrub_texture_strength",
            "haptic_grip_edge_high_strength",
            "haptic_slip_sizzle_strength",
        ],
        "switches": {
            "haptic_body_motion_enabled": ["haptic_body_motion_gain"],
            "haptic_traction_pulse_enabled": ["haptic_traction_pulse_gain"],
            "haptic_vehicle_flavor_enabled": [],
        },
    },
    {
        "title": "🔈 공간감 / Spatial",
        "description": "[햅틱] L/R 좌우 분리·전후 구분. 높이면 방향감↑, 낮추면 중앙 집중.",
        "always": [
            "haptic_spatial_width",
            "haptic_front_rear_contrast",
        ],
        "switches": {
            "haptic_spatial_haptics_enabled": ["haptic_final_side_boost"],
        },
    },
    {
        "title": "🎛️ 고급 / Advanced",
        "description": "[햅틱] 내부 오디오 마스터링. 마스터링 ON/OFF로 후처리 제어.",
        "always": [],
        "switches": {
            "haptic_mastering_enabled": [
                "haptic_bass_foundation_gain",
                "haptic_sub_bass_boost",
                "haptic_mid_texture_balance",
                "haptic_high_edge_gain",
                "haptic_high_shimmer_ratio",
                "haptic_high_shimmer_cap",
                "haptic_spectrum_glue_gain",
                "haptic_mid_min_gain",
                "haptic_punch_sustain_blend",
                "haptic_mastering_sidechain_strength",
                "haptic_mastering_soft_saturation",
            ],
        },
    },
]


def settings_groups_resolved():
    """Return SETTINGS_GROUPS with spec objects resolved for each key."""
    out = []
    for grp in SETTINGS_GROUPS:
        always = [SPEC_BY_KEY[k] for k in grp["always"] if k in SPEC_BY_KEY]
        switches = {}
        for sw_key, detail_keys in grp["switches"].items():
            sw_spec = SPEC_BY_KEY.get(sw_key)
            if sw_spec is None:
                continue
            details = [SPEC_BY_KEY[k] for k in detail_keys if k in SPEC_BY_KEY]
            switches[sw_spec] = details
        resolved = {
            "title": grp["title"],
            "always": always,
            "switches": switches,
        }
        # 그룹 설명이 있으면 전달 (UI에서 표시)
        if "description" in grp:
            resolved["description"] = grp["description"]
        out.append(resolved)
    return out


SYSTEM_SECTIONS = [
    ("General", [
        OptionSpec("language", "Language", "언어", "System", None, None, None, "advanced", "safe", "system"),
    ]),
    ("Forza 텔레메트리 수신", [
        OptionSpec("udp_host", "수신 주소", "수신 주소", "Telemetry", None, None, None, "advanced", "safe", "telemetry",
                   "Bind address. 127.0.0.1 = local only, 0.0.0.0 = all interfaces.",
                   "바인드 주소. 127.0.0.1 = 로컬만, 0.0.0.0 = 모든 네트워크."),
        OptionSpec("udp_port", "수신 포트", "수신 포트", "Telemetry", 1, 65535, 1, "advanced", "safe", "telemetry",
                   "Forza → Settings → HUD → Data Out port. Default 5300.",
                   "포르자 설정 → HUD → 데이터 출력 포트와 동일하게 맞춤. 기본 5300."),
        OptionSpec("udp_forward", "텔레메트리 포워딩", "텔레메트리 포워딩", "Telemetry", None, None, None, "advanced", "safe", "telemetry",
                   "ON: copies raw UDP to another app (SimHub, dash apps).",
                   "ON: 수신 데이터를 다른 앱(SimHub, 대시보드 등)에 복사 전달."),
        OptionSpec("udp_forward_to", "포워딩 주소", "포워딩 주소", "Telemetry", None, None, None, "advanced", "safe", "telemetry",
                   "Target host:port (e.g. 127.0.0.1:5301).",
                   "데이터를 보낼 주소:포트 (예: 127.0.0.1:5301)."),
    ]),
    ("Startup / reconnect", [
        OptionSpec("startup_pulse_force", "Startup buzz strength", "시작 진동 세기", "System", 0, 255, 1, "advanced", "safe", "system"),
        OptionSpec("enable_reconnect", "Auto-reconnect", "자동 재연결", "System", None, None, None, "advanced", "safe", "system"),
        OptionSpec("reconnect_interval_s", "Reconnect interval", "재연결 주기", "System", 0.1, 60.0, 0.1, "advanced", "safe", "system"),
    ]),
    ("Game detection", [
        OptionSpec("exit_on_game_close", "Auto-exit when game closes", "게임 종료 시 자동 종료", "System", None, None, None, "advanced", "safe", "system"),
        OptionSpec("game_poll_interval_s", "Game-watch check interval", "게임 감시 주기", "System", 0.5, 30.0, 0.5, "advanced", "safe", "system"),
    ]),
]


def _flatten(sections: Iterable[tuple[str, list[OptionSpec]]]) -> list[OptionSpec]:
    out = []
    for _title, specs in sections:
        out.extend(specs)
    return out

ALL_SPECS = _flatten(ADVANCED_SECTIONS) + _flatten(SYSTEM_SECTIONS)
SPEC_BY_KEY = {s.key: s for s in ALL_SPECS}


def spec_for(key: str) -> OptionSpec | None:
    return SPEC_BY_KEY.get(key)


def bilingual(spec: OptionSpec | str, lang: str = "ko") -> str:
    if isinstance(spec, str):
        key = spec
        spec = SPEC_BY_KEY.get(key)
        if spec is None:
            return key
    return f"{spec.label_ko} / {spec.label_en}" if lang == "ko" else f"{spec.label_en} / {spec.label_ko}"


def label_for(key: str, lang: str = "ko", include_key: bool = False) -> str:
    spec = spec_for(key)
    label = bilingual(spec, lang) if spec else key
    return f"{label}\n{key}" if include_key else label


def sections_as_tuples(sections, *, developer_ranges: bool = False, include_key: bool = False):
    out = []
    for title, specs in sections:
        fields = []
        for s in specs:
            lo = s.dev_min if developer_ranges and s.dev_min is not None else s.ui_min
            hi = s.dev_max if developer_ranges and s.dev_max is not None else s.ui_max
            hint = s.description_ko if s.description_ko else s.description_en
            fields.append((s.key, label_for(s.key, include_key=include_key), lo, hi, hint))
        out.append((title, fields))
    return out


def _strip_developer_mode(sections):
    out = []
    for title, specs in sections:
        shown = [s for s in specs if s.key != "developer_mode"]
        if shown:
            out.append((title, shown))
    return out


def visible_settings_sections():
    """User-facing tuning surface only.

    System/app options (language, UDP, reconnect, game-watch, folders) do not
    belong here because Settings is for haptic/trigger feel tuning only.
    """
    out = []
    for title, specs in ADVANCED_SECTIONS:
        shown = [s for s in specs if s.ui_level != "developer"]
        if shown:
            out.append((title, shown))
    return out


def visible_developer_sections():
    """Developer-only options that are not duplicated in Settings/System.

    Developer is not a second settings editor. It exposes diagnostic/logging
    controls and read-only dumps; raw tuning values are shown through dumps, not
    editable duplicate sliders.
    """
    out = []
    for title, specs in ADVANCED_SECTIONS:
        shown = [s for s in specs if s.ui_level == "developer"]
        if shown:
            out.append((title, shown))
    return out


def visible_advanced_sections(developer_mode: bool = False):
    # Backward compatible name.
    return visible_developer_sections() if developer_mode else visible_settings_sections()


def visible_system_sections(developer_mode: bool = False):
    return _strip_developer_mode(SYSTEM_SECTIONS)


def all_ranges(developer_mode: bool = False):
    out = {}
    for s in ALL_SPECS:
        lo = s.dev_min if developer_mode and s.dev_min is not None else s.ui_min
        hi = s.dev_max if developer_mode and s.dev_max is not None else s.ui_max
        if lo is not None and hi is not None:
            out[s.key] = (lo, hi)
    return out


def core_base_overrides() -> dict:
    """Read DHE Core Base preset values (tries runtime file, then shipped default)."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    candidates = [
        root / "data" / "user_preferences.json",
        root / "data" / "user_preferences.json.default",
    ]
    for p in candidates:
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            presets = raw.get("presets", {})
            core = presets.get("DHE Core Base", {})
            if isinstance(core, dict) and core:
                return dict(core)
        except Exception:
            continue
    return {}


def changed_from_core(settings) -> dict:
    base = core_base_overrides()
    out = {}
    for k, b in base.items():
        if not hasattr(settings, k):
            continue
        cur = getattr(settings, k)
        if cur != b:
            out[k] = {"core": b, "current": cur}
    return out


def changed_from_core_human(settings, *, limit: int = 999, include_keys: bool = False) -> list[str]:
    rows = []
    for key, item in changed_from_core(settings).items():
        label = label_for(key, include_key=include_keys)
        base = item.get("core")
        cur = item.get("current")
        try:
            if isinstance(base, (int, float)) and not isinstance(base, bool) and float(base) != 0.0:
                pct = (float(cur) / float(base) - 1.0) * 100.0
                sign = "+" if pct >= 0 else ""
                rows.append(f"{label}: {sign}{pct:.0f}%  ({base:g} → {float(cur):g})")
            else:
                rows.append(f"{label}: {base} → {cur}")
        except Exception:
            rows.append(f"{label}: {base} → {cur}")
        if len(rows) >= limit:
            break
    return rows


def default_value_for(key: str):
    """100% reference = Settings class default (authoritative source of truth).
    Falls back to Core Base profile if not found in Settings."""
    from config.settings import Settings
    _defaults = Settings()
    val = getattr(_defaults, key, None)
    if val is not None:
        return val
    return core_base_overrides().get(key)


# -- Display conversion types ------------------------------------------------
# A: default=100%  (gain, force 계열)
# B: min~max → 0%~100% 리매핑  (위치, 데드존 계열)
# C: raw×100 → %  (비율 계열, 예: 0.85 → 85%)
# I: 반전 (올리면 약해지는 파라미터 → UI에서 뒤집어 표시)

_REMAP_KEYS = {"brake_static_wall_at", "brake_deadzone", "accel_deadzone"}
_RATIO_KEYS = {"rev_limit_ratio", "redline_warning_width", "haptic_redline_warning_width"}
_INVERTED_KEYS = {"haptic_fatigue_control"}


def _display_type(key: str) -> str:
    """Return display conversion type for a key."""
    if key in _REMAP_KEYS:
        return "remap"
    if key in _RATIO_KEYS:
        return "ratio"
    if key in _INVERTED_KEYS:
        return "inverted"
    return "default"


def is_percent_tuning_key(key: str) -> bool:
    """True when Settings should display this raw numeric value as %-based."""
    spec = spec_for(key)
    if spec is None:
        return False
    if spec.affects not in ("haptic", "trigger"):
        return False
    if spec.ui_level == "developer":
        return False
    dtype = _display_type(key)
    if dtype in ("remap", "ratio", "inverted"):
        return True
    base = default_value_for(key)
    return isinstance(base, (int, float)) and not isinstance(base, bool) and float(base) != 0.0


def percent_from_raw(key: str, raw) -> float | None:
    """Convert raw setting value → display percent."""
    try:
        raw = float(raw)
    except (TypeError, ValueError):
        return None
    dtype = _display_type(key)
    spec = spec_for(key)

    if dtype == "remap" and spec is not None:
        lo, hi = float(spec.ui_min), float(spec.ui_max)
        if hi == lo:
            return 0.0
        return (raw - lo) / (hi - lo) * 100.0

    if dtype == "ratio":
        return raw * 100.0

    if dtype == "inverted" and spec is not None:
        lo, hi = float(spec.ui_min), float(spec.ui_max)
        return (1.0 - (raw - lo) / max(hi - lo, 1e-9)) * 100.0

    # default: base=100%
    base = default_value_for(key)
    if not isinstance(base, (int, float)) or isinstance(base, bool) or float(base) == 0.0:
        return None
    return raw / float(base) * 100.0


def raw_from_percent(key: str, percent: float):
    """Convert display percent → raw value."""
    try:
        percent = float(percent)
    except (TypeError, ValueError):
        return None
    dtype = _display_type(key)
    spec = spec_for(key)

    if dtype == "remap" and spec is not None:
        lo, hi = float(spec.ui_min), float(spec.ui_max)
        return lo + (hi - lo) * percent / 100.0

    if dtype == "ratio":
        return percent / 100.0

    if dtype == "inverted" and spec is not None:
        lo, hi = float(spec.ui_min), float(spec.ui_max)
        return lo + (hi - lo) * (1.0 - percent / 100.0)

    # default: base=100%
    base = default_value_for(key)
    if not isinstance(base, (int, float)) or isinstance(base, bool):
        return None
    return float(base) * percent / 100.0


def percent_slider_range(key: str) -> tuple[float, float] | None:
    """Return (min%, max%) for percent slider display. None = not a percent key."""
    if not is_percent_tuning_key(key):
        return None
    spec = spec_for(key)
    if spec is None or spec.ui_min is None or spec.ui_max is None:
        return None
    lo_pct = percent_from_raw(key, spec.ui_min)
    hi_pct = percent_from_raw(key, spec.ui_max)
    if lo_pct is None or hi_pct is None:
        return None
    return (min(lo_pct, hi_pct), max(lo_pct, hi_pct))


def changed_from_defaults(settings) -> dict:
    """Changed values using user wording: default is 100% / default bool."""
    return changed_from_core(settings)


def changed_from_defaults_human(settings, *, limit: int = 999, include_keys: bool = False) -> list[str]:
    rows = []
    for key, item in changed_from_defaults(settings).items():
        spec = spec_for(key)
        if spec is None and not include_keys:
            continue
        label = label_for(key, include_key=include_keys) if spec is not None else key
        base = item.get("core")
        cur = item.get("current")
        try:
            if isinstance(base, bool):
                rows.append(f"{label}: {'켜짐' if cur else '꺼짐'}")
            elif isinstance(base, (int, float)) and float(base) != 0.0:
                pct = (float(cur) / float(base) - 1.0) * 100.0
                sign = "+" if pct >= 0 else ""
                rows.append(f"{label}: {sign}{pct:.0f}%")
            else:
                rows.append(f"{label}: {base} → {cur}")
        except Exception:
            rows.append(f"{label}: {base} → {cur}")
        if len(rows) >= limit:
            break
    return rows
