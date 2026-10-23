from __future__ import annotations
import math
from datetime import datetime, timedelta
from analysis.cutoff import apply_cutoffs
from analysis.gpx_utils import GpxCourse, bin_track, hysteresis_smooth, median_filter_smooth
from analysis.heat_model import course_temp_c, feels_like_c, heat_penalty_factor
from analysis.pace_model import PaceModel
TEMP_ADJ_FACTOR_CLAMP = (0.7, 1.5)
FATIGUE_FACTOR_CLAMP = (0.5, 2.5)
GRADIENT_BANDS_FINE = [('steep_downhill', -999.0, -15.0), ('moderate_downhill', -15.0, -7.5), ('gentle_downhill', -7.5, -2.5), ('flat', -2.5, 2.5), ('gentle_uphill', 2.5, 7.5), ('moderate_uphill', 7.5, 12.5), ('steep_uphill', 12.5, 20.0), ('very_steep_uphill', 20.0, 999.0)]

def gradient_category_fine(slope_pct: float) -> str:
    for name, lo, hi in GRADIENT_BANDS_FINE:
        if lo <= slope_pct < hi:
            return name
    return GRADIENT_BANDS_FINE[-1][0] if slope_pct >= 0 else GRADIENT_BANDS_FINE[0][0]
CP_AID_KCAL = 180.0
GLYCOGEN_STORE_KCAL_PER_KG = 25.0
GLYCOGEN_COVERAGE_MAX_HOURS = 1.5
GEL_ROUND_TOLERANCE_KCAL = 15.0
WATER_ML_PER_H_MIN = 500.0
WATER_ML_PER_H_MAX = 900.0
WATER_FEELS_LIKE_LO_C = 20.0
WATER_FEELS_LIKE_HI_C = 35.0
SWEAT_LOSS_MARGIN = 1.2
KCAL_EXPENDITURE_PER_KG_PER_KM = 1.0
KCAL_EXPENDITURE_PER_KG_PER_GAIN_M = 0.01
TARGET_CATEGORY_ELASTICITY = {'flat': {'weight': 1.5, 'max_reduction_pct': 25.0}, 'gentle_downhill': {'weight': 1.3, 'max_reduction_pct': 20.0}, 'gentle_uphill': {'weight': 1.0, 'max_reduction_pct': 15.0}, 'moderate_downhill': {'weight': 1.1, 'max_reduction_pct': 18.0}, 'moderate_uphill': {'weight': 0.7, 'max_reduction_pct': 10.0}, 'steep_downhill': {'weight': 0.9, 'max_reduction_pct': 15.0}, 'steep_uphill': {'weight': 0.4, 'max_reduction_pct': 6.0}, 'very_steep_uphill': {'weight': 0.2, 'max_reduction_pct': 3.0}}
assert set(TARGET_CATEGORY_ELASTICITY) == {name for name, _, _ in GRADIENT_BANDS_FINE}

def _water_ml_per_h(feels_like: float) -> float:
    if feels_like <= WATER_FEELS_LIKE_LO_C:
        return WATER_ML_PER_H_MIN
    if feels_like >= WATER_FEELS_LIKE_HI_C:
        return WATER_ML_PER_H_MAX
    frac = (feels_like - WATER_FEELS_LIKE_LO_C) / (WATER_FEELS_LIKE_HI_C - WATER_FEELS_LIKE_LO_C)
    return WATER_ML_PER_H_MIN + frac * (WATER_ML_PER_H_MAX - WATER_ML_PER_H_MIN)

def simulate_race(course: GpxCourse, cps: list[dict], race_start_local: datetime, pace_model: PaceModel, diurnal_temp: dict, diurnal_hum: dict, ele_hysteresis_threshold_m: float=0.0, default_cp_dwell_min: float=5.0, cp_dwell_overrides_min: dict | None=None, bodyweight_kg: float=70.0, kcal_per_kg_per_hr: float=3.5, gel_kcal: float=100.0, cp_aid_kcal: float=CP_AID_KCAL, category_multipliers: dict[str, float] | None=None) -> dict:
    cp_dwell_overrides_min = cp_dwell_overrides_min or {}
    category_time_s: dict[str, float] = {name: 0.0 for name, _, _ in GRADIENT_BANDS_FINE}
    points = course.points
    cum_dist = course.cum_dist_m
    start_ele = points[0].elevation
    total_dist_m = cum_dist[-1]
    ele_mf = median_filter_smooth([p.elevation for p in points], window_size=5)
    ele_hysteresis = hysteresis_smooth(ele_mf, ele_hysteresis_threshold_m)
    hyst_gain_m = sum((max(0.0, ele_hysteresis[i] - ele_hysteresis[i - 1]) for i in range(1, len(points))))
    hyst_loss_m = sum((max(0.0, ele_hysteresis[i - 1] - ele_hysteresis[i]) for i in range(1, len(points))))
    highest_idx = max(range(len(points)), key=lambda i: points[i].elevation)
    highest_point = {'elevation_m': round(points[highest_idx].elevation), 'dist_km': round(cum_dist[highest_idx] / 1000.0, 1)}
    cp_targets_m = sorted(({'name': c['name'], 'dist_m': max(0.0, min(total_dist_m, c['dist_km'] * 1000.0)), 'cutoff': c.get('cutoff')} for c in cps), key=lambda c: c['dist_m'])
    bins = bin_track(course)
    elapsed_s = 0.0
    cp_ptr = 0
    cp_results = []
    total_gain_m = 0.0
    total_loss_m = 0.0
    gain_since_prev_cp = 0.0
    loss_since_prev_cp = 0.0
    prev_cp_dist_m = 0.0
    curve = [[0.0, 0.0]]
    profile_with_time = [[0.0, round(start_ele, 1), 0.0]]

    def _flush_cp(cp, elapsed_s, ele_here, temp_here, hum_here, fatigue_adj_factor, cum_km_start, extrapolated):
        nonlocal gain_since_prev_cp, loss_since_prev_cp, prev_cp_dist_m
        arrival = race_start_local + timedelta(seconds=elapsed_s)
        is_start_finish = 'START' in cp['name'].upper() or 'FINISH' in cp['name'].upper() or 'GOAL' in cp['name'].upper()
        dwell_min = 0.0 if is_start_finish else cp_dwell_overrides_min.get(cp['name'], default_cp_dwell_min)
        departure_elapsed_s = elapsed_s + dwell_min * 60.0
        fl = feels_like_c(temp_here, hum_here) if temp_here is not None else None
        cp_results.append({'name': cp['name'], 'dist_km': round(cp['dist_m'] / 1000.0, 2), 'segment_km': round((cp['dist_m'] - prev_cp_dist_m) / 1000.0, 2), 'gain_m': round(gain_since_prev_cp), 'loss_m': round(loss_since_prev_cp), 'elevation_m': round(ele_here) if ele_here is not None else None, 'arrival_local': arrival.strftime('%Y-%m-%d %H:%M'), 'arrival_clock': arrival.strftime('%H:%M'), 'elapsed_s': round(elapsed_s, 1), 'elapsed_h': round(elapsed_s / 3600.0, 2), 'dwell_min': dwell_min, 'temp_c': round(temp_here, 1) if temp_here is not None else None, 'feels_like_c': round(fl, 1) if fl is not None else None, 'humidity_pct': round(hum_here) if hum_here is not None else None, 'fatigue_factor': round(fatigue_adj_factor, 3) if fatigue_adj_factor is not None else None, 'extrapolated': extrapolated, 'cutoff': cp.get('cutoff') or None})
        gain_since_prev_cp = 0.0
        loss_since_prev_cp = 0.0
        prev_cp_dist_m = cp['dist_m']
        return departure_elapsed_s
    for b in bins:
        base_pace_min_km = pace_model.lookup_pace(b['slope_pct'])
        current_time = race_start_local + timedelta(seconds=elapsed_s)
        hour = current_time.hour
        temp_at_start_ele = diurnal_temp[hour]
        temp_here = course_temp_c(temp_at_start_ele, b['ele_avg'], start_ele)
        hum_here = diurnal_hum.get(hour)
        temp_adj_factor = heat_penalty_factor(temp_here, hum_here) / pace_model.reference_heat_factor
        temp_adj_factor = max(TEMP_ADJ_FACTOR_CLAMP[0], min(TEMP_ADJ_FACTOR_CLAMP[1], temp_adj_factor))
        cum_km_start = b['cum_dist_start_m'] / 1000.0
        fatigue_adj_factor = pace_model.fatigue_factor(cum_km_start, FATIGUE_FACTOR_CLAMP)
        category = gradient_category_fine(b['slope_pct'])
        category_adj_factor = category_multipliers.get(category, 1.0) if category_multipliers else 1.0
        pace_min_km = base_pace_min_km * temp_adj_factor * fatigue_adj_factor * category_adj_factor
        seg_time_s = pace_min_km * 60.0 * (b['dist_m'] / 1000.0)
        elapsed_s += seg_time_s
        category_time_s[category] += seg_time_s
        if b['slope_pct'] > 0:
            seg_gain = b['slope_pct'] / 100.0 * b['dist_m']
            total_gain_m += seg_gain
            gain_since_prev_cp += seg_gain
        else:
            seg_loss = -(b['slope_pct'] / 100.0) * b['dist_m']
            total_loss_m += seg_loss
            loss_since_prev_cp += seg_loss
        curve.append([round(b['cum_dist_end_m'] / 1000.0, 3), round(elapsed_s, 1)])
        profile_with_time.append([round(b['cum_dist_end_m'] / 1000.0, 3), round(b['ele_avg'], 1), round(elapsed_s, 1)])
        while cp_ptr < len(cp_targets_m) and cp_targets_m[cp_ptr]['dist_m'] <= b['cum_dist_end_m']:
            elapsed_s = _flush_cp(cp_targets_m[cp_ptr], elapsed_s, b['ele_avg'], temp_here, hum_here, fatigue_adj_factor, cum_km_start, cum_km_start > pace_model.fatigue_max_observed_km)
            cp_ptr += 1
    last_temp = cp_results[-1]['temp_c'] if cp_results else None
    last_hum = cp_results[-1]['humidity_pct'] if cp_results else None
    last_fatigue = cp_results[-1]['fatigue_factor'] if cp_results else None
    while cp_ptr < len(cp_targets_m):
        elapsed_s = _flush_cp(cp_targets_m[cp_ptr], elapsed_s, points[-1].elevation, last_temp, last_hum, last_fatigue, total_dist_m / 1000.0, False)
        cp_ptr += 1
    if curve[-1][0] * 1000.0 < total_dist_m:
        curve.append([round(total_dist_m / 1000.0, 3), round(elapsed_s, 1)])
        profile_with_time.append([round(total_dist_m / 1000.0, 3), round(points[-1].elevation, 1), round(elapsed_s, 1)])
    finish_time = race_start_local + timedelta(seconds=elapsed_s)
    total_dwell_min = sum((r['dwell_min'] for r in cp_results))
    cutoff_summary = apply_cutoffs(cp_results, race_start_local)
    nutrition = []
    prev_elapsed_h = 0.0
    prev_name = cp_results[0]['name'] if cp_results else 'START'
    for i, r in enumerate(cp_results[1:] if cp_results else [], start=1):
        seg_h = r['elapsed_h'] - prev_elapsed_h
        if seg_h > 0:
            prev_cp = cp_results[i - 1]
            avg_feels_like = (prev_cp['feels_like_c'] + r['feels_like_c']) / 2 if prev_cp['feels_like_c'] is not None and r['feels_like_c'] is not None else r['feels_like_c'] or 0.0
            kcal_target = kcal_per_kg_per_hr * bodyweight_kg * seg_h
            water_ml_per_h = _water_ml_per_h(avg_feels_like)
            water_ml = water_ml_per_h * seg_h
            is_first_segment = i == 1
            if is_first_segment:
                cp_aid = 0.0
                glycogen_store_kcal = GLYCOGEN_STORE_KCAL_PER_KG * bodyweight_kg
                glycogen_covered_kcal = min(glycogen_store_kcal, kcal_per_kg_per_hr * bodyweight_kg * min(seg_h, GLYCOGEN_COVERAGE_MAX_HOURS))
                net_kcal = kcal_target - glycogen_covered_kcal
                if net_kcal <= GEL_ROUND_TOLERANCE_KCAL:
                    gels = 0
                    note = 'スタート前の朝食で体内グリコーゲン充填済みのため補給食なしでも可(体内貯蔵分で足りる)'
                    note_code = 'glycogen_covers'
                else:
                    gels = math.ceil(net_kcal / gel_kcal)
                    note = '体内グリコーゲン貯蔵を使い切った後は、CPがないため携行ジェル等で補給してください'
                    note_code = 'glycogen_then_gels'
            else:
                cp_aid = cp_aid_kcal
                net_kcal = kcal_target - cp_aid
                if net_kcal <= GEL_ROUND_TOLERANCE_KCAL:
                    gels = 0
                    note = f'{prev_name}のバナナ2本で充足' if net_kcal < 0 else '—'
                    note_code = 'cp_bananas_cover' if net_kcal < 0 else None
                else:
                    gels = math.ceil(net_kcal / gel_kcal)
                    note = '—'
                    note_code = None
            nutrition.append({'from': prev_name, 'to': r['name'], 'seg_h': round(seg_h, 2), 'avg_feels_like_c': round(avg_feels_like, 1), 'kcal_target': round(kcal_target), 'cp_aid_kcal': round(cp_aid), 'net_kcal': round(net_kcal), 'gels': gels, 'water_ml': round(water_ml), 'water_ml_per_h': round(water_ml_per_h), 'note': note, 'note_code': note_code})
        prev_elapsed_h = r['elapsed_h']
        prev_name = r['name']
    total_water_l = sum((n['water_ml'] for n in nutrition)) / 1000.0
    total_gels = sum((n['gels'] for n in nutrition))
    total_gel_kcal = total_gels * gel_kcal
    n_aid_stops = max(0, len(cp_results) - 2)
    total_cp_aid_kcal = n_aid_stops * cp_aid_kcal
    total_distance_km = total_dist_m / 1000.0
    estimated_kcal_expenditure = bodyweight_kg * (total_distance_km * KCAL_EXPENDITURE_PER_KG_PER_KM + hyst_gain_m * KCAL_EXPENDITURE_PER_KG_PER_GAIN_M)
    nutrition_summary = {'total_water_l': round(total_water_l, 1), 'total_gels': total_gels, 'total_gel_kcal': round(total_gel_kcal), 'n_aid_stops': n_aid_stops, 'total_cp_aid_kcal': round(total_cp_aid_kcal), 'total_intake_kcal': round(total_gel_kcal + total_cp_aid_kcal), 'estimated_sweat_l': round(total_water_l * SWEAT_LOSS_MARGIN, 1), 'estimated_kcal_expenditure': round(estimated_kcal_expenditure), 'bodyweight_kg': bodyweight_kg}
    baseline_elapsed_s = 0.0
    for b in bins:
        base_pace_min_km = pace_model.lookup_pace(b['slope_pct'])
        fatigue_adj_factor = pace_model.fatigue_factor(b['cum_dist_start_m'] / 1000.0, FATIGUE_FACTOR_CLAMP)
        baseline_elapsed_s += base_pace_min_km * fatigue_adj_factor * 60.0 * (b['dist_m'] / 1000.0)
    baseline_elapsed_s += total_dwell_min * 60.0
    temp_correction_pct = (elapsed_s - baseline_elapsed_s) / baseline_elapsed_s * 100.0 if baseline_elapsed_s else 0.0
    real_cps = [r for r in cp_results if r['dist_km'] not in (0.0,) and r['name'].upper() not in ('START',)]
    segments = []
    for i in range(1, len(cp_results)):
        a, c = (cp_results[i - 1], cp_results[i])
        seg_time_s = c['elapsed_s'] - (a['elapsed_s'] + a['dwell_min'] * 60.0)
        segments.append({'from': a['name'], 'to': c['name'], 'km': c['segment_km'], 'gain_m': c['gain_m'], 'time_s': seg_time_s, 'feels_like_c': c['feels_like_c'], 'elapsed_h_at_end': c['elapsed_h']})
    longest_seg = max(segments, key=lambda s: s['time_s']) if segments else None
    hottest_seg = max(segments, key=lambda s: s['feels_like_c'] if s['feels_like_c'] is not None else -999) if segments else None
    steepest_seg = max(segments, key=lambda s: s['gain_m'] / s['km'] if s['km'] > 0 else 0) if segments else None
    cp1 = cp_results[1] if len(cp_results) > 1 else None
    return {'race_start_local': race_start_local.isoformat(), 'reference_temp_c': round(pace_model.reference_temp_c, 2), 'heat_normalized': pace_model.heat_normalized, 'total_distance_km': round(total_distance_km, 2), 'total_gain_m': round(hyst_gain_m), 'total_loss_m': round(hyst_loss_m), 'total_gain_raw_m': round(total_gain_m), 'total_loss_raw_m': round(total_loss_m), 'highest_point': highest_point, 'predicted_finish_local': finish_time.strftime('%Y-%m-%d %H:%M'), 'predicted_finish_clock': finish_time.strftime('%H:%M'), 'predicted_elapsed_hours': round(elapsed_s / 3600.0, 2), 'predicted_elapsed_s': round(elapsed_s, 1), 'baseline_elapsed_s': round(baseline_elapsed_s, 1), 'category_time_s': {k: round(v, 1) for k, v in category_time_s.items()}, 'temp_correction_pct': round(temp_correction_pct, 1), 'total_dwell_min': round(total_dwell_min), 'fatigue_max_observed_km': pace_model.fatigue_max_observed_km, 'cp_schedule': cp_results, 'cutoff_summary': cutoff_summary, 'nutrition_plan': nutrition, 'nutrition_summary': nutrition_summary, 'predicted_curve': curve, 'elevation_profile_timed': profile_with_time, 'bodyweight_kg': bodyweight_kg, 'mindset': {'longest_segment': longest_seg, 'hottest_segment': hottest_seg, 'steepest_segment': steepest_seg, 'cp1': cp1, 'max_feels_like_c': max((c['feels_like_c'] for c in cp_results if c['feels_like_c'] is not None), default=None)}}

def _distribute_target_reduction(category_time_s: dict[str, float], delta_t_s: float) -> dict[str, float]:
    r = {cat: 0.0 for cat in TARGET_CATEGORY_ELASTICITY}
    capped: set[str] = set()
    remaining = delta_t_s
    for _ in range(len(TARGET_CATEGORY_ELASTICITY) + 1):
        active = [c for c in TARGET_CATEGORY_ELASTICITY if c not in capped and category_time_s.get(c, 0.0) > 0]
        if not active or remaining <= 0:
            break
        denom = sum((TARGET_CATEGORY_ELASTICITY[c]['weight'] * category_time_s[c] for c in active))
        if denom <= 0:
            break
        k = remaining / denom
        newly_capped = []
        for c in active:
            cap_frac = TARGET_CATEGORY_ELASTICITY[c]['max_reduction_pct'] / 100.0
            candidate = k * TARGET_CATEGORY_ELASTICITY[c]['weight']
            if candidate >= cap_frac:
                r[c] = cap_frac
                newly_capped.append(c)
            else:
                r[c] = candidate
        allocated = sum((r[c] * category_time_s[c] for c in TARGET_CATEGORY_ELASTICITY))
        remaining = delta_t_s - allocated
        if not newly_capped:
            break
        capped.update(newly_capped)
    return r

def compute_target_plan(course: GpxCourse, cps: list[dict], race_start_local: datetime, pace_model: PaceModel, diurnal_temp: dict, diurnal_hum: dict, baseline_result: dict, target_elapsed_s: float, **simulate_kwargs) -> dict:
    baseline_elapsed_s = baseline_result['predicted_elapsed_s']
    delta_t = baseline_elapsed_s - target_elapsed_s
    if delta_t <= 0:
        return {'adjustment_needed': False, 'feasible': True, 'target_elapsed_s': target_elapsed_s, 'achieved_elapsed_s': baseline_elapsed_s, 'category_breakdown': [], 'plan': None}
    category_time_s = baseline_result['category_time_s']
    r = _distribute_target_reduction(category_time_s, delta_t)
    achieved_delta = sum((r[c] * category_time_s.get(c, 0.0) for c in TARGET_CATEGORY_ELASTICITY))
    achieved_elapsed_s = baseline_elapsed_s - achieved_delta
    feasible = achieved_elapsed_s <= target_elapsed_s + 1.0
    category_multipliers = {c: 1.0 - r[c] for c in TARGET_CATEGORY_ELASTICITY}
    adjusted = simulate_race(course=course, cps=cps, race_start_local=race_start_local, pace_model=pace_model, diurnal_temp=diurnal_temp, diurnal_hum=diurnal_hum, category_multipliers=category_multipliers, **simulate_kwargs)
    category_breakdown = [{'category': name, 'time_s': round(category_time_s.get(name, 0.0), 1), 'reduction_pct': round(r[name] * 100.0, 1), 'capped': r[name] * 100.0 >= TARGET_CATEGORY_ELASTICITY[name]['max_reduction_pct'] - 1e-06} for name, _, _ in GRADIENT_BANDS_FINE if category_time_s.get(name, 0.0) > 0]
    return {'adjustment_needed': True, 'feasible': feasible, 'target_elapsed_s': target_elapsed_s, 'achieved_elapsed_s': round(achieved_elapsed_s, 1), 'category_breakdown': category_breakdown, 'plan': adjusted}
