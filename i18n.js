// UI text in Japanese / English. t('key', {param}) fills {param} placeholders.
// Values are trusted markup (some contain <b>, <a>, entities); anything coming
// from user input or GPX files must still go through esc() before it is
// passed in as a param.

const I18N = {
  ja: {
    'tab.myRaces': 'マイレース',
    'tab.predict': '予測',
    'tab.review': '振り返り',
    'common.error': 'エラー: {v}',
    'common.delete': '削除',
    'diff.min': '{v}分',

    // ----- 予測: 1. コースGPX -----
    'course.title': '1. コースGPX',
    'course.note': '大会公式のコースGPXを選択してください(名前付きwaypointがあればCPとして自動検出します)。',
    'course.dzTitle': 'GPXファイルを選択',
    'course.dzSub': '.gpx ファイルのみ対応',
    'course.dzPicked': '{name}(タップで別のファイルを選択)',
    'course.loading': '読み込み中...',
    'link.loading': '{name} のコースを読み込み中...',
    'link.loaded': '{name} のコース・スタート時刻・関門（{n} か所）を入れました。CP の設定で確認できます。',
    'link.failed': 'コースを読み込めませんでした({v})。GPX をダウンロードして選んでください。',
    'stat.distance': '距離',

    // ----- 予測: 2. レース条件 -----
    'setup.title': '2. レース条件',
    'setup.raceStart': 'スタート日時(現地時刻)',
    'setup.bodyweight': '体重(kg)',
    'setup.manualTemp': '平均気温(&deg;C)',
    'setup.manualHum': '平均湿度(%)',
    'setup.cpWarn': 'CPを自動検出できなかったため、距離を仮配置しています。「チェックポイント」で確認・修正してください。',
    'setup.checkpoints': 'チェックポイント',
    'setup.cpName': '名前',
    'setup.cpDist': '距離(km)',
    'setup.cpCutoff': '関門',
    'setup.cpDistCutoff': '距離(km)/関門',
    'setup.cpCutoffPlaceholder': '関門 --:--',
    'setup.cutoffNote': '関門(任意): 大会の関門時刻を 14:30 のように入れると、関門までの余裕を表示します。日をまたぐ関門は自動で翌日として扱います。2日以上あとの関門は 30:00(2日目の6:00)のように24を足して入れてください。',
    'setup.addCp': '+ CPを追加',
    'setup.dwell': 'CP滞在時間(分)',
    'setup.target': '目標タイム(任意)<span class="pro-badge">PRO</span>',
    'setup.targetNote': '予測より速い目標を入れると、登り・下り・平地ごとのペース配分プランも表示します。',
    'setup.hours': '時間',
    'setup.minutes': '分',
    'setup.run': '予測する',
    'setup.running': '計算中...',
    'weather.needStart': 'スタート日時を入力してください',
    'weather.fetching': '気温データを取得中...',
    'weather.forecast': '天気予報',
    'weather.normals': '平年値',
    'weather.ok': '気温: {src}(平均 約{avg}&deg;C)',
    'weather.fail': '気温データを取得できませんでした({e})。気温を入力してください。',

    // ----- 予測結果 -----
    'report.finishLabel': '予想ゴールタイム',
    'report.finishSub': 'ゴール目安 {finish} ・ スタート {start}',
    'report.highest': '最高点',
    'report.heat': '暑さの影響 {v}%(補正前 {base})',
    'report.customModel': 'マイペースモデルで予測しています。',
    'report.standardModel': '標準モデルで予測しています。<a href="#" id="toMyRacesLink">マイレース</a>に過去レースを登録すると、あなた専用の予測になります。',
    'report.cpTitle': 'チェックポイント通過予定',
    'report.chartTitle': '標高と通過予定',
    'report.pdf': 'PDFで書き出す',
    'report.saved': 'この予測は自動で保存されました。レース後に「振り返り」で実際の記録と比べられます。',
    'report.saveFail': '自動保存できませんでした: {e}',
    'report.tooltip': '<b>{km} km</b> (標高{e}m)<br>予想経過: <b>{t}</b>',
    'cpTable.segment': '区間',
    'cpTable.arrival': '到着',
    'cpTable.temp': '気温',
    'cpTable.cum': '累積{v}',
    'cpTable.feels': '体感{v}&deg;',
    'cpTable.cutoff': '関門の余裕',

    'cutoff.title': '関門までの余裕',
    'cutoff.over': '予測のペースでは、{n}か所の関門に間に合いません({list})。',
    'cutoff.tight': '余裕が{m}分未満の関門が{n}か所あります。',
    'cutoff.allOk': 'すべての関門に{m}分以上の余裕があります。',
    'cutoff.tightest': '余裕が一番少ない関門',
    'cutoff.count': '関門',
    'cutoff.official': '関門 {c}',
    'cutoff.effective': '実質 {c}',
    'cutoff.nextDay': '翌日',
    'cutoff.daysLater': '{n}日後',
    'cutoff.dayClock': '{d}{clock}',
    'cutoff.trapLabel': 'ひっかけ関門',
    'cutoff.trapTitle': '{by}の関門({c})が、手前の関門より厳しい',
    'cutoff.trapBody': '{list}に関門ぎりぎりで着くと、予測のペースでは{by}に間に合いません。実質の関門:',
    'cutoff.trapLine': '{name} {e}(関門 {c} より{m}分早い)',
    'cutoff.footnote': '余裕 = 実質の関門 &minus; 予測の到着時刻。実質の関門は、その先の関門にも予測のペースで間に合う、一番遅い到着時刻です。到着時刻で比べています(出発時刻が関門の大会では、滞在時間の分だけ余裕が減ります)。',

    'grad.steep_downhill': '急な下り',
    'grad.moderate_downhill': '中程度の下り',
    'grad.gentle_downhill': '緩い下り',
    'grad.flat': '平地',
    'grad.gentle_uphill': '緩い登り',
    'grad.moderate_uphill': '中程度の登り',
    'grad.steep_uphill': '急な登り',
    'grad.very_steep_uphill': '非常に急な登り',

    'target.title': '目標タイムプラン',
    'target.notNeeded': '目標({t})は予測より遅いため、上の予測どおりのペースで達成できます。',
    'target.feasible': '目標 {t} は、地形ごとのペース配分で達成可能な見込みです。',
    'target.infeasible': '目標 {t} には届かない見込みです。現実的な上限まで速めても約{best}が目安です。',
    'target.terrain': '地形',
    'target.predTime': '予測での所要時間',
    'target.paceUp': '必要なペースアップ',
    'target.cap': '(上限)',
    'target.footnote': '平地・緩斜面ほど伸びしろが大きく、急な登り・下りほど小さいという仮定に基づく試算です。',
    'target.schedule': '目標タイムでの通過予定',

    'nut.title': '補給プラン',
    'nut.water': '水分',
    'nut.gels': 'ジェル',
    'nut.gelsN': '{v}個',
    'nut.cpAid': 'CP補給',
    'nut.cpAidN': '{v}ヶ所',
    'nut.segment': '区間',
    'nut.kcal': 'カロリー',
    'nut.segSub': '{min}分・体感{t}&deg;C',
    'nut.kcalSub': 'CP{aid}&rarr;差引{net}',
    'nut.method': '計算方法',
    'nut.footnote': '水分: 区間平均の体感温度に応じて500&ndash;900mL/時。推定発汗量は{sweat}L(全量を飲む必要はありません)。<br>'
      + 'ジェル: 体重{bw}kg&times;3.5kcal/時を目標に、CPごとにバナナ2本(約180kcal)を食べる想定で差し引き、不足分をジェル1個=100kcalで補う本数。スタート直後は体内のグリコーゲンで最大1.5時間分をまかなう想定。<br>'
      + '推定消費カロリーは{kcal}kcal。電解質は別途計画してください。個人差が大きいので目安としてご利用ください。',
    'nut.note.glycogen_covers': 'スタート前の朝食で体内グリコーゲン充填済みのため補給食なしでも可(体内貯蔵分で足りる)',
    'nut.note.glycogen_then_gels': '体内グリコーゲン貯蔵を使い切った後は、CPがないため携行ジェル等で補給してください',
    'nut.note.cp_bananas_cover': '{cp}のバナナ2本で充足',

    'mind.title': '注意ポイント',
    'mind.none': '特になし',
    'mind.steepLabel': '急登区間',
    'mind.steepTitle': '{from} &rarr; {to}(平均勾配 約{grade}%)',
    'mind.steepBody': '{km}kmで{gain}m登る、最も傾斜がきつい区間。余裕があっても突っ込みすぎない。',
    'mind.longLabel': '最長区間',
    'mind.longTitle': '{from} &rarr; {to}({km}km・予想{t})',
    'mind.longBody': '所要時間が最も長い区間。携行する水とジェルを多めに。',
    'mind.hotLabel': '暑さのピーク',
    'mind.hotTitle': '{from} &rarr; {to}(体感{t}&deg;C)',
    'mind.hotBody': '最も体感温度が高い区間。ペースを抑え、給水・給食を切らさない。',

    // ----- マイレース -----
    'my.title': 'マイレース',
    'my.note': '自分が走った過去レースのGPX(ウォッチの記録など、時刻付き)を登録すると、あなた専用のペースモデルが自動で作られ、予測に使われます。',
    'my.add': '+ レースを追加',
    'my.statusCustom': 'マイペースモデルで予測中({n}レース)',
    'my.statusStandard': '標準モデルで予測中。レースを追加すると自分専用になります。',
    'my.legacy': '現在のモデルは以前の方式で作成されています({list})。レースを追加するとモデルはここに登録したGPXだけで作り直されるので、残したいレースも再登録してください。',
    'my.listSep': '、',
    'my.empty': 'まだレースがありません。',
    'my.race': 'レース',
    'my.distGain': '距離/D+',
    'my.temp': '気温',
    'my.adding': '{name} を追加中(気温取得・モデル更新)...',
    'my.added': '{name} を追加し、モデルを更新しました',
    'my.confirmDelete': '「{name}」を削除して、残りのレースでモデルを作り直しますか?',
    'my.deleted': '{name} を削除しました',

    // ----- 振り返り -----
    'review.title': '振り返り',
    'review.note': '予測したレースが自動で保存されて並びます。レース後に実際の記録GPXを入れると、CPごとに予測との差が見られます。',
    'review.empty': 'まだ保存した予測がありません。',
    'review.state': '状態',
    'review.savedOn': '{date} 保存',
    'review.compared': '比較済み',
    'review.waiting': '実績待ち',
    'review.confirmDelete': '「{name}」の保存済み予測を削除しますか?',
    'review.back': '&larr; 一覧に戻る',
    'review.summary': '{km}km ・ D+{gain}m ・ スタート {start}',
    'review.instruction': 'レース後に、実際に走った記録のGPX(時刻付き)を選択すると、予測との差がCPごとに表示されます。',
    'review.dzTitle': '実績GPXを選択',
    'review.dzSub': 'ウォッチの記録など、時刻付きのGPX',
    'review.comparing': '比較中...',
    'review.predicted': '予測',
    'review.goal': '目標',
    'review.actual': '実績',
    'review.diffFromPred': '予測との差',
    'review.cpDiffs': 'チェックポイントごとの差',
    'review.diff': '差',
    'review.segment': '区間',
    'review.diffFromGoal': '目標との差',
    'review.predCell': '予測{v}',
    'review.footnote': '差 = 実績 &minus; 予測(+は予測より遅い)。区間 = 前のCPからその区間だけの差。GPXでCPを通過した地点が見つからない場合は「&mdash;」になります。',
  },

  en: {
    'tab.myRaces': 'My Races',
    'tab.predict': 'Predict',
    'tab.review': 'Review',
    'common.error': 'Error: {v}',
    'common.delete': 'Delete',
    'diff.min': '{v} min',

    'course.title': '1. Course GPX',
    'course.note': 'Choose the official course GPX for the race. Named waypoints are detected as checkpoints automatically.',
    'course.dzTitle': 'Choose a GPX file',
    'course.dzSub': '.gpx files only',
    'course.dzPicked': '{name} (tap to choose another file)',
    'course.loading': 'Loading...',
    'link.loading': 'Loading the {name} course...',
    'link.loaded': 'Loaded the {name} course, start time and {n} cutoffs. Check them under checkpoint settings.',
    'link.failed': 'Could not load the course ({v}). Download the GPX and choose it here.',
    'stat.distance': 'Distance',

    'setup.title': '2. Race conditions',
    'setup.raceStart': 'Start date and time (local)',
    'setup.bodyweight': 'Body weight (kg)',
    'setup.manualTemp': 'Average temperature (&deg;C)',
    'setup.manualHum': 'Average humidity (%)',
    'setup.cpWarn': 'No checkpoints were found in the GPX, so they are evenly spaced for now. Check and fix them under "Checkpoints".',
    'setup.checkpoints': 'Checkpoints',
    'setup.cpName': 'Name',
    'setup.cpDist': 'Distance (km)',
    'setup.cpCutoff': 'Cutoff',
    'setup.cpDistCutoff': 'Distance (km)/Cutoff',
    'setup.cpCutoffPlaceholder': 'cutoff --:--',
    'setup.cutoffNote': 'Cutoffs (optional): enter each checkpoint\'s cutoff like 14:30 to see your margin. Cutoffs after midnight roll over to the next day automatically. For cutoffs two or more days later, add 24 per day (30:00 = day 2, 06:00).',
    'setup.addCp': '+ Add checkpoint',
    'setup.dwell': 'Time at each checkpoint (min)',
    'setup.target': 'Target time (optional)<span class="pro-badge">PRO</span>',
    'setup.targetNote': 'Enter a target faster than the prediction to also see a pacing plan for climbs, descents and flats.',
    'setup.hours': 'Hours',
    'setup.minutes': 'Minutes',
    'setup.run': 'Predict',
    'setup.running': 'Calculating...',
    'weather.needStart': 'Enter the start date and time',
    'weather.fetching': 'Getting temperature data...',
    'weather.forecast': 'weather forecast',
    'weather.normals': 'climate normals',
    'weather.ok': 'Temperature: {src} (average about {avg}&deg;C)',
    'weather.fail': 'Could not get temperature data ({e}). Please enter the temperature.',

    'report.finishLabel': 'Predicted finish time',
    'report.finishSub': 'Finish around {finish} &middot; Start {start}',
    'report.highest': 'High point',
    'report.heat': 'Heat effect {v}% (before correction {base})',
    'report.customModel': 'Predicted with your personal pace model.',
    'report.standardModel': 'Predicted with the standard model. Add your past races under <a href="#" id="toMyRacesLink">My Races</a> to get a prediction based on your own running.',
    'report.cpTitle': 'Checkpoint schedule',
    'report.chartTitle': 'Elevation and schedule',
    'report.pdf': 'Export PDF',
    'report.saved': 'This prediction was saved automatically. After the race, compare it with your actual run under "Review".',
    'report.saveFail': 'Could not save automatically: {e}',
    'report.tooltip': '<b>{km} km</b> (elevation {e}m)<br>Predicted elapsed: <b>{t}</b>',
    'cpTable.segment': 'Segment',
    'cpTable.arrival': 'Arrival',
    'cpTable.temp': 'Temp',
    'cpTable.cum': 'total {v}',
    'cpTable.feels': 'feels {v}&deg;',
    'cpTable.cutoff': 'Cutoff margin',

    'cutoff.title': 'Cutoff margins',
    'cutoff.over': 'At the predicted pace you miss {n} cutoff(s) ({list}).',
    'cutoff.tight': '{n} cutoff(s) with less than {m} min to spare.',
    'cutoff.allOk': 'At least {m} min to spare at every cutoff.',
    'cutoff.tightest': 'Tightest cutoff',
    'cutoff.count': 'Cutoffs',
    'cutoff.official': 'cutoff {c}',
    'cutoff.effective': 'really {c}',
    'cutoff.nextDay': 'next day ',
    'cutoff.daysLater': '+{n} days ',
    'cutoff.dayClock': '{d}{clock}',
    'cutoff.trapLabel': 'Trap cutoff',
    'cutoff.trapTitle': 'The cutoff at {by} ({c}) is tighter than the ones before it',
    'cutoff.trapBody': 'Arrive at {list} right at the cutoff and, at your predicted pace, you miss {by}. Effective cutoffs:',
    'cutoff.trapLine': '{name} {e} ({m} min before its cutoff {c})',
    'cutoff.footnote': 'Margin = effective cutoff &minus; predicted arrival. The effective cutoff is the latest arrival that still makes every later cutoff at your predicted pace. Compared with arrival time (where a race times cutoffs on departure, your time at the checkpoint comes off the margin).',

    'grad.steep_downhill': 'Steep descent',
    'grad.moderate_downhill': 'Moderate descent',
    'grad.gentle_downhill': 'Gentle descent',
    'grad.flat': 'Flat',
    'grad.gentle_uphill': 'Gentle climb',
    'grad.moderate_uphill': 'Moderate climb',
    'grad.steep_uphill': 'Steep climb',
    'grad.very_steep_uphill': 'Very steep climb',

    'target.title': 'Target time plan',
    'target.notNeeded': 'Your target ({t}) is slower than the prediction, so the pace above already gets you there.',
    'target.feasible': 'Target {t} looks achievable by pacing each type of terrain.',
    'target.infeasible': 'Target {t} looks out of reach. Even at a realistic maximum, about {best} is the best estimate.',
    'target.terrain': 'Terrain',
    'target.predTime': 'Time in prediction',
    'target.paceUp': 'Pace-up needed',
    'target.cap': '(max)',
    'target.footnote': 'Estimate assumes flats and gentle slopes have the most room to speed up, and steep climbs and descents the least.',
    'target.schedule': 'Schedule at target time',

    'nut.title': 'Nutrition plan',
    'nut.water': 'Water',
    'nut.gels': 'Gels',
    'nut.gelsN': '{v}',
    'nut.cpAid': 'Aid stops',
    'nut.cpAidN': '{v}',
    'nut.segment': 'Segment',
    'nut.kcal': 'Calories',
    'nut.segSub': '{min} min &middot; feels {t}&deg;C',
    'nut.kcalSub': 'CP {aid} &rarr; net {net}',
    'nut.method': 'How this is calculated',
    'nut.footnote': 'Water: 500&ndash;900 mL per hour depending on the average feels-like temperature of each segment. Estimated sweat loss is {sweat} L (you do not need to drink all of it).<br>'
      + 'Gels: target of {bw} kg body weight &times; 3.5 kcal per hour, minus 2 bananas (about 180 kcal) eaten at each checkpoint; the rest is covered by gels at 100 kcal each. Right after the start, stored glycogen is assumed to cover up to 1.5 hours.<br>'
      + 'Estimated energy use is {kcal} kcal. Plan electrolytes separately. Needs vary a lot between people, so use this as a guide.',
    'nut.note.glycogen_covers': 'No food needed: glycogen from your pre-race breakfast covers this segment',
    'nut.note.glycogen_then_gels': 'Once your glycogen stores run out there is no checkpoint, so carry gels for this segment',
    'nut.note.cp_bananas_cover': 'Covered by 2 bananas at {cp}',

    'mind.title': 'Watch out for',
    'mind.none': 'Nothing in particular',
    'mind.steepLabel': 'Steepest climb',
    'mind.steepTitle': '{from} &rarr; {to} (average grade about {grade}%)',
    'mind.steepBody': '{gain} m of climbing in {km} km, the steepest part of the course. Do not push too hard even if you feel good.',
    'mind.longLabel': 'Longest segment',
    'mind.longTitle': '{from} &rarr; {to} ({km} km &middot; about {t})',
    'mind.longBody': 'The segment that takes the longest. Carry extra water and gels.',
    'mind.hotLabel': 'Hottest segment',
    'mind.hotTitle': '{from} &rarr; {to} (feels {t}&deg;C)',
    'mind.hotBody': 'The highest feels-like temperature. Ease off the pace and keep drinking and eating.',

    'my.title': 'My Races',
    'my.note': 'Add GPX files of races you have run (with timestamps, such as watch recordings). A personal pace model is built from them automatically and used for predictions.',
    'my.add': '+ Add race',
    'my.statusCustom': 'Predicting with your personal pace model ({n} races)',
    'my.statusStandard': 'Predicting with the standard model. Add races to make it your own.',
    'my.legacy': 'Your current model was built the old way ({list}). Adding a race rebuilds the model from only the GPX files listed here, so add again any race you want to keep.',
    'my.listSep': ', ',
    'my.empty': 'No races yet.',
    'my.race': 'Race',
    'my.distGain': 'Dist/D+',
    'my.temp': 'Temp',
    'my.adding': 'Adding {name} (getting temperature, updating model)...',
    'my.added': 'Added {name} and updated the model',
    'my.confirmDelete': 'Delete "{name}" and rebuild the model from the remaining races?',
    'my.deleted': 'Deleted {name}',

    'review.title': 'Review',
    'review.note': 'Every prediction is saved here automatically. After the race, add the GPX of your actual run to see the difference at each checkpoint.',
    'review.empty': 'No saved predictions yet.',
    'review.state': 'Status',
    'review.savedOn': 'Saved {date}',
    'review.compared': 'Compared',
    'review.waiting': 'Awaiting result',
    'review.confirmDelete': 'Delete the saved prediction for "{name}"?',
    'review.back': '&larr; Back to list',
    'review.summary': '{km}km &middot; D+{gain}m &middot; Start {start}',
    'review.instruction': 'After the race, choose the GPX of your actual run (with timestamps) to see the difference from the prediction at each checkpoint.',
    'review.dzTitle': 'Choose your actual GPX',
    'review.dzSub': 'A GPX with timestamps, such as a watch recording',
    'review.comparing': 'Comparing...',
    'review.predicted': 'Predicted',
    'review.goal': 'Target',
    'review.actual': 'Actual',
    'review.diffFromPred': 'vs prediction',
    'review.cpDiffs': 'Difference at each checkpoint',
    'review.diff': 'Diff',
    'review.segment': 'Segment',
    'review.diffFromGoal': 'vs target',
    'review.predCell': 'pred {v}',
    'review.footnote': 'Diff = actual &minus; predicted (+ means slower than predicted). Segment = the difference for that segment alone, from the previous checkpoint. "&mdash;" means the checkpoint could not be found in the GPX.',
  },
};

// Error messages the server sends in Japanese (HTTPException detail etc.),
// shown in English mode. Exact matches first, then prefixes that are
// followed by technical detail.
const SERVER_MSG_EN = {
  'GPXファイルを選択してください': 'Please choose a GPX file',
  'このGPXにはタイムスタンプがありません。実際に走った記録のGPX(ウォッチのエクスポート等)をアップロードしてください':
    'This GPX has no timestamps. Please upload a GPX of a run you actually did (for example, exported from your watch)',
  'レースが見つかりません': 'Race not found',
  'コースが見つかりません。GPXを再アップロードしてください': 'Course not found. Please upload the GPX again',
  'race_date は YYYY-MM-DD 形式で指定してください': 'race_date must be in YYYY-MM-DD format',
  'race_start_local は YYYY-MM-DDTHH:mm 形式で指定してください': 'race_start_local must be in YYYY-MM-DDTHH:mm format',
  '気温データがありません。先に /api/weather を呼ぶか、manual_avg_temp_c を指定してください': 'No temperature data. Please enter the temperature',
  'CPは少なくともSTART/FINISHの2点が必要です': 'At least START and FINISH are needed',
  '予測結果にCPが含まれていません': 'The prediction has no checkpoints',
  'GPXにトラック(track)データが見つかりません': 'No track data found in the GPX',
  '少なくとも1レース分のGPXが必要です': 'At least one race GPX is needed',
  '有効なペースデータが見つかりませんでした(GPXのタイムスタンプ/標高を確認してください)':
    'No usable pace data found (check the timestamps and elevation in the GPX)',
  '天気データの取得がタイムアウトしました': 'Getting weather data timed out',
  'PowerShellが見つかりません(Windows以外の環境では気温は手動入力してください)': 'Weather lookup is not available here. Please enter the temperature',
  '気候平年値の取得に全て失敗しました': 'Could not get climate normals',
};
const SERVER_MSG_PREFIX_EN = [
  ['GPXの解析に失敗しました: ', 'Could not read the GPX: '],
  ['天気データの取得に失敗しました: ', 'Could not get weather data: '],
  ['cps/cp_dwell_overrides_min のJSONが不正です: ', 'Invalid cps/cp_dwell_overrides_min JSON: '],
  ['関門時刻は 14:30 のように入力してください: ', 'Enter cutoffs like 14:30: '],
];

const LANG_STORAGE_KEY = 'trailRacePlanner.lang';

function detectLang() {
  try {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    if (saved === 'ja' || saved === 'en') return saved;
  } catch (e) {}
  return (navigator.language || '').toLowerCase().startsWith('ja') ? 'ja' : 'en';
}

let LANG = detectLang();

function t(key, params) {
  let s = I18N[LANG][key];
  if (s == null) s = I18N.ja[key];
  if (s == null) return key;
  if (params) s = s.replace(/\{(\w+)\}/g, (m, k) => (params[k] != null ? params[k] : m));
  return s;
}

function serverMsg(detail) {
  const s = String(detail == null ? '' : detail);
  if (LANG === 'ja') return s;
  if (SERVER_MSG_EN[s]) return SERVER_MSG_EN[s];
  for (const [ja, en] of SERVER_MSG_PREFIX_EN) {
    if (s.startsWith(ja)) return en + s.slice(ja.length);
  }
  // "<race name>: GPXにタイムスタンプがありません..." from the pace model builder
  if (s.includes('GPXにタイムスタンプがありません')) {
    return s.replace(/GPXにタイムスタンプがありません.*$/, 'this GPX has no timestamps (a recording of a run you actually did is needed; course GPX files without times cannot be used)');
  }
  return s;
}

// Static text in index.html: data-i18n="key" sets innerHTML.
function applyStaticI18n() {
  document.documentElement.lang = LANG;
  document.querySelectorAll('[data-i18n]').forEach((e) => { e.innerHTML = t(e.dataset.i18n); });
  document.querySelectorAll('.lang-btn').forEach((b) => b.classList.toggle('active', b.dataset.lang === LANG));
}

function setLang(lang) {
  if (lang === LANG || !I18N[lang]) return;
  LANG = lang;
  try { localStorage.setItem(LANG_STORAGE_KEY, lang); } catch (e) {}
  applyStaticI18n();
  if (typeof onLangChange === 'function') onLangChange();
}
