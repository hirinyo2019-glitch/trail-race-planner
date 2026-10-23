from __future__ import annotations
import bisect
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from analysis.gpx_utils import GpxCourse, find_nearest_point_sequential
MAX_CP_MATCH_OFFSET_M = 150.0

class RaceReviewError(Exception):
    pass

@dataclass
class CpTarget:
    name: str
    dist_km: float
    lat: float
    lon: float

@dataclass
class PredictionSnapshot:
    race_id: str
    race_name: str
    course_filename: str
    saved_at_utc: str
    race_start_local: str
    predicted_finish_local: str
    predicted_elapsed_s: float
    total_distance_km: float
    total_gain_m: float
    total_loss_m: float
    cp_schedule: list[dict]
    cp_targets: list[CpTarget] = field(default_factory=list)
    was_custom_pace_model: bool = False
    pace_model_reference_temp_c: float | None = None
    weather_source: str = ''

@dataclass
class ActualCpResult:
    name: str
    predicted_dist_km: float
    matched: bool
    actual_elapsed_s: float | None
    match_offset_m: float | None
    predicted_elapsed_s: float | None
    diff_s: float | None
    actual_point_idx: int | None = None

@dataclass
class ActualSegmentResult:
    from_name: str
    to_name: str
    matched: bool
    predicted_segment_s: float | None
    actual_segment_s: float | None
    diff_s: float | None
    predicted_pace_min_km: float | None
    actual_pace_min_km: float | None

@dataclass
class ActualRaceData:
    filename: str
    uploaded_at_utc: str
    actual_total_distance_km: float
    actual_total_elapsed_s: float | None
    actual_total_gain_m: float
    actual_total_loss_m: float
    cp_results: list[ActualCpResult]
    segment_results: list[ActualSegmentResult]

@dataclass
class RaceHistoryEntry:
    race_id: str
    prediction_snapshot: PredictionSnapshot
    actual_summary: ActualRaceData | None = None
    cp_results: list[ActualCpResult] = field(default_factory=list)
    segment_results: list[ActualSegmentResult] = field(default_factory=list)
    goal_prediction_snapshot: PredictionSnapshot | None = None
    goal_cp_results: list[ActualCpResult] = field(default_factory=list)
    goal_segment_results: list[ActualSegmentResult] = field(default_factory=list)

def _resolve_cp_targets(course: GpxCourse, cp_schedule: list[dict]) -> list[CpTarget]:
    cum_dist = course.cum_dist_m
    targets = []
    for cp in cp_schedule:
        target_m = cp['dist_km'] * 1000.0
        idx = bisect.bisect_left(cum_dist, target_m)
        idx = min(idx, len(cum_dist) - 1)
        if idx > 0 and abs(cum_dist[idx - 1] - target_m) < abs(cum_dist[idx] - target_m):
            idx -= 1
        pt = course.points[idx]
        targets.append(CpTarget(name=cp['name'], dist_km=cp['dist_km'], lat=pt.latitude, lon=pt.longitude))
    return targets

def build_prediction_snapshot(course: GpxCourse, plan_result: dict, race_name: str, course_filename: str) -> PredictionSnapshot:
    cp_schedule = plan_result['cp_schedule']
    if not cp_schedule:
        raise RaceReviewError('予測結果にCPが含まれていません')
    return PredictionSnapshot(race_id=uuid.uuid4().hex, race_name=race_name or course_filename, course_filename=course_filename, saved_at_utc=datetime.now(timezone.utc).isoformat(), race_start_local=plan_result['race_start_local'], predicted_finish_local=plan_result['predicted_finish_local'], predicted_elapsed_s=plan_result['predicted_elapsed_s'], total_distance_km=plan_result['total_distance_km'], total_gain_m=plan_result['total_gain_m'], total_loss_m=plan_result['total_loss_m'], cp_schedule=cp_schedule, cp_targets=_resolve_cp_targets(course, cp_schedule), was_custom_pace_model=bool(plan_result.get('was_custom_pace_model', False)), pace_model_reference_temp_c=plan_result.get('reference_temp_c'), weather_source=plan_result.get('weather_source', ''))

def match_actual_cps(snapshot: PredictionSnapshot, actual_course: GpxCourse) -> list[ActualCpResult]:
    if actual_course.points[0].time is None:
        raise RaceReviewError('このGPXにはタイムスタンプがありません。実際に走った記録のGPX(ウォッチのエクスポート等)をアップロードしてください')
    targets = [(t.name, t.lat, t.lon) for t in snapshot.cp_targets]
    matches = find_nearest_point_sequential(actual_course, targets, MAX_CP_MATCH_OFFSET_M)
    predicted_by_name = {cp['name']: cp for cp in snapshot.cp_schedule}
    actual_start_time = actual_course.points[0].time
    if targets and matches[0]['matched']:
        start_pt_time = actual_course.points[matches[0]['point_idx']].time
        if start_pt_time is not None:
            actual_start_time = start_pt_time
    results = []
    for cp_target, match in zip(snapshot.cp_targets, matches):
        predicted_cp = predicted_by_name.get(cp_target.name)
        predicted_elapsed_s = predicted_cp['elapsed_s'] if predicted_cp else None
        if match['matched']:
            pt = actual_course.points[match['point_idx']]
            if pt.time is None:
                actual_elapsed_s = None
            else:
                actual_elapsed_s = (pt.time - actual_start_time).total_seconds()
        else:
            actual_elapsed_s = None
        diff_s = None
        if actual_elapsed_s is not None and predicted_elapsed_s is not None:
            diff_s = actual_elapsed_s - predicted_elapsed_s
        results.append(ActualCpResult(name=cp_target.name, predicted_dist_km=cp_target.dist_km, matched=match['matched'] and actual_elapsed_s is not None, actual_elapsed_s=actual_elapsed_s, match_offset_m=match['offset_m'], predicted_elapsed_s=predicted_elapsed_s, diff_s=diff_s, actual_point_idx=match['point_idx']))
    return results

def build_segment_results(snapshot: PredictionSnapshot, cp_results: list[ActualCpResult], actual_course: GpxCourse) -> list[ActualSegmentResult]:
    predicted_by_name = {cp['name']: cp for cp in snapshot.cp_schedule}
    segments = []
    for i in range(1, len(cp_results)):
        a, b = (cp_results[i - 1], cp_results[i])
        pred_a, pred_b = (predicted_by_name.get(a.name), predicted_by_name.get(b.name))
        predicted_segment_s = None
        if pred_a is not None and pred_b is not None:
            predicted_segment_s = pred_b['elapsed_s'] - pred_a['elapsed_s']
        matched = a.matched and b.matched
        actual_segment_s = diff_s = actual_pace = predicted_pace = None
        if matched:
            actual_segment_s = b.actual_elapsed_s - a.actual_elapsed_s
            if predicted_segment_s is not None:
                diff_s = actual_segment_s - predicted_segment_s
            seg_dist_km = b.predicted_dist_km - a.predicted_dist_km
            if seg_dist_km > 0 and actual_segment_s and (actual_segment_s > 0):
                actual_pace = actual_segment_s / 60.0 / seg_dist_km
            if seg_dist_km > 0 and predicted_segment_s and (predicted_segment_s > 0):
                predicted_pace = predicted_segment_s / 60.0 / seg_dist_km
        segments.append(ActualSegmentResult(from_name=a.name, to_name=b.name, matched=matched, predicted_segment_s=predicted_segment_s, actual_segment_s=actual_segment_s, diff_s=diff_s, predicted_pace_min_km=round(predicted_pace, 2) if predicted_pace is not None else None, actual_pace_min_km=round(actual_pace, 2) if actual_pace is not None else None))
    return segments

def build_actual_race_data(filename: str, actual_course: GpxCourse, cp_results: list[ActualCpResult], segment_results: list[ActualSegmentResult]) -> ActualRaceData:
    from analysis.gpx_utils import course_summary
    summary = course_summary(actual_course)
    start_cp = cp_results[0] if cp_results else None
    finish_cp = cp_results[-1] if cp_results else None
    actual_total_elapsed_s = None
    if start_cp and finish_cp and start_cp.matched and finish_cp.matched:
        actual_total_elapsed_s = finish_cp.actual_elapsed_s - start_cp.actual_elapsed_s
    return ActualRaceData(filename=filename, uploaded_at_utc=datetime.now(timezone.utc).isoformat(), actual_total_distance_km=summary['total_distance_km'], actual_total_elapsed_s=actual_total_elapsed_s, actual_total_gain_m=summary['total_gain_m'], actual_total_loss_m=summary['total_loss_m'], cp_results=cp_results, segment_results=segment_results)
