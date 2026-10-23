from __future__ import annotations
LAPSE_RATE_C_PER_100M = -0.65
HEAT_THRESHOLD_FEELS_LIKE_C = 22.0
HEAT_PENALTY_PCT_PER_C = 2.0

def feels_like_c(temp_c: float, humidity_pct: float | None) -> float:
    if humidity_pct is None:
        return temp_c
    return temp_c + max(0.0, humidity_pct - 40.0) * 0.06

def course_temp_c(temp_at_start_ele_c: float, ele_m: float, start_ele_m: float) -> float:
    return temp_at_start_ele_c + (ele_m - start_ele_m) / 100.0 * LAPSE_RATE_C_PER_100M

def heat_penalty_factor(temp_c: float, humidity_pct: float | None) -> float:
    excess_c = max(0.0, feels_like_c(temp_c, humidity_pct) - HEAT_THRESHOLD_FEELS_LIKE_C)
    return 1.0 + HEAT_PENALTY_PCT_PER_C / 100.0 * excess_c
