from __future__ import annotations
from datetime import datetime, timedelta, timezone
from analysis.gpx_utils import bin_track, hysteresis_smooth, median_filter_smooth
from analysis.heat_model import HEAT_PENALTY_PCT_PER_C, HEAT_THRESHOLD_FEELS_LIKE_C, course_temp_c, heat_penalty_factor
SLOPE_BUCKET_WIDTH = 3.0
ELE_HYSTERESIS_THRESHOLD_M = 0.0
MAX_REASONABLE_PACE_MIN_KM = 25.0
RECENCY_HALF_LIFE_DAYS = 180.0

class PaceModelBuildError(Exception):
    pass

def _recency_weight(race_date: datetime, ref_date: datetime) -> float:
    days = (ref_date - race_date).days
    return 0.5 ** (days / RECENCY_HALF_LIFE_DAYS)

def _heat_normalize_bins(bins: list[dict], start_time: datetime, start_ele_m: float, hourly_weather: dict | None, avg_temp_c: float | None, avg_humidity_pct: float | None) -> tuple[float | None, float | None]:
    start_utc = start_time.astimezone(timezone.utc)
    t_acc = h_acc = d_t = d_h = 0.0
    for b in bins:
        pace = b.get('pace_min_km')
        if pace is None or pace > MAX_REASONABLE_PACE_MIN_KM or b.get('elapsed_h_start') is None:
            continue
        temp = hum = None
        if hourly_weather:
            key = (start_utc + timedelta(hours=b['elapsed_h_start'])).strftime('%Y-%m-%dT%H:00')
            if key in hourly_weather:
                grid_temp, hum = hourly_weather[key]
                temp = course_temp_c(grid_temp, b['ele_avg'], start_ele_m)
        elif avg_temp_c is not None:
            temp, hum = (avg_temp_c, avg_humidity_pct)
        if temp is None:
            continue
        b['pace_min_km'] = pace / heat_penalty_factor(temp, hum)
        t_acc += temp * b['dist_m']
        d_t += b['dist_m']
        if hum is not None:
            h_acc += hum * b['dist_m']
            d_h += b['dist_m']
    return (t_acc / d_t if d_t else None, h_acc / d_h if d_h else None)

def build_pace_model(races: list[dict]) -> dict:
    if not races:
        raise PaceModelBuildError('少なくとも1レース分のGPXが必要です')
    summaries = []
    for r in races:
        course = r['course']
        points = course.points
        start, end = (points[0], points[-1])
        if start.time is None or end.time is None:
            raise PaceModelBuildError(f"{r['name']}: GPXにタイムスタンプがありません(実際に走った記録のGPXが必要です。コース下見用など、時刻情報のないGPXは使えません)")
        bins = bin_track(course)
        avg_temp_c, avg_humidity_pct = _heat_normalize_bins(bins, start.time, start.elevation, r.get('hourly_weather'), r.get('avg_temp_c'), r.get('avg_humidity_pct'))
        ele_mf = median_filter_smooth([p.elevation for p in points], window_size=5)
        ele_smoothed = hysteresis_smooth(ele_mf, ELE_HYSTERESIS_THRESHOLD_M)
        gain_m = sum((max(0.0, ele_smoothed[i] - ele_smoothed[i - 1]) for i in range(1, len(ele_smoothed))))
        summaries.append({'name': r['name'], 'start_time_utc': start.time, 'end_time_utc': end.time, 'distance_km': round(course.cum_dist_m[-1] / 1000.0, 2), 'elevation_gain_m': round(gain_m), 'avg_temp_c': round(avg_temp_c, 1) if avg_temp_c is not None else None, 'avg_humidity_pct': round(avg_humidity_pct, 1) if avg_humidity_pct is not None else None, 'bins': bins})
    ref_date = max((r['start_time_utc'] for r in summaries))
    for r in summaries:
        r['recency_weight'] = round(_recency_weight(r['start_time_utc'], ref_date), 4)
    bucket_sums: dict[float, list[float]] = {}
    for r in summaries:
        w_race = r['recency_weight']
        for b in r['bins']:
            pace = b.get('pace_min_km')
            if pace is None or pace > MAX_REASONABLE_PACE_MIN_KM:
                continue
            bucket = round(b['slope_pct'] / SLOPE_BUCKET_WIDTH) * SLOPE_BUCKET_WIDTH
            weight = w_race * b['dist_m']
            acc = bucket_sums.setdefault(bucket, [0.0, 0.0, 0])
            acc[0] += pace * weight
            acc[1] += weight
            acc[2] += 1
    model: dict[float, dict] = {}
    for bucket, (wsum, wtotal, n) in bucket_sums.items():
        if wtotal > 0:
            model[bucket] = {'pace_min_km': round(wsum / wtotal, 2), 'sample_bins': n}
    if not model:
        raise PaceModelBuildError('有効なペースデータが見つかりませんでした(GPXのタイムスタンプ/標高を確認してください)')
    fatigue_points = []
    for r in summaries:
        w_race = r['recency_weight']
        for b in r['bins']:
            pace = b.get('pace_min_km')
            if pace is None or pace > MAX_REASONABLE_PACE_MIN_KM or b.get('elapsed_h_start') is None:
                continue
            bucket = round(b['slope_pct'] / SLOPE_BUCKET_WIDTH) * SLOPE_BUCKET_WIDTH
            expected = model.get(bucket, {}).get('pace_min_km')
            if not expected:
                continue
            ratio = pace / expected
            if ratio < 0.4 or ratio > 3.0:
                continue
            cum_km_start = b['cum_dist_start_m'] / 1000.0
            fatigue_points.append((cum_km_start, ratio, w_race * b['dist_m']))
    Sw = sum((w for _, _, w in fatigue_points))
    Sx = sum((w * x for x, _, w in fatigue_points))
    Sy = sum((w * y for _, y, w in fatigue_points))
    Sxx = sum((w * x * x for x, _, w in fatigue_points))
    Sxy = sum((w * x * y for x, y, w in fatigue_points))
    denom = Sw * Sxx - Sx * Sx
    fatigue_slope_per_km = (Sw * Sxy - Sx * Sy) / denom if denom else 0.0
    fatigue_intercept = (Sy - fatigue_slope_per_km * Sx) / Sw if Sw else 1.0
    max_observed_km = max((x for x, _, _ in fatigue_points), default=0.0)
    return {'generated_at': datetime.now(timezone.utc).isoformat(), 'recency_half_life_days': RECENCY_HALF_LIFE_DAYS, 'slope_bucket_width_pct': SLOPE_BUCKET_WIDTH, 'races': [{k: v.isoformat() if isinstance(v, datetime) else v for k, v in r.items() if k != 'bins'} for r in summaries], 'slope_pace_model': {str(b): v for b, v in sorted(model.items())}, 'heat_model': {'normalized': True, 'threshold_feels_like_c': HEAT_THRESHOLD_FEELS_LIKE_C, 'pct_per_c': HEAT_PENALTY_PCT_PER_C, 'temp_basis': 'on-course, lapse-corrected from start elevation'}, 'fatigue_model': {'intercept': round(fatigue_intercept, 4), 'slope_per_km': round(fatigue_slope_per_km, 6), 'max_observed_km': round(max_observed_km, 1), 'n_bins': len(fatigue_points), 'note': 'pace_ratio = intercept + slope_per_km * cumulative_km_into_race; apply as a multiplier on the slope-only baseline pace'}}
