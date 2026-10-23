from __future__ import annotations
import json
from pathlib import Path
from analysis.heat_model import heat_penalty_factor
SLOPE_BUCKET_WIDTH = 3.0

class PaceModelUnavailable(Exception):
    pass

def slope_bucket(slope_pct: float) -> float:
    return round(slope_pct / SLOPE_BUCKET_WIDTH) * SLOPE_BUCKET_WIDTH

class PaceModel:

    def __init__(self, data: dict):
        self.data = data
        self.slope_pace_model = {float(k): v['pace_min_km'] for k, v in data['slope_pace_model'].items()}
        self.sorted_buckets = sorted(self.slope_pace_model.keys())
        fatigue = data['fatigue_model']
        self.fatigue_intercept = fatigue['intercept']
        self.fatigue_slope_per_km = fatigue['slope_per_km']
        self.fatigue_max_observed_km = fatigue['max_observed_km']
        races = data['races']
        w_sum = sum((r['recency_weight'] for r in races if r.get('avg_temp_c') is not None))
        t_sum = sum((r['recency_weight'] * r['avg_temp_c'] for r in races if r.get('avg_temp_c') is not None))
        self.reference_temp_c = t_sum / w_sum if w_sum else 20.0
        self.heat_normalized = bool(data.get('heat_model', {}).get('normalized'))
        if self.heat_normalized:
            self.reference_heat_factor = 1.0
        else:
            f_sum = sum((r['recency_weight'] * heat_penalty_factor(r['avg_temp_c'], r.get('avg_humidity_pct')) for r in races if r.get('avg_temp_c') is not None))
            self.reference_heat_factor = f_sum / w_sum if w_sum else 1.0

    def lookup_pace(self, slope_pct: float) -> float:
        b = slope_bucket(slope_pct)
        if b in self.slope_pace_model:
            return self.slope_pace_model[b]
        if b < self.sorted_buckets[0]:
            return self.slope_pace_model[self.sorted_buckets[0]]
        if b > self.sorted_buckets[-1]:
            return self.slope_pace_model[self.sorted_buckets[-1]]
        nearest = min(self.sorted_buckets, key=lambda x: abs(x - b))
        return self.slope_pace_model[nearest]

    def fatigue_factor(self, cum_km: float, clamp=(0.5, 2.5)) -> float:
        f = self.fatigue_intercept + self.fatigue_slope_per_km * cum_km
        return max(clamp[0], min(clamp[1], f))

def load_pace_model(path: Path) -> PaceModel:
    if not path.exists():
        raise PaceModelUnavailable(f'pace_model.json が見つかりません ({path})。先に Trail Race Planning Workflow の scripts/build_pace_model.py を実行してください。')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return PaceModel(data)
