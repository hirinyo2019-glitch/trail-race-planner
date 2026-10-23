from __future__ import annotations
import math
import statistics
from dataclasses import dataclass
import gpxpy
BIN_DISTANCE_M = 100.0
DEFAULT_ELE_HYSTERESIS_THRESHOLD_M = 0.0
MATCH_GIVE_UP_DISTANCE_M = 3000.0

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = (math.radians(lat1), math.radians(lat2))
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

def hysteresis_smooth(values, threshold):
    if not values:
        return []
    ref = values[0]
    out = [ref]
    for v in values[1:]:
        if abs(v - ref) >= threshold:
            ref = v
        out.append(ref)
    return out

def median_filter_smooth(values: list[float], window_size: int=5) -> list[float]:
    if not values:
        return []
    if len(values) < window_size:
        return list(values)
    half_window = window_size // 2
    smoothed = []
    n = len(values)
    for i in range(n):
        start = max(0, i - half_window)
        end = min(n, i + half_window + 1)
        smoothed.append(statistics.median(values[start:end]))
    return smoothed

@dataclass
class GpxCourse:
    points: list
    cum_dist_m: list
    waypoints: list

def _fill_missing_elevations(points) -> None:
    last_known = None
    for p in points:
        if p.elevation is None:
            p.elevation = last_known
        else:
            last_known = p.elevation
    if points[0].elevation is None:
        first_known = next((p.elevation for p in points if p.elevation is not None), 0.0)
        for p in points:
            if p.elevation is None:
                p.elevation = first_known
            else:
                break

def parse_gpx(gpx_bytes: bytes) -> GpxCourse:
    gpx = gpxpy.parse(gpx_bytes.decode('utf-8'))
    points = []
    for track in gpx.tracks:
        for seg in track.segments:
            points.extend(seg.points)
    if not points and gpx.routes:
        for route in gpx.routes:
            points.extend(route.points)
    if len(points) < 2:
        raise ValueError('GPXにトラック(track)データが見つかりません')
    _fill_missing_elevations(points)
    cum_dist = [0.0] * len(points)
    for i in range(1, len(points)):
        cum_dist[i] = cum_dist[i - 1] + haversine_m(points[i - 1].latitude, points[i - 1].longitude, points[i].latitude, points[i].longitude)
    waypoints = [{'name': wp.name or f'WPT{i + 1}', 'lat': wp.latitude, 'lon': wp.longitude} for i, wp in enumerate(gpx.waypoints)]
    return GpxCourse(points=points, cum_dist_m=cum_dist, waypoints=waypoints)

def detect_checkpoints(course: GpxCourse) -> list[dict]:
    cps = []
    search_start_idx = 0
    n = len(course.points)
    for wp in course.waypoints:
        best_idx, best_d = (search_start_idx, float('inf'))
        for i in range(search_start_idx, n):
            d = haversine_m(wp['lat'], wp['lon'], course.points[i].latitude, course.points[i].longitude)
            if d < best_d:
                best_d, best_idx = (d, i)
        cps.append({'name': wp['name'], 'dist_km': round(course.cum_dist_m[best_idx] / 1000.0, 2), 'match_offset_m': round(best_d, 1), 'auto_detected': True})
        search_start_idx = best_idx
    cps.sort(key=lambda c: c['dist_km'])
    total_km = round(course.cum_dist_m[-1] / 1000.0, 2)
    names_upper = [c['name'].upper() for c in cps]
    if not any(('START' in n_ for n_ in names_upper)):
        cps.insert(0, {'name': 'START', 'dist_km': 0.0, 'match_offset_m': 0.0, 'auto_detected': True})
    if not any(('FINISH' in n_ or 'GOAL' in n_ for n_ in names_upper)):
        cps.append({'name': 'FINISH', 'dist_km': total_km, 'match_offset_m': 0.0, 'auto_detected': True})
    return cps

def find_nearest_point_sequential(course: GpxCourse, targets: list[tuple[str, float, float]], max_offset_m: float) -> list[dict]:
    results = []
    search_start_idx = 0
    n = len(course.points)
    cum_dist = course.cum_dist_m
    for name, lat, lon in targets:
        best_idx, best_d = (search_start_idx, float('inf'))
        i = search_start_idx
        while i < n:
            d = haversine_m(lat, lon, course.points[i].latitude, course.points[i].longitude)
            if d < best_d:
                best_d, best_idx = (d, i)
            elif best_d <= max_offset_m and cum_dist[i] - cum_dist[best_idx] > MATCH_GIVE_UP_DISTANCE_M:
                break
            i += 1
        if best_d <= max_offset_m:
            results.append({'name': name, 'matched': True, 'point_idx': best_idx, 'offset_m': round(best_d, 1)})
        else:
            results.append({'name': name, 'matched': False, 'point_idx': None, 'offset_m': None})
        search_start_idx = best_idx
    return results

def course_summary(course: GpxCourse, ele_hysteresis_threshold_m: float=DEFAULT_ELE_HYSTERESIS_THRESHOLD_M) -> dict:
    ele_values = [p.elevation for p in course.points]
    ele_mf = median_filter_smooth(ele_values, window_size=5)
    ele_smoothed = hysteresis_smooth(ele_mf, ele_hysteresis_threshold_m)
    gain_m = sum((max(0.0, ele_smoothed[i] - ele_smoothed[i - 1]) for i in range(1, len(ele_smoothed))))
    loss_m = sum((max(0.0, ele_smoothed[i - 1] - ele_smoothed[i]) for i in range(1, len(ele_smoothed))))
    profile = []
    next_target = 0.0
    for i, d in enumerate(course.cum_dist_m):
        if d >= next_target:
            profile.append([round(d / 1000.0, 3), round(ele_values[i], 1)])
            next_target += 250.0
    profile.append([round(course.cum_dist_m[-1] / 1000.0, 3), round(ele_values[-1], 1)])
    return {'total_distance_km': round(course.cum_dist_m[-1] / 1000.0, 2), 'total_gain_m': round(gain_m), 'total_loss_m': round(loss_m), 'start_lat': course.points[0].latitude, 'start_lon': course.points[0].longitude, 'start_elevation_m': round(course.points[0].elevation, 1), 'elevation_profile': profile}

def bin_track(course: GpxCourse) -> list[dict]:
    bins = []
    acc_dist = 0.0
    seg_start_idx = 0
    points = course.points
    cum_dist = course.cum_dist_m
    race_start_time = points[0].time
    for i in range(1, len(points)):
        d = haversine_m(points[i - 1].latitude, points[i - 1].longitude, points[i].latitude, points[i].longitude)
        acc_dist += d
        if acc_dist >= BIN_DISTANCE_M:
            ele_delta = points[i].elevation - points[seg_start_idx].elevation
            ele_avg = (points[i].elevation + points[seg_start_idx].elevation) / 2
            slope_pct = ele_delta / acc_dist * 100 if acc_dist > 0 else 0.0
            pace_min_km = None
            elapsed_h_start = None
            t_end, t_start = (points[i].time, points[seg_start_idx].time)
            if t_end is not None and t_start is not None:
                time_delta_s = (t_end - t_start).total_seconds()
                if time_delta_s > 0 and acc_dist > 0:
                    pace_min_km = time_delta_s / 60.0 / (acc_dist / 1000.0)
                if race_start_time is not None:
                    elapsed_h_start = (t_start - race_start_time).total_seconds() / 3600.0
            bins.append({'dist_m': acc_dist, 'slope_pct': slope_pct, 'ele_avg': ele_avg, 'cum_dist_start_m': cum_dist[seg_start_idx], 'cum_dist_end_m': cum_dist[i], 'pace_min_km': pace_min_km, 'elapsed_h_start': elapsed_h_start})
            seg_start_idx = i
            acc_dist = 0.0
    return bins
