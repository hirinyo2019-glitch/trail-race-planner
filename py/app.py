from __future__ import annotations
import json
import logging
import os
import threading
import uuid
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from analysis.cutoff import CutoffInputError
from analysis.gpx_utils import DEFAULT_ELE_HYSTERESIS_THRESHOLD_M, course_summary, detect_checkpoints, parse_gpx
from analysis.pace_model import PaceModelUnavailable, load_pace_model
from analysis.pace_model_builder import PaceModelBuildError, build_pace_model
from analysis.pdf_report import build_plan_pdf
from analysis.simulate import CP_AID_KCAL, compute_target_plan, simulate_race
from analysis.race_review import CpTarget, PredictionSnapshot, RaceHistoryEntry, RaceReviewError, build_actual_race_data, build_prediction_snapshot, build_segment_results, match_actual_cps
from analysis.weather import WeatherFetchError, fetch_actual_hourly, fetch_diurnal_curve, window_average
from config.settings import APP_TITLE, DEFAULT_BODYWEIGHT_KG, DEFAULT_CP_DWELL_MIN, DEFAULT_GEL_KCAL, DEFAULT_KCAL_PER_KG_PER_HR, MY_PACE_MODEL_PATH, MY_RACES_DIR, PACE_MODEL_PATH, RACE_HISTORY_PATH, UPLOAD_DIR, WEB_DIR
from version import BUILD_DATE, __version__
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('race_predictor')
app = FastAPI(title=APP_TITLE)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_COURSES: dict[str, dict] = {}
_LOCK = threading.Lock()
MY_RACES_INDEX_PATH = MY_RACES_DIR / 'races.json'

def _active_pace_model_path() -> Path:
    return MY_PACE_MODEL_PATH if MY_PACE_MODEL_PATH.exists() else PACE_MODEL_PATH

@app.get('/api/version')
def api_version():
    return {'app': 'race-predictor-web', 'version': __version__, 'build_date': BUILD_DATE}

@app.post('/shutdown')
def shutdown():
    logger.info('shutdown requested from web UI')

    def _terminate() -> None:
        import time
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=_terminate, daemon=True).start()
    return {'status': 'shutting down'}

def _load_my_races() -> list[dict]:
    if not MY_RACES_INDEX_PATH.exists():
        return []
    with open(MY_RACES_INDEX_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save_my_races(races: list[dict]) -> None:
    MY_RACES_DIR.mkdir(parents=True, exist_ok=True)
    with open(MY_RACES_INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(races, f, ensure_ascii=False, indent=2)

def _rebuild_my_pace_model(races: list[dict]) -> None:
    if not races:
        MY_PACE_MODEL_PATH.unlink(missing_ok=True)
        return
    races_for_builder = []
    for r in races:
        course = parse_gpx((MY_RACES_DIR / f"{r['id']}.gpx").read_bytes())
        races_for_builder.append({'name': r['name'], 'course': course, 'avg_temp_c': r['avg_temp_c'], 'avg_humidity_pct': r['avg_humidity_pct'], 'hourly_weather': r.get('hourly_weather')})
    try:
        model_data = build_pace_model(races_for_builder)
    except PaceModelBuildError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    MY_PACE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MY_PACE_MODEL_PATH, 'w', encoding='utf-8') as f:
        json.dump(model_data, f, ensure_ascii=False, indent=2)

def _my_races_response() -> dict:
    races = _load_my_races()
    listed = [{k: r[k] for k in ('id', 'name', 'distance_km', 'gain_m', 'start_time_utc', 'avg_temp_c')} for r in sorted(races, key=lambda r: r['start_time_utc'], reverse=True)]
    legacy_races = []
    if not races and MY_PACE_MODEL_PATH.exists():
        try:
            legacy_races = [r['name'] for r in load_pace_model(MY_PACE_MODEL_PATH).data.get('races', [])]
        except PaceModelUnavailable:
            legacy_races = []
    return {'races': listed, 'legacy_races': legacy_races, 'is_custom_model': MY_PACE_MODEL_PATH.exists()}

@app.get('/api/my-races')
def api_my_races():
    return _my_races_response()

@app.post('/api/my-races')
async def api_my_races_add(file: UploadFile=File(...)):
    filename = Path(file.filename or 'race.gpx').name
    if not filename.lower().endswith('.gpx'):
        raise HTTPException(status_code=400, detail='GPXファイルを選択してください')
    raw = await file.read()
    try:
        course = parse_gpx(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'GPXの解析に失敗しました: {e}') from e
    start, end = (course.points[0], course.points[-1])
    if start.time is None or end.time is None:
        raise HTTPException(status_code=400, detail='このGPXにはタイムスタンプがありません。実際に走った記録のGPX(ウォッチのエクスポート等)をアップロードしてください')
    summary = course_summary(course)
    hourly_weather = fetch_actual_hourly(start.latitude, start.longitude, start.time, end.time)
    avg_temp_c, avg_humidity_pct = window_average(hourly_weather, start.time, end.time)
    race_id = uuid.uuid4().hex
    MY_RACES_DIR.mkdir(parents=True, exist_ok=True)
    (MY_RACES_DIR / f'{race_id}.gpx').write_bytes(raw)
    with _LOCK:
        races = _load_my_races()
        races.append({'id': race_id, 'name': filename.rsplit('.', 1)[0].strip() or filename, 'distance_km': summary['total_distance_km'], 'gain_m': summary['total_gain_m'], 'start_time_utc': start.time.isoformat(), 'avg_temp_c': round(avg_temp_c, 1) if avg_temp_c is not None else None, 'avg_humidity_pct': round(avg_humidity_pct, 1) if avg_humidity_pct is not None else None, 'hourly_weather': hourly_weather})
        try:
            _rebuild_my_pace_model(races)
        except HTTPException:
            (MY_RACES_DIR / f'{race_id}.gpx').unlink(missing_ok=True)
            raise
        _save_my_races(races)
    return _my_races_response()

@app.delete('/api/my-races/{race_id}')
def api_my_races_delete(race_id: str):
    with _LOCK:
        races = _load_my_races()
        remaining = [r for r in races if r['id'] != race_id]
        if len(remaining) == len(races):
            raise HTTPException(status_code=404, detail='レースが見つかりません')
        _rebuild_my_pace_model(remaining)
        _save_my_races(remaining)
        (MY_RACES_DIR / f'{race_id}.gpx').unlink(missing_ok=True)
    return _my_races_response()

@app.post('/api/gpx/upload')
async def api_gpx_upload(file: UploadFile=File(...)):
    filename = Path(file.filename or 'course.gpx').name
    if not filename.lower().endswith('.gpx'):
        raise HTTPException(status_code=400, detail='GPXファイルを選択してください')
    raw = await file.read()
    try:
        course = parse_gpx(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'GPXの解析に失敗しました: {e}') from e
    summary = course_summary(course)
    cps = detect_checkpoints(course)
    upload_id = uuid.uuid4().hex
    with _LOCK:
        _COURSES[upload_id] = {'course': course, 'summary': summary, 'cps': cps, 'filename': filename}
    return {'upload_id': upload_id, 'filename': filename, 'summary': summary, 'cps': cps}

class WeatherRequest(BaseModel):
    upload_id: str
    race_date: str
    lat: float | None = None
    lon: float | None = None

@app.post('/api/weather')
def api_weather(req: WeatherRequest):
    with _LOCK:
        entry = _COURSES.get(req.upload_id)
    if entry is None:
        raise HTTPException(status_code=404, detail='コースが見つかりません。GPXを再アップロードしてください')
    lat = req.lat if req.lat is not None else entry['summary']['start_lat']
    lon = req.lon if req.lon is not None else entry['summary']['start_lon']
    try:
        race_date = datetime.strptime(req.race_date, '%Y-%m-%d').date()
    except ValueError as e:
        raise HTTPException(status_code=400, detail='race_date は YYYY-MM-DD 形式で指定してください') from e
    try:
        result = fetch_diurnal_curve(lat, lon, race_date)
    except WeatherFetchError as e:
        with _LOCK:
            entry.pop('weather', None)
        raise HTTPException(status_code=502, detail=str(e)) from e
    with _LOCK:
        entry['weather'] = result
    return result

class CpInput(BaseModel):
    name: str
    dist_km: float
    cutoff: str | None = None

class PlanRequest(BaseModel):
    upload_id: str
    race_start_local: str
    cps: list[CpInput]
    ele_hysteresis_threshold_m: float = DEFAULT_ELE_HYSTERESIS_THRESHOLD_M
    default_cp_dwell_min: float = DEFAULT_CP_DWELL_MIN
    cp_dwell_overrides_min: dict[str, float] = {}
    bodyweight_kg: float = DEFAULT_BODYWEIGHT_KG
    cp_aid_kcal: float = CP_AID_KCAL
    manual_avg_temp_c: float | None = None
    manual_avg_humidity_pct: float | None = None
    target_elapsed_s: float | None = None

@app.post('/api/plan')
def api_plan(req: PlanRequest):
    with _LOCK:
        entry = _COURSES.get(req.upload_id)
    if entry is None:
        raise HTTPException(status_code=404, detail='コースが見つかりません。GPXを再アップロードしてください')
    active_pace_model_path = _active_pace_model_path()
    try:
        pace_model = load_pace_model(active_pace_model_path)
    except PaceModelUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    try:
        race_start_local = datetime.strptime(req.race_start_local, '%Y-%m-%dT%H:%M')
    except ValueError as e:
        raise HTTPException(status_code=400, detail='race_start_local は YYYY-MM-DDTHH:mm 形式で指定してください') from e
    weather = entry.get('weather')
    if weather is not None:
        diurnal_temp = weather['diurnal_temp']
        diurnal_hum = weather['diurnal_hum']
    elif req.manual_avg_temp_c is not None:
        diurnal_temp = {h: req.manual_avg_temp_c for h in range(24)}
        diurnal_hum = {h: req.manual_avg_humidity_pct or 60.0 for h in range(24)}
    else:
        raise HTTPException(status_code=400, detail='気温データがありません。先に /api/weather を呼ぶか、manual_avg_temp_c を指定してください')
    if len(req.cps) < 2:
        raise HTTPException(status_code=400, detail='CPは少なくともSTART/FINISHの2点が必要です')
    cps = [{'name': c.name, 'dist_km': c.dist_km, 'cutoff': c.cutoff} for c in req.cps]
    try:
        return _plan_with_target(req, entry, cps, race_start_local, pace_model, active_pace_model_path, weather, diurnal_temp, diurnal_hum)
    except CutoffInputError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

def _plan_with_target(req, entry, cps, race_start_local, pace_model, active_pace_model_path, weather, diurnal_temp, diurnal_hum) -> dict:
    result = simulate_race(course=entry['course'], cps=cps, race_start_local=race_start_local, pace_model=pace_model, diurnal_temp=diurnal_temp, diurnal_hum=diurnal_hum, ele_hysteresis_threshold_m=req.ele_hysteresis_threshold_m, default_cp_dwell_min=req.default_cp_dwell_min, cp_dwell_overrides_min=req.cp_dwell_overrides_min, bodyweight_kg=req.bodyweight_kg, kcal_per_kg_per_hr=DEFAULT_KCAL_PER_KG_PER_HR, gel_kcal=DEFAULT_GEL_KCAL, cp_aid_kcal=req.cp_aid_kcal)
    result['elevation_profile'] = entry['summary']['elevation_profile']
    result['filename'] = entry['filename']
    result['weather_source'] = weather['detail'] if weather else '手動入力'
    result['was_custom_pace_model'] = active_pace_model_path == MY_PACE_MODEL_PATH
    if req.target_elapsed_s is not None:
        target_plan = compute_target_plan(course=entry['course'], cps=cps, race_start_local=race_start_local, pace_model=pace_model, diurnal_temp=diurnal_temp, diurnal_hum=diurnal_hum, baseline_result=result, target_elapsed_s=req.target_elapsed_s, ele_hysteresis_threshold_m=req.ele_hysteresis_threshold_m, default_cp_dwell_min=req.default_cp_dwell_min, cp_dwell_overrides_min=req.cp_dwell_overrides_min, bodyweight_kg=req.bodyweight_kg, kcal_per_kg_per_hr=DEFAULT_KCAL_PER_KG_PER_HR, gel_kcal=DEFAULT_GEL_KCAL, cp_aid_kcal=req.cp_aid_kcal)
        if target_plan['adjustment_needed']:
            target_plan['plan']['elevation_profile'] = entry['summary']['elevation_profile']
            target_plan['plan']['filename'] = entry['filename']
            target_plan['plan']['weather_source'] = result['weather_source']
            target_plan['plan']['was_custom_pace_model'] = result['was_custom_pace_model']
        result['target_plan'] = target_plan
    return result

@app.get('/api/plan/pdf')
def api_plan_pdf(upload_id: str, race_start_local: str, cps: str=Query(..., description='JSON-encoded list of {name, dist_km}'), ele_hysteresis_threshold_m: float=DEFAULT_ELE_HYSTERESIS_THRESHOLD_M, default_cp_dwell_min: float=DEFAULT_CP_DWELL_MIN, cp_dwell_overrides_min: str='{}', bodyweight_kg: float=DEFAULT_BODYWEIGHT_KG, cp_aid_kcal: float=CP_AID_KCAL, manual_avg_temp_c: float | None=None, manual_avg_humidity_pct: float | None=None, target_elapsed_s: float | None=None, lang: str='ja'):
    try:
        cps_parsed = json.loads(cps)
        cp_dwell_overrides_parsed = json.loads(cp_dwell_overrides_min)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f'cps/cp_dwell_overrides_min のJSONが不正です: {e}') from e
    req = PlanRequest(upload_id=upload_id, race_start_local=race_start_local, cps=cps_parsed, ele_hysteresis_threshold_m=ele_hysteresis_threshold_m, default_cp_dwell_min=default_cp_dwell_min, cp_dwell_overrides_min=cp_dwell_overrides_parsed, bodyweight_kg=bodyweight_kg, cp_aid_kcal=cp_aid_kcal, manual_avg_temp_c=manual_avg_temp_c, manual_avg_humidity_pct=manual_avg_humidity_pct, target_elapsed_s=target_elapsed_s)
    result = api_plan(req)
    pdf_bytes = build_plan_pdf(result, lang=lang)
    race_name = (result.get('filename') or 'race').rsplit('.', 1)[0]
    filename_utf8 = quote(f'{race_name}.pdf')
    return Response(content=pdf_bytes, media_type='application/pdf', headers={'Content-Disposition': f"attachment; filename*=UTF-8''{filename_utf8}"})

class SavePredictionRequest(BaseModel):
    upload_id: str
    race_name: str
    plan_result: dict
    replace_race_id: str | None = None

def _load_race_history() -> list[dict]:
    if not RACE_HISTORY_PATH.exists():
        return []
    with open(RACE_HISTORY_PATH, 'r', encoding='utf-8') as f:
        return json.load(f).get('entries', [])

def _save_race_history(entries: list[dict]) -> None:
    RACE_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RACE_HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump({'entries': entries}, f, ensure_ascii=False, indent=2)

def _find_race_entry(entries: list[dict], race_id: str) -> dict | None:
    return next((e for e in entries if e.get('race_id') == race_id), None)

@app.post('/api/race-review/save-prediction')
def api_race_review_save_prediction(req: SavePredictionRequest):
    with _LOCK:
        entry = _COURSES.get(req.upload_id)
    if entry is None:
        raise HTTPException(status_code=404, detail='コースが見つかりません。GPXを再アップロードしてください')
    try:
        snapshot = build_prediction_snapshot(entry['course'], req.plan_result, req.race_name, entry['filename'])
    except RaceReviewError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    goal_snapshot = None
    target_plan = req.plan_result.get('target_plan')
    if target_plan and target_plan.get('adjustment_needed') and target_plan.get('plan'):
        try:
            goal_snapshot = build_prediction_snapshot(entry['course'], target_plan['plan'], req.race_name, entry['filename'])
        except RaceReviewError:
            goal_snapshot = None
    with _LOCK:
        entries = _load_race_history()
        old = _find_race_entry(entries, req.replace_race_id) if req.replace_race_id else None
        if old is not None and (not old.get('actual_summary')):
            snapshot = replace(snapshot, race_id=old['race_id'])
            if goal_snapshot is not None:
                goal_snapshot = replace(goal_snapshot, race_id=old['race_id'])
            history_entry = RaceHistoryEntry(race_id=snapshot.race_id, prediction_snapshot=snapshot, goal_prediction_snapshot=goal_snapshot)
            entries[entries.index(old)] = asdict(history_entry)
        else:
            history_entry = RaceHistoryEntry(race_id=snapshot.race_id, prediction_snapshot=snapshot, goal_prediction_snapshot=goal_snapshot)
            entries.append(asdict(history_entry))
        _save_race_history(entries)
    return {'race_id': snapshot.race_id}

@app.get('/api/race-review/history')
def api_race_review_history():
    entries = _load_race_history()
    return [{'race_id': e['race_id'], 'race_name': e['prediction_snapshot']['race_name'], 'saved_at_utc': e['prediction_snapshot']['saved_at_utc'], 'predicted_finish_local': e['prediction_snapshot']['predicted_finish_local'], 'distance_km': e['prediction_snapshot']['total_distance_km'], 'gain_m': e['prediction_snapshot']['total_gain_m'], 'has_actual': e.get('actual_summary') is not None} for e in entries]

@app.get('/api/race-review/{race_id}')
def api_race_review_get(race_id: str):
    entry = _find_race_entry(_load_race_history(), race_id)
    if entry is None:
        raise HTTPException(status_code=404, detail='レースが見つかりません')
    return entry

@app.post('/api/race-review/{race_id}/upload-actual')
async def api_race_review_upload_actual(race_id: str, file: UploadFile=File(...)):
    entry = _find_race_entry(_load_race_history(), race_id)
    if entry is None:
        raise HTTPException(status_code=404, detail='レースが見つかりません')
    filename = Path(file.filename or 'actual.gpx').name
    if not filename.lower().endswith('.gpx'):
        raise HTTPException(status_code=400, detail='GPXファイルを選択してください')
    raw = await file.read()
    try:
        actual_course = parse_gpx(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'GPXの解析に失敗しました: {e}') from e

    def _snapshot_from_dict(snap_data: dict) -> PredictionSnapshot:
        return PredictionSnapshot(race_id=snap_data['race_id'], race_name=snap_data['race_name'], course_filename=snap_data['course_filename'], saved_at_utc=snap_data['saved_at_utc'], race_start_local=snap_data['race_start_local'], predicted_finish_local=snap_data['predicted_finish_local'], predicted_elapsed_s=snap_data['predicted_elapsed_s'], total_distance_km=snap_data['total_distance_km'], total_gain_m=snap_data['total_gain_m'], total_loss_m=snap_data['total_loss_m'], cp_schedule=snap_data['cp_schedule'], cp_targets=[CpTarget(**t) for t in snap_data['cp_targets']], was_custom_pace_model=snap_data['was_custom_pace_model'], pace_model_reference_temp_c=snap_data.get('pace_model_reference_temp_c'), weather_source=snap_data.get('weather_source', ''))
    snapshot = _snapshot_from_dict(entry['prediction_snapshot'])
    try:
        cp_results = match_actual_cps(snapshot, actual_course)
    except RaceReviewError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    segment_results = build_segment_results(snapshot, cp_results, actual_course)
    actual_data = build_actual_race_data(filename, actual_course, cp_results, segment_results)
    entry['actual_summary'] = asdict(actual_data)
    entry['cp_results'] = [asdict(r) for r in cp_results]
    entry['segment_results'] = [asdict(r) for r in segment_results]
    goal_snap_data = entry.get('goal_prediction_snapshot')
    if goal_snap_data:
        try:
            goal_snapshot = _snapshot_from_dict(goal_snap_data)
            goal_cp_results = match_actual_cps(goal_snapshot, actual_course)
            goal_segment_results = build_segment_results(goal_snapshot, goal_cp_results, actual_course)
            entry['goal_cp_results'] = [asdict(r) for r in goal_cp_results]
            entry['goal_segment_results'] = [asdict(r) for r in goal_segment_results]
        except RaceReviewError:
            entry['goal_cp_results'] = []
            entry['goal_segment_results'] = []
    with _LOCK:
        entries = _load_race_history()
        for i, e in enumerate(entries):
            if e.get('race_id') == race_id:
                entries[i] = entry
                break
        _save_race_history(entries)
    return entry

@app.delete('/api/race-review/{race_id}')
def api_race_review_delete(race_id: str):
    with _LOCK:
        entries = _load_race_history()
        remaining = [e for e in entries if e.get('race_id') != race_id]
        if len(remaining) == len(entries):
            raise HTTPException(status_code=404, detail='レースが見つかりません')
        _save_race_history(remaining)
    return {'status': 'deleted'}
app.mount('/', StaticFiles(directory=str(WEB_DIR), html=True), name='web')
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app:app', host='127.0.0.1', port=8020, reload=False)
