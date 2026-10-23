from __future__ import annotations
import re
from datetime import datetime, timedelta
CUTOFF_TIGHT_MARGIN_MIN = 30.0
TRAP_MIN_EARLIER_MIN = 10.0
_CUTOFF_RE = re.compile('^\\s*(\\d{1,2}):?([0-5]\\d)\\s*$')

class CutoffInputError(ValueError):
    pass

def _parse_cutoff(text: str) -> tuple[int, int]:
    normalized = text.translate(str.maketrans('０１２３４５６７８９：', '0123456789:'))
    m = _CUTOFF_RE.match(normalized)
    if not m:
        raise CutoffInputError(f'関門時刻は 14:30 のように入力してください: {text}')
    return (int(m.group(1)), int(m.group(2)))

def resolve_cutoffs(cp_schedule: list[dict], race_start_local: datetime) -> list[datetime | None]:
    start_midnight = race_start_local.replace(hour=0, minute=0, second=0, microsecond=0)
    anchor = race_start_local
    resolved: list[datetime | None] = []
    for i, cp in enumerate(cp_schedule):
        text = (cp.get('cutoff') or '').strip()
        if i == 0 or not text:
            resolved.append(None)
            continue
        hour, minute = _parse_cutoff(text)
        if hour >= 24:
            at = start_midnight + timedelta(hours=hour, minutes=minute)
        else:
            at = anchor.replace(hour=hour, minute=minute, second=0, microsecond=0)
            while at <= anchor:
                at += timedelta(days=1)
        resolved.append(at)
        anchor = max(anchor, at)
    return resolved

def apply_cutoffs(cp_schedule: list[dict], race_start_local: datetime) -> dict | None:
    cutoffs = resolve_cutoffs(cp_schedule, race_start_local)
    idx = [i for i, c in enumerate(cutoffs) if c is not None]
    if not idx:
        return None
    arrival = {i: race_start_local + timedelta(seconds=cp_schedule[i]['elapsed_s']) for i in idx}
    official_margin = {i: (cutoffs[i] - arrival[i]).total_seconds() / 60.0 for i in idx}
    effective_margin: dict[int, float] = {}
    bound_by: dict[int, int] = {}
    next_i = None
    for i in reversed(idx):
        if next_i is not None and effective_margin[next_i] < official_margin[i]:
            effective_margin[i] = effective_margin[next_i]
            bound_by[i] = bound_by[next_i]
        else:
            effective_margin[i] = official_margin[i]
            bound_by[i] = i
        next_i = i
    start_date = race_start_local.date()
    rows = []
    for i in idx:
        r = cp_schedule[i]
        official = cutoffs[i]
        eff = arrival[i] + timedelta(minutes=effective_margin[i])
        earlier_min = official_margin[i] - effective_margin[i]
        trap = bound_by[i] != i and earlier_min >= TRAP_MIN_EARLIER_MIN
        if effective_margin[i] < 0:
            status = 'over'
        elif effective_margin[i] < CUTOFF_TIGHT_MARGIN_MIN:
            status = 'tight'
        else:
            status = 'ok'
        r.update({'cutoff_local': official.strftime('%Y-%m-%d %H:%M'), 'cutoff_clock': official.strftime('%H:%M'), 'cutoff_day_offset': (official.date() - start_date).days, 'cutoff_margin_min': round(official_margin[i]), 'cutoff_missed': official_margin[i] < 0, 'effective_cutoff_local': eff.strftime('%Y-%m-%d %H:%M'), 'effective_cutoff_clock': eff.strftime('%H:%M'), 'effective_cutoff_day_offset': (eff.date() - start_date).days, 'effective_margin_min': round(effective_margin[i]), 'cutoff_trap': trap, 'cutoff_trap_by': cp_schedule[bound_by[i]]['name'] if trap else None, 'cutoff_trap_earlier_min': round(earlier_min) if trap else 0, 'cutoff_status': status})
        rows.append((i, r))
    traps: list[dict] = []
    for i, r in rows:
        if not r['cutoff_trap']:
            continue
        b = bound_by[i]
        group = next((g for g in traps if g['by_index'] == b), None)
        if group is None:
            group = {'by_index': b, 'by': cp_schedule[b]['name'], 'by_cutoff_clock': cp_schedule[b]['cutoff_clock'], 'by_cutoff_day_offset': cp_schedule[b]['cutoff_day_offset'], 'cps': []}
            traps.append(group)
        group['cps'].append({'name': r['name'], 'cutoff_clock': r['cutoff_clock'], 'cutoff_day_offset': r['cutoff_day_offset'], 'effective_cutoff_clock': r['effective_cutoff_clock'], 'effective_cutoff_day_offset': r['effective_cutoff_day_offset'], 'minutes_earlier': r['cutoff_trap_earlier_min']})
    for g in traps:
        del g['by_index']
    tightest = min((r for _, r in rows), key=lambda r: r['cutoff_margin_min'])
    return {'n_cutoffs': len(rows), 'missed': [r['name'] for _, r in rows if r['cutoff_missed']], 'n_tight': sum((0 <= r['cutoff_margin_min'] < CUTOFF_TIGHT_MARGIN_MIN for _, r in rows)), 'tight_margin_min': CUTOFF_TIGHT_MARGIN_MIN, 'tightest': {'name': tightest['name'], 'margin_min': tightest['cutoff_margin_min']}, 'traps': traps}
