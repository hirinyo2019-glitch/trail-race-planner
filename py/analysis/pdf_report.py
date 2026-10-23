from __future__ import annotations
import io
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Group, Line, Polygon, PolyLine, String
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
_JP_FONT = 'NotoSansJP'
_JP_FONT_PATH = Path(__file__).resolve().parent.parent / 'assets' / 'fonts' / 'NotoSansJP-Regular.ttf'
pdfmetrics.registerFont(TTFont(_JP_FONT, str(_JP_FONT_PATH)))
_TABLE_HEADER_BG = colors.HexColor('#eef3fa')
_TABLE_GRIDLINE = colors.HexColor('#e1e0d9')
_TEXT_MUTED = colors.HexColor('#52514e')
_CHART_LINE_COLOR = colors.HexColor('#256abf')
_CHART_FILL_COLOR = colors.HexColor('#e8ecf3')
_CHART_CP_LINE_COLOR = colors.HexColor('#b5b3a8')
_CELL_STYLE_LEFT = ParagraphStyle('cell_left', fontName=_JP_FONT, fontSize=8, leading=10.5, alignment=TA_LEFT)
_CELL_STYLE_RIGHT = ParagraphStyle('cell_right', fontName=_JP_FONT, fontSize=8, leading=10.5, alignment=TA_RIGHT)
_TEXT = {'ja': {'cp_header': ['Point', '距離/標高', 'D+/D-', '区間タイム', '到着/累積', '気温/体感/湿度'], 'elev': '標高{v}m', 'feels': '体感{t}C/{h}%', 'cum': '累積{v}', 'nut_header': ['区間', '所要時間', '水分', 'カロリー', 'ジェル'], 'gels': '{v}個', 'cp_heading': 'チェックポイント通過予定', 'stats': '距離 {km}km \u3000D+ {gain}m \u3000D- {loss}m \u3000予想ゴールタイム {t}(到着目安 {finish}) \u3000スタート {start}', 'profile': 'コースプロファイル(標高・チェックポイント)', 'nutrition': '補給食プラン', 'title': '{name} -- レースプラン', 'generated': '作成日時: {v}', 'feasible': 'この目標タイムは、区間特性に応じたペース配分で達成可能な見込みです。', 'infeasible': 'この目標タイムには届きません。達成可能な最速は約{v}です。', 'target_heading': '目標タイムプラン(目標 {v})', 'target_cp_heading': '目標タイムでのチェックポイント通過予定', 'cutoff_header': '関門/余裕', 'cutoff_official': '関門{c}', 'cutoff_effective': '実質{c}', 'min': '{v}分', 'next_day': '翌', 'days_later': '{n}日後', 'cutoff_over': '予測のペースでは、{n}か所の関門に間に合いません({list})。', 'cutoff_traps': 'ひっかけ関門: {list}(実質の関門までに着く必要があります)。'}, 'en': {'cp_header': ['Point', 'Dist/Elev', 'D+/D-', 'Segment', 'Arrival/Elapsed', 'Temp/Feels/Hum'], 'elev': '{v}m', 'feels': 'feels {t}C/{h}%', 'cum': 'total {v}', 'nut_header': ['Segment', 'Time', 'Water', 'Calories', 'Gels'], 'gels': '{v}', 'cp_heading': 'Checkpoint schedule', 'stats': 'Distance {km}km   D+ {gain}m   D- {loss}m   Predicted finish time {t} (arrive ~{finish})   Start {start}', 'profile': 'Course profile (elevation and checkpoints)', 'nutrition': 'Nutrition plan', 'title': '{name} -- Race plan', 'generated': 'Generated: {v}', 'feasible': 'This target time looks achievable with pacing matched to each type of terrain.', 'infeasible': 'This target time is out of reach. The fastest realistic time is about {v}.', 'target_heading': 'Target time plan (target {v})', 'target_cp_heading': 'Checkpoint schedule at target time', 'cutoff_header': 'Cutoff/Margin', 'cutoff_official': 'cutoff {c}', 'cutoff_effective': 'really {c}', 'min': '{v} min', 'next_day': 'next day ', 'days_later': '+{n} days ', 'cutoff_over': 'At the predicted pace you miss {n} cutoff(s) ({list}).', 'cutoff_traps': 'Trap cutoffs: {list} (you need to arrive by the effective cutoff).'}}

def _hms(total_seconds: float) -> str:
    t = round(abs(total_seconds))
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f'{h}:{m:02d}:{s:02d}'

def _styles():
    base = getSampleStyleSheet()
    return {'title': ParagraphStyle('title', fontName=_JP_FONT, fontSize=16, leading=20, spaceAfter=4), 'meta': ParagraphStyle('meta', fontName=_JP_FONT, fontSize=9, leading=13, textColor=_TEXT_MUTED), 'h2': ParagraphStyle('h2', fontName=_JP_FONT, fontSize=12, leading=16, spaceBefore=14, spaceAfter=6), 'body': ParagraphStyle('body', fontName=_JP_FONT, fontSize=9, leading=13), 'cell': ParagraphStyle('cell', fontName=_JP_FONT, fontSize=8, leading=11)}

def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + '…'

def _cell(text: str, align: str='left') -> Paragraph:
    style = _CELL_STYLE_LEFT if align == 'left' else _CELL_STYLE_RIGHT
    return Paragraph(text.replace('\n', '<br/>'), style)

def _table_style(header_rows: int=1) -> TableStyle:
    return TableStyle([('FONTNAME', (0, 0), (-1, -1), _JP_FONT), ('FONTSIZE', (0, 0), (-1, -1), 8), ('BACKGROUND', (0, 0), (-1, header_rows - 1), _TABLE_HEADER_BG), ('FONTNAME', (0, 0), (-1, header_rows - 1), _JP_FONT), ('GRID', (0, 0), (-1, -1), 0.5, _TABLE_GRIDLINE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('ALIGN', (1, 0), (-1, -1), 'RIGHT'), ('ALIGN', (0, 0), (0, -1), 'LEFT'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5)])

def _cp_schedule_table(cp_schedule: list[dict], tx: dict) -> Table:
    has_cutoff = any((r.get('cutoff_clock') for r in cp_schedule))
    header = list(tx['cp_header'])
    if has_cutoff:
        header.insert(5, tx['cutoff_header'])
    rows = [header]
    prev = None
    for r in cp_schedule:
        elev = tx['elev'].format(v=r['elevation_m']) if r.get('elevation_m') is not None else ''
        gain_loss = '-' if r['dist_km'] == 0.0 else f"+{r['gain_m']}/-{r['loss_m']}m"
        weather = f"{r['temp_c']}C" if r.get('temp_c') is not None else '-'
        weather_sub = tx['feels'].format(t=r['feels_like_c'], h=r['humidity_pct']) if r.get('feels_like_c') is not None else ''
        if prev is None:
            segment_time = '-'
        else:
            seg_s = r['elapsed_s'] - (prev['elapsed_s'] + prev['dwell_min'] * 60.0)
            segment_time = _hms(seg_s)
        row = [_cell(r['name'], 'left'), _cell(f"{r['dist_km']}km\n{elev}", 'right'), _cell(gain_loss, 'right'), _cell(segment_time, 'right'), _cell(f"{r['arrival_clock']}\n" + tx['cum'].format(v=_hms(r['elapsed_s'])), 'right'), _cell(f'{weather}\n{weather_sub}', 'right')]
        if has_cutoff:
            row.insert(5, _cell(_cutoff_text(r, tx), 'right'))
        rows.append(row)
        prev = r
    widths = [28, 20, 20, 18, 26, 28, 26] if has_cutoff else [30, 24, 24, 20, 28, 30]
    t = Table(rows, colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(_table_style())
    return t

def _day_clock(clock: str, day_offset: int, tx: dict) -> str:
    if day_offset <= 0:
        return clock
    return (tx['next_day'] if day_offset == 1 else tx['days_later'].format(n=day_offset)) + clock

def _cutoff_text(r: dict, tx: dict) -> str:
    if not r.get('cutoff_clock'):
        return '-'
    m = r['effective_margin_min']
    lines = [tx['min'].format(v=f"{('+' if m > 0 else '')}{m}"), tx['cutoff_official'].format(c=_day_clock(r['cutoff_clock'], r['cutoff_day_offset'], tx))]
    if r.get('cutoff_trap'):
        lines.append(tx['cutoff_effective'].format(c=_day_clock(r['effective_cutoff_clock'], r['effective_cutoff_day_offset'], tx)))
    return '\n'.join(lines)

def _nutrition_table(nutrition_plan: list[dict], tx: dict) -> Table:
    header = tx['nut_header']
    rows = [header]
    for n in nutrition_plan:
        rows.append([_cell(f"{n['from']} -> {n['to']}", 'left'), _cell(f"{n['seg_h']}h", 'right'), _cell(f"{n['water_ml']}ml", 'right'), _cell(f"{n['net_kcal']}kcal", 'right'), _cell(tx['gels'].format(v=n['gels']), 'right')])
    t = Table(rows, colWidths=[58 * mm, 20 * mm, 20 * mm, 26 * mm, 18 * mm], repeatRows=1)
    t.setStyle(_table_style())
    return t
_CHART_CP_LABEL_MAX_CHARS = 18
_CHART_CP_LABEL_MIN_GAP_MM = 3.5

def _elevation_chart(elevation_profile_timed: list, cp_schedule: list[dict], width_mm: float=178, height_mm: float=78) -> Drawing:
    width, height = (width_mm * mm, height_mm * mm)
    if not elevation_profile_timed:
        return Drawing(width, 0)
    left_pad, right_pad, top_pad, bottom_pad = (10 * mm, 4 * mm, 28 * mm, 4 * mm)
    plot_w = width - left_pad - right_pad
    plot_h = height - top_pad - bottom_pad
    total_km = elevation_profile_timed[-1][0] or 1.0
    eles = [p[1] for p in elevation_profile_timed]
    ele_pad = max(10.0, (max(eles) - min(eles)) * 0.1)
    min_ele, max_ele = (min(eles) - ele_pad, max(eles) + ele_pad)
    ele_range = max_ele - min_ele or 1.0

    def x_of(km: float) -> float:
        return left_pad + km / total_km * plot_w

    def y_of(ele: float) -> float:
        return bottom_pad + (ele - min_ele) / ele_range * plot_h
    d = Drawing(width, height)
    area_points = [x_of(0), y_of(min_ele)]
    for km, ele, _ in elevation_profile_timed:
        area_points += [x_of(km), y_of(ele)]
    area_points += [x_of(total_km), y_of(min_ele)]
    d.add(Polygon(area_points, fillColor=_CHART_FILL_COLOR, strokeColor=None))
    line_points = []
    for km, ele, _ in elevation_profile_timed:
        line_points += [x_of(km), y_of(ele)]
    d.add(PolyLine(line_points, strokeColor=_CHART_LINE_COLOR, strokeWidth=1.2))
    last_label_x = None
    for cp in cp_schedule:
        x = x_of(cp['dist_km'])
        d.add(Line(x, bottom_pad, x, height - top_pad, strokeColor=_CHART_CP_LINE_COLOR, strokeWidth=0.6, strokeDashArray=(2, 2)))
        if last_label_x is not None and x - last_label_x < _CHART_CP_LABEL_MIN_GAP_MM * mm:
            continue
        last_label_x = x
        label_group = Group()
        label_group.add(String(0, 0, _truncate(cp['name'], _CHART_CP_LABEL_MAX_CHARS), fontName=_JP_FONT, fontSize=6.5, fillColor=_TEXT_MUTED, textAnchor='start'))
        label_group.translate(x + 2, height - top_pad + 2)
        label_group.rotate(90)
        d.add(label_group)
    d.add(String(2, y_of(min_ele + ele_pad) - 2, f'{round(min_ele + ele_pad)}m', fontName=_JP_FONT, fontSize=6.5, fillColor=_TEXT_MUTED))
    d.add(String(2, y_of(max_ele - ele_pad) - 2, f'{round(max_ele - ele_pad)}m', fontName=_JP_FONT, fontSize=6.5, fillColor=_TEXT_MUTED))
    return d

def _plan_flow(story: list, styles: dict, result: dict, tx: dict, cp_heading: str | None=None) -> None:
    stats = tx['stats'].format(km=result['total_distance_km'], gain=result['total_gain_m'], loss=result['total_loss_m'], t=_hms(result['predicted_elapsed_s']), finish=result['predicted_finish_clock'], start=result['race_start_local'].replace('T', ' '))
    story.append(Paragraph(stats, styles['body']))
    story.append(Spacer(1, 8))
    if result.get('elevation_profile_timed'):
        story.append(KeepTogether([Paragraph(tx['profile'], styles['h2']), _elevation_chart(result['elevation_profile_timed'], result['cp_schedule'])]))
        story.append(Spacer(1, 6))
    story.append(Paragraph(cp_heading or tx['cp_heading'], styles['h2']))
    cutoff_summary = result.get('cutoff_summary')
    if cutoff_summary:
        over = cutoff_summary['missed']
        if over:
            story.append(Paragraph(tx['cutoff_over'].format(n=len(over), list=escape(', '.join(over))), styles['body']))
        if cutoff_summary['traps']:
            story.append(Paragraph(tx['cutoff_traps'].format(list=escape(', '.join((c['name'] for g in cutoff_summary['traps'] for c in g['cps'])))), styles['body']))
        if over or cutoff_summary['traps']:
            story.append(Spacer(1, 4))
    story.append(_cp_schedule_table(result['cp_schedule'], tx))
    if result.get('nutrition_plan'):
        story.append(Paragraph(tx['nutrition'], styles['h2']))
        story.append(_nutrition_table(result['nutrition_plan'], tx))

def build_plan_pdf(result: dict, lang: str='ja') -> bytes:
    tx = _TEXT.get(lang, _TEXT['ja'])
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm)
    styles = _styles()
    story = []
    race_name = result.get('filename', 'race').rsplit('.', 1)[0] if result.get('filename') else 'race'
    generated_at = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M')
    story.append(Paragraph(tx['title'].format(name=race_name), styles['title']))
    story.append(Paragraph(tx['generated'].format(v=generated_at), styles['meta']))
    story.append(Spacer(1, 6))
    _plan_flow(story, styles, result, tx)
    target_plan = result.get('target_plan')
    if target_plan and target_plan.get('adjustment_needed') and target_plan.get('plan'):
        story.append(Spacer(1, 14))
        feasible_note = tx['feasible'] if target_plan['feasible'] else tx['infeasible'].format(v=_hms(target_plan['achieved_elapsed_s']))
        story.append(Paragraph(tx['target_heading'].format(v=_hms(target_plan['target_elapsed_s'])), styles['h2']))
        story.append(Paragraph(feasible_note, styles['body']))
        story.append(Spacer(1, 8))
        _plan_flow(story, styles, target_plan['plan'], tx, cp_heading=tx['target_cp_heading'])
    doc.build(story)
    return buf.getvalue()
