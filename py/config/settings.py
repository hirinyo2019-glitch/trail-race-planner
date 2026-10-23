import os
import sys
from pathlib import Path
if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent
_workflow_root_override = os.environ.get('RACE_PREDICTOR_WORKFLOW_ROOT')
WORKFLOW_ROOT = Path(_workflow_root_override) if _workflow_root_override else APP_DIR.parent
PACE_MODEL_PATH = WORKFLOW_ROOT / 'past-race-gpx' / 'pace_model.json'
MY_PACE_MODEL_PATH = APP_DIR / 'my_pace_model.json'
MY_RACES_DIR = APP_DIR / 'my_races'
RACE_HISTORY_PATH = APP_DIR / 'race_history.json'
WEB_DIR = APP_DIR / 'web'
OUTPUT_DIR = APP_DIR / 'output'
UPLOAD_DIR = APP_DIR / 'uploads'
SCRIPTS_DIR = APP_DIR / 'scripts'
FETCH_WEATHER_PS1 = SCRIPTS_DIR / 'fetch_weather.ps1'
APP_TITLE = 'トレイルレース予測プランナー'
DEFAULT_BODYWEIGHT_KG = 70.0
DEFAULT_KCAL_PER_KG_PER_HR = 3.5
DEFAULT_GEL_KCAL = 100.0
DEFAULT_CP_DWELL_MIN = 5.0
FORECAST_HORIZON_DAYS = 15
CLIMATOLOGY_YEARS_BACK = 6
CLIMATOLOGY_WINDOW_DAYS = 3
APP_DIR = Path('/data')
PACE_MODEL_PATH = Path('/app/pace_model.json')
MY_PACE_MODEL_PATH = APP_DIR / 'my_pace_model.json'
MY_RACES_DIR = APP_DIR / 'my_races'
RACE_HISTORY_PATH = APP_DIR / 'race_history.json'
WEB_DIR = APP_DIR / 'web'
OUTPUT_DIR = APP_DIR / 'output'
UPLOAD_DIR = APP_DIR / 'uploads'
