# -*- coding: utf-8 -*-
"""Forza Horizon haptic source registry.

Registers all game-specific haptic sources into the core bus framework.
Import this module at app startup to populate HAPTIC_SOURCES.
"""
from dsio.haptics.bus import (
    HapticBus, HapticCategory, HapticSource, register,
)

# ── Surface Bus ──
register(
    HapticSource(
        id="road_texture",
        name_ko="노면 텍스처", name_en="Road Texture",
        bus=HapticBus.SURFACE, category=HapticCategory.ROAD_FEEL,
        settings=("haptic_road_texture_gain",),
        description_ko="아스팔트 노면의 미세한 질감",
        description_en="Fine texture of asphalt surface",
    ),
    HapticSource(
        id="rough_asphalt",
        name_ko="거친 아스팔트", name_en="Rough Asphalt",
        bus=HapticBus.SURFACE, category=HapticCategory.ROAD_FEEL,
        settings=("haptic_road_texture_gain",),
        description_ko="거친 노면의 진동",
        description_en="Vibration from rough road surface",
    ),
    HapticSource(
        id="kerb",
        name_ko="연석", name_en="Kerb/Curb",
        bus=HapticBus.SURFACE, category=HapticCategory.ROAD_FEEL,
        settings=("haptic_kerb_gain",),
        description_ko="연석을 밟았을 때의 충격",
        description_en="Impact when hitting curbs",
    ),
    HapticSource(
        id="gravel",
        name_ko="자갈", name_en="Gravel",
        bus=HapticBus.SURFACE, category=HapticCategory.SURFACE_TYPE,
        settings=("haptic_gravel_gain",),
        description_ko="자갈길 위의 덜컹거림",
        description_en="Rumble on gravel surface",
    ),
    HapticSource(
        id="dirt",
        name_ko="비포장", name_en="Dirt",
        bus=HapticBus.SURFACE, category=HapticCategory.SURFACE_TYPE,
        settings=("haptic_dirt_gain",),
        description_ko="흙길 위의 진동",
        description_en="Vibration on dirt road",
    ),
    HapticSource(
        id="grass",
        name_ko="잔디", name_en="Grass",
        bus=HapticBus.SURFACE, category=HapticCategory.SURFACE_TYPE,
        settings=("haptic_grass_gain",),
        description_ko="잔디 위 주행 감각",
        description_en="Driving feel on grass",
    ),
    HapticSource(
        id="puddle",
        name_ko="물웅덩이", name_en="Puddle",
        bus=HapticBus.SURFACE, category=HapticCategory.WEATHER,
        settings=("haptic_puddle_gain",),
        description_ko="물웅덩이 통과 저항감",
        description_en="Splash resistance in puddles",
    ),
    HapticSource(
        id="wet_surface",
        name_ko="젖은 노면", name_en="Wet Surface",
        bus=HapticBus.SURFACE, category=HapticCategory.WEATHER,
        settings=("haptic_weather_gain",),
        description_ko="젖은 노면의 미끄러운 감각",
        description_en="Slippery feel on wet roads",
    ),
    HapticSource(
        id="snow",
        name_ko="눈", name_en="Snow",
        bus=HapticBus.SURFACE, category=HapticCategory.WEATHER,
        settings=("haptic_snow_gain",),
        description_ko="눈길 위의 뭉근한 진동",
        description_en="Soft vibration on snow",
    ),
    HapticSource(
        id="ice",
        name_ko="빙판", name_en="Ice",
        bus=HapticBus.SURFACE, category=HapticCategory.WEATHER,
        settings=("haptic_ice_gain",),
        description_ko="빙판 위의 미끄러운 감각",
        description_en="Slippery feel on ice",
    ),
)

# ── Vehicle Bus ──
register(
    HapticSource(
        id="weight_transfer",
        name_ko="하중 이동", name_en="Weight Transfer",
        bus=HapticBus.VEHICLE, category=HapticCategory.BODY_MOTION,
        settings=("haptic_weight_shift_gain",),
        description_ko="가감속/코너링 시 하중 이동",
        description_en="Weight shift during acceleration/braking/cornering",
    ),
    HapticSource(
        id="slide",
        name_ko="슬라이드", name_en="Slide",
        bus=HapticBus.VEHICLE, category=HapticCategory.BODY_MOTION,
        settings=("haptic_slide_gain",),
        description_ko="차체가 미끄러질 때의 진동",
        description_en="Vibration when car is sliding",
    ),
    HapticSource(
        id="drift",
        name_ko="드리프트", name_en="Drift",
        bus=HapticBus.VEHICLE, category=HapticCategory.BODY_MOTION,
        settings=("haptic_drift_gain",),
        description_ko="드리프트 중의 동적 진동",
        description_en="Dynamic vibration during drifting",
    ),
    HapticSource(
        id="rear_breakaway",
        name_ko="후방 이탈", name_en="Rear Breakaway",
        bus=HapticBus.VEHICLE, category=HapticCategory.BODY_MOTION,
        settings=("haptic_slide_gain",),
        description_ko="후륜이 그립을 잃을 때",
        description_en="Rear wheels losing grip",
    ),
)

# ── Engine Bus ──
register(
    HapticSource(
        id="rpm_body",
        name_ko="RPM 차체 진동", name_en="RPM Body Vibration",
        bus=HapticBus.ENGINE, category=HapticCategory.ENGINE_VIBRATION,
        settings=("haptic_engine_rpm_gain", "haptic_engine_body_gain"),
        description_ko="엔진 RPM에 따른 차체 진동",
        description_en="Body vibration from engine RPM",
    ),
    HapticSource(
        id="idle_engine",
        name_ko="공회전 진동", name_en="Idle Vibration",
        bus=HapticBus.ENGINE, category=HapticCategory.ENGINE_VIBRATION,
        settings=("haptic_engine_idle_gain",),
        description_ko="정차 시 엔진 공회전 진동",
        description_en="Engine vibration when idling",
    ),
    HapticSource(
        id="rpm_texture",
        name_ko="RPM 텍스처", name_en="RPM Texture",
        bus=HapticBus.ENGINE, category=HapticCategory.ENGINE_VIBRATION,
        settings=("haptic_engine_rpm_gain",),
        description_ko="고 RPM 영역의 진동 텍스처",
        description_en="Vibration texture at high RPM",
    ),
    HapticSource(
        id="boost_build",
        name_ko="부스트", name_en="Boost Build-up",
        bus=HapticBus.ENGINE, category=HapticCategory.DRIVETRAIN,
        settings=("haptic_turbo_gain",),
        description_ko="터보/슈퍼차저 부스트 상승",
        description_en="Turbo/supercharger boost building up",
    ),
    HapticSource(
        id="launch_load",
        name_ko="런치 부하", name_en="Launch Load",
        bus=HapticBus.ENGINE, category=HapticCategory.DRIVETRAIN,
        settings=("haptic_launch_gain",),
        description_ko="출발 시 구동계 부하",
        description_en="Drivetrain load during launch",
    ),
    HapticSource(
        id="torque_surge",
        name_ko="토크 서지", name_en="Torque Surge",
        bus=HapticBus.ENGINE, category=HapticCategory.DRIVETRAIN,
        settings=("haptic_torque_gain",),
        description_ko="급격한 토크 변화",
        description_en="Sudden torque changes",
    ),
)

# ── Tire Feedback ──
register(
    HapticSource(
        id="wheelspin",
        name_ko="휠스핀", name_en="Wheelspin",
        bus=HapticBus.VEHICLE, category=HapticCategory.TIRE_FEEDBACK,
        settings=("haptic_wheelspin_gain",),
        description_ko="타이어 공회전 진동",
        description_en="Tire spinning vibration",
    ),
    HapticSource(
        id="tire_scrub",
        name_ko="타이어 스크럽", name_en="Tire Scrub",
        bus=HapticBus.VEHICLE, category=HapticCategory.TIRE_FEEDBACK,
        settings=("haptic_tire_scrub_gain",),
        description_ko="타이어 횡방향 마찰",
        description_en="Tire scrubbing on surface",
    ),
    HapticSource(
        id="asphalt_grip",
        name_ko="아스팔트 그립", name_en="Asphalt Grip",
        bus=HapticBus.VEHICLE, category=HapticCategory.TIRE_FEEDBACK,
        settings=("haptic_grip_gain",),
        description_ko="아스팔트에서의 그립 감각",
        description_en="Grip feel on asphalt",
    ),
)

# ── Event Bus ──
register(
    HapticSource(
        id="collision",
        name_ko="충돌", name_en="Collision",
        bus=HapticBus.EVENT, category=HapticCategory.IMPACT,
        settings=("haptic_collision_gain",),
        description_ko="물체와의 충돌 충격",
        description_en="Impact from collisions",
    ),
    HapticSource(
        id="bump",
        name_ko="범프/착지", name_en="Bump",
        bus=HapticBus.EVENT, category=HapticCategory.IMPACT,
        settings=("haptic_bump_gain",),
        description_ko="큰 범프 및 착지 충격",
        description_en="Large bumps and landing impacts",
    ),
    HapticSource(
        id="shift_click",
        name_ko="기어 변속", name_en="Gear Shift",
        bus=HapticBus.EVENT, category=HapticCategory.IMPACT,
        settings=("haptic_shift_gain",),
        description_ko="변속 시 클릭 느낌",
        description_en="Click feel when shifting gears",
    ),
    HapticSource(
        id="landing",
        name_ko="착지 충격", name_en="Landing Impact",
        bus=HapticBus.EVENT, category=HapticCategory.IMPACT,
        settings=("haptic_bump_gain",),
        description_ko="점프 후 착지 충격",
        description_en="Impact when landing from jumps",
    ),
    HapticSource(
        id="scrape",
        name_ko="긁힘", name_en="Scrape",
        bus=HapticBus.EVENT, category=HapticCategory.IMPACT,
        settings=("haptic_scrape_gain",),
        description_ko="벽면 긁힘 마찰",
        description_en="Scraping against walls",
    ),
)
