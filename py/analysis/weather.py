from __future__ import annotations
import json
import platform
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from config.settings import CLIMATOLOGY_WINDOW_DAYS, CLIMATOLOGY_YEARS_BACK, FETCH_WEATHER_PS1, FORECAST_HORIZON_DAYS

class WeatherFetchError(Exception):
    pass

def _fetch_http(lat: float, lon: float, mode: str, start_date: str, end_date: str, timezone: str='auto') -> dict:
    base = 'https://api.open-meteo.com/v1/forecast' if mode == 'forecast' else 'https://archive-api.open-meteo.com/v1/archive'
    query = urllib.parse.urlencode({'latitude': lat, 'longitude': lon, 'start_date': start_date, 'end_date': end_date, 'hourly': 'temperature_2m,relative_humidity_2m', 'timezone': timezone})
    try:
        with urllib.request.urlopen(f'{base}?{query}', timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise WeatherFetchError(f'天気データの取得に失敗しました: {e}') from e

def _fetch_weather(lat: float, lon: float, mode: str, start_date: str, end_date: str, timezone: str='auto') -> dict:
    if platform.system() == 'Windows':
        return _run_ps1(lat, lon, mode, start_date, end_date, timezone)
    return _fetch_http(lat, lon, mode, start_date, end_date, timezone)

def _run_ps1(lat: float, lon: float, mode: str, start_date: str, end_date: str, timezone: str='auto') -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / 'weather.json'
        cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(FETCH_WEATHER_PS1), '-Lat', str(lat), '-Lon', str(lon), '-Mode', mode, '-StartDate', start_date, '-EndDate', end_date, '-Timezone', timezone, '-OutFile', str(out_path)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        except subprocess.TimeoutExpired as e:
            raise WeatherFetchError('天気データの取得がタイムアウトしました') from e
        except FileNotFoundError as e:
            raise WeatherFetchError('PowerShellが見つかりません(Windows以外の環境では気温は手動入力してください)') from e
        if proc.returncode != 0 or not out_path.exists():
            raise WeatherFetchError(f'天気データの取得に失敗しました: {proc.stdout}\n{proc.stderr}')
        with open(out_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)

def _diurnal_from_hourly(hourly_batches: list[dict]) -> tuple[dict, dict]:
    temp_by_hour = {h: [] for h in range(24)}
    hum_by_hour = {h: [] for h in range(24)}
    for hourly in hourly_batches:
        times = hourly.get('time', [])
        temps = hourly.get('temperature_2m', [])
        hums = hourly.get('relative_humidity_2m', [])
        for t, temp, hum in zip(times, temps, hums):
            hour = int(t.split('T')[1].split(':')[0])
            if temp is not None:
                temp_by_hour[hour].append(temp)
            if hum is not None:
                hum_by_hour[hour].append(hum)
    diurnal_temp = {h: sum(v) / len(v) if v else None for h, v in temp_by_hour.items()}
    diurnal_hum = {h: sum(v) / len(v) if v else None for h, v in hum_by_hour.items()}
    for target in (diurnal_temp, diurnal_hum):
        known = [h for h in range(24) if target[h] is not None]
        if not known:
            continue
        for h in range(24):
            if target[h] is None:
                nearest = min(known, key=lambda k: abs(k - h))
                target[h] = target[nearest]
    return (diurnal_temp, diurnal_hum)

def fetch_actual_hourly(lat: float, lon: float, start_dt: datetime, end_dt: datetime) -> dict[str, tuple[float, float | None]]:
    try:
        hourly = _fetch_weather(lat, lon, 'archive', start_dt.date().isoformat(), end_dt.date().isoformat(), 'UTC').get('hourly', {})
    except WeatherFetchError:
        return {}
    return {tm: (t, h) for tm, t, h in zip(hourly.get('time', []), hourly.get('temperature_2m', []), hourly.get('relative_humidity_2m', [])) if t is not None}

def window_average(hourly_weather: dict[str, tuple[float, float | None]], start_dt: datetime, end_dt: datetime) -> tuple[float | None, float | None]:
    start_hour = start_dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:00')
    end_hour = end_dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:00')
    window = [v for tm, v in hourly_weather.items() if start_hour <= tm <= end_hour]
    temps = [t for t, _ in window]
    hums = [h for _, h in window if h is not None]
    return (sum(temps) / len(temps) if temps else None, sum(hums) / len(hums) if hums else None)

def fetch_diurnal_curve(lat: float, lon: float, race_date: date) -> dict:
    today = date.today()
    days_out = (race_date - today).days
    if 0 <= days_out <= FORECAST_HORIZON_DAYS:
        d = race_date.isoformat()
        hourly = _fetch_weather(lat, lon, 'forecast', d, d).get('hourly', {})
        diurnal_temp, diurnal_hum = _diurnal_from_hourly([hourly])
        return {'mode': 'forecast', 'diurnal_temp': diurnal_temp, 'diurnal_hum': diurnal_hum, 'detail': f'{d} の天気予報(Open-Meteo forecast API)'}
    batches = []
    years_used = []
    for years_back in range(1, CLIMATOLOGY_YEARS_BACK + 1):
        y = race_date.year - years_back
        try:
            center = date(y, race_date.month, race_date.day)
        except ValueError:
            center = date(y, race_date.month, 28)
        start = center - timedelta(days=CLIMATOLOGY_WINDOW_DAYS)
        end = center + timedelta(days=CLIMATOLOGY_WINDOW_DAYS)
        try:
            hourly = _fetch_weather(lat, lon, 'archive', start.isoformat(), end.isoformat()).get('hourly', {})
            batches.append(hourly)
            years_used.append(y)
        except WeatherFetchError:
            continue
    if not batches:
        raise WeatherFetchError('気候平年値の取得に全て失敗しました')
    diurnal_temp, diurnal_hum = _diurnal_from_hourly(batches)
    return {'mode': 'climatology', 'diurnal_temp': diurnal_temp, 'diurnal_hum': diurnal_hum, 'detail': f"{race_date.month}/{race_date.day}前後 ±{CLIMATOLOGY_WINDOW_DAYS}日の気候平年値({', '.join((str(y) for y in years_used))}年平均)"}
