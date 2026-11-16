"""Translations (English / Japanese) and locale-aware formatting.

UI text is written in English in the code and wrapped with tr().
tr() returns the Japanese text from JA when the language is set to "ja".
"""
from __future__ import annotations

from datetime import date

LANGUAGES = {"en": "English", "ja": "日本語"}
_state = {"lang": "en"}


def set_language(code: str) -> None:
    _state["lang"] = code if code in LANGUAGES else "en"


def lang() -> str:
    return _state["lang"]


def is_ja() -> bool:
    return _state["lang"] == "ja"


def tr(text: str, **kw) -> str:
    s = JA.get(text, text) if is_ja() else text
    return s.format(**kw) if kw else s


def app_title() -> str:
    return tr("Memo Reminder")


# ------------------------------------------------------------------ dates
WEEK_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEK_JA = ["月", "火", "水", "木", "金", "土", "日"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]


def weekday_short(wd: int) -> str:
    return WEEK_JA[wd] if is_ja() else WEEK_EN[wd]


def fmt_month_title(year: int, month: int) -> str:
    return f"{year}年 {month}月" if is_ja() else f"{MONTHS_EN[month - 1]} {year}"


def fmt_date(d: date, force_year: bool = False) -> str:
    """Nov 16 (Mon) style date. Adds the year when it is not this year."""
    show_year = force_year or d.year != date.today().year
    if is_ja():
        s = f"{d.month}月{d.day}日({WEEK_JA[d.weekday()]})"
        return f"{d.year}年" + s if show_year else s
    s = f"{WEEK_EN[d.weekday()]}, {MONTHS_EN[d.month - 1][:3]} {d.day}"
    return s + f", {d.year}" if show_year else s


def relative_day(d: date) -> str | None:
    delta = (d - date.today()).days
    return {0: tr("Today"), 1: tr("Tomorrow"), -1: tr("Yesterday")}.get(delta)


def date_label(d: date) -> str:
    rel = relative_day(d)
    return f"{rel} · {fmt_date(d)}" if rel else fmt_date(d)


def fmt_minutes(m: int) -> str:
    h, r = divmod(int(m), 60)
    if is_ja():
        if h and r:
            return f"{h}時間{r}分"
        return f"{h}時間" if h else f"{r}分"
    if h and r:
        return f"{h} hr {r} min"
    return f"{h} hr" if h else f"{r} min"


def time_range(start: str, end: str) -> str:
    sep = "〜" if is_ja() else "–"
    return f"{start}{sep}{end}" if end else f"{start}{sep}"


# ------------------------------------------------------------------ label sets
def priorities() -> dict:
    return {"high": tr("High"), "normal": tr("Medium"), "low": tr("Low")}


def repeats() -> dict:
    return {"none": tr("Does not repeat"), "daily": tr("Daily"), "weekdays": tr("Weekdays (Mon–Fri)"),
            "weekly": tr("Weekly"), "monthly": tr("Monthly"), "yearly": tr("Yearly")}


def notify_until_labels() -> dict:
    return {"start": tr("Until the event starts"), "end": tr("Until the event ends"),
            "day_end": tr("Until the end of the day")}


def popup_positions() -> dict:
    return {"bottom_right": tr("Bottom right"), "top_right": tr("Top right"),
            "bottom_left": tr("Bottom left"), "top_left": tr("Top left"), "center": tr("Center of screen")}


def themes() -> dict:
    return {"system": tr("Match Windows"), "light": tr("Light"), "dark": tr("Dark")}


def week_starts() -> dict:
    return {"sunday": tr("Sunday"), "monday": tr("Monday")}


def reverse(mapping: dict, label: str, default: str) -> str:
    for k, v in mapping.items():
        if v == label:
            return k
    return default


# ------------------------------------------------------------------ Japanese
JA: dict[str, str] = {}  # filled in below

JA.update({
    # app / general
    "Memo Reminder": "メモリマインダー",
    "Today": "今日", "Tomorrow": "明日", "Yesterday": "昨日",
    "High": "高", "Medium": "中", "Low": "低",
    "Does not repeat": "なし", "Daily": "毎日", "Weekdays (Mon–Fri)": "平日(月〜金)",
    "Weekly": "毎週", "Monthly": "毎月", "Yearly": "毎年",
    "Until the event starts": "予定の開始時刻まで", "Until the event ends": "予定の終了時刻まで",
    "Until the end of the day": "その日の終わりまで",
    "Bottom right": "右下", "Top right": "右上", "Bottom left": "左下", "Top left": "左上",
    "Center of screen": "画面中央",
    "Match Windows": "Windowsの設定に合わせる", "Light": "ライト", "Dark": "ダーク",
    "Sunday": "日曜日", "Monday": "月曜日",
    "All day": "終日",
    # popup
    "Starting soon · in {mins} min": "まもなく開始 · あと {mins} 分",
    "Today's event": "今日の予定", "Tomorrow's event": "明日の予定", "In {n} days": "{n}日後の予定",
    "In {t}": "{t}後", "(untitled)": "(無題)", "Got it": "確認しました",
    "Remind me in {t}": "{t}後に再通知", "Mark done": "完了にする",
    # menus
    "New memo": "新しいメモ", "Export…": "エクスポート…", "Import…": "インポート…",
    "Open data folder": "データフォルダを開く", "Quit": "終了", "File": "ファイル",
    "Selected day": "選択した日", "Upcoming": "今後の予定", "All memos": "すべてのメモ",
    "Show completed memos": "完了したメモも表示", "Go to today": "今日へ移動", "View": "表示",
    "Notifications": "通知", "Settings…": "設定…", "Tools": "ツール", "How to use": "使い方",
    "About": "バージョン情報", "Your data is stored in:": "データの保存場所:", "Help": "ヘルプ",
    "30 minutes": "30分", "1 hour": "1時間", "3 hours": "3時間", "Until I resume": "再開するまで",
    "Pause notifications": "通知を一時停止", "Resume notifications": "通知を再開",
    "Show a test notification": "テスト通知を表示", "Settings": "設定", "Search": "検索", "Open": "開く",
    # main window
    "Double-click a day to add a memo": "日付をダブルクリックでメモを追加",
    "Scroll to change month": "ホイールで月を移動",
    "All": "すべて", "Show completed": "完了も表示", "Edit": "編集", "Done / Not done": "完了 / 未完了",
    "Duplicate": "複製", "Delete": "削除", "Next {n} days": "今後 {n} 日間", "(filtered)": "(検索中)",
    "1 memo": "1 件", "{n} memos": "{n} 件", "Nothing planned": "メモはありません",
    "No memos to show": "表示するメモはありません",
    "Click “+ New memo” or double-click a day in the calendar":
        "「+ 新しいメモ」またはカレンダーの日付をダブルクリックして追加できます",
    "High priority": "優先度 高", "Done": "完了済み", "No reminders": "通知オフ",
    "Reminds at {t}": "当日 {t} に通知", "Reminds from {n} days before at {t}": "{n}日前から {t} に通知",
    "{t} before": "{t}前", "“Starting soon” {t} before": "開始 {t}前にも通知",
    "stays until closed": "閉じるまで表示", "shows for {t}": "{t}表示",
    "{shown}, again after {t}": "{shown} → {t}後に再表示",
    "Select a memo to see its details here": "メモを選択すると、ここに詳細が表示されます",
    "Priority: {p}": "優先度 {p}", "(until {d})": "(〜{d})", "(no notes)": "(内容なし)",
    "Notifications: off": "通知: 無効", "Notifications: paused": "通知: 一時停止中",
    "Notifications: paused until {t}": "通知: 一時停止中 ({t} まで)", "Notifications: on": "通知: 有効",
    "{n} on screen": "表示中 {n} 件", "Next reminder {t}": "次の再表示 {t}", "Today: {n}": "今日の予定 {n} 件",
    "Test: weekly team meeting": "テスト通知: 定例会議",
    "This is a test notification.\nRoom 3F-B · bring the printed handouts":
        "これはテスト表示です。\n会議室 3F-B · 資料を印刷して持参",
    "(copy)": "(コピー)", "Delete “{title}”?": "「{title}」を削除しますか？",
    "(All repeats of this memo will be deleted.)": "(繰り返しのすべての予定が削除されます)",
    "Delete memo": "削除の確認",
    "Dismissed reminders for this memo will show again.": "止めていた通知を元に戻しました。",
    "Bring back dismissed reminders": "止めた通知を元に戻す",
    "Could not change the auto-start setting.": "自動起動の設定に失敗しました。",
    "Export complete.": "エクスポートしました。", "Could not import the file.": "読み込みに失敗しました。",
    "Imported {n} memos.": "{n} 件のメモを読み込みました。",
    "Still running in the tray. Right-click the tray icon to quit.":
        "タスクトレイで動作を続けます。終了はトレイアイコンの右クリックメニューから。",
    "Reminders will stop while the app is closed. Quit anyway?":
        "終了すると通知が表示されなくなります。終了しますか？",
    # settings
    "Reminders": "通知タイミング", "Enable notifications": "通知を有効にする",
    "Start reminding at": "通知開始時刻",
    "Reminders begin at this time on the day": "予定日のこの時刻から通知を始める",
    "Days in advance": "何日前から通知",
    "0 = on the day only; 1 = also the day before": "0 = 当日のみ。1 なら前日の開始時刻からも通知",
    "Show for (min)": "1回の表示時間(分)",
    "0 = stay on screen until I close it": "0 = 手動で閉じるまで表示し続ける",
    "Repeat every (min)": "再表示までの間隔(分)",
    "Gap after it hides before it shows again": "自動で消えてから再び表示するまで",
    "Default snooze (min)": "スヌーズ既定(分)", "Snooze options (min)": "スヌーズの選択肢(分)",
    "Comma-separated, e.g. 5,10,30,60": "カンマ区切り 例: 5,10,30,60",
    "Also alert me shortly before the start time": "開始時刻の直前にも通知する",
    "“Starting soon” (min)": "直前通知(分前)", "Only for memos with a start time": "時刻指定のある予定のみ",
    "Keep reminding": "通知を続ける期限",
    "For timed memos (all-day memos: until midnight)": "時刻指定のある予定 (終日の予定はその日の終わりまで)",
    "Check every (sec)": "通知チェック周期(秒)",
    "Popup & sound": "ポップアップ・音", "Position": "表示位置", "Width (px)": "幅(px)", "Opacity": "不透明度",
    "Flash the border when it appears": "表示時に枠を点滅させる",
    "Also send a Windows notification (Action Center)": "Windows標準の通知(アクションセンター)にも出す",
    "Requires winotify (included in the .exe)": "※ 利用するには winotify が必要です (exe版には同梱)",
    "Play a sound": "通知音を鳴らす", "System sound": "システムサウンド", "Browse…": "参照…",
    "WAV file": "WAVファイル", "Used instead of the system sound": "指定するとこちらを優先",
    "Test sound": "音のテスト", "Appearance & behavior": "外観・動作", "Language": "言語 (Language)",
    "Theme": "テーマ", "(Automatic)": "(自動)", "Font": "フォント", "Text size": "文字サイズ",
    "Week starts on": "週の始まり", "“Upcoming” shows (days)": "「今後の予定」の日数",
    "Closing the window keeps the app running in the tray": "×ボタンで終了せずタスクトレイに格納する",
    "Start hidden (tray only)": "起動時にウィンドウを表示しない",
    "Start automatically with Windows": "Windows起動時に自動で起動する",
    "Restore defaults": "初期値に戻す", "Cancel": "キャンセル", "Please check your input": "入力エラー",
    "One of the numbers is not valid.": "数値の入力が正しくありません。",
    "Reset every setting to its default? (Nothing is saved until you press OK.)":
        "すべての設定を初期値に戻しますか？（保存は OK を押したとき）",
    "All files": "すべてのファイル",
    # widgets
    "+{n} more": "他 {n} 件", "Pick…": "カレンダー", "Clear": "クリア", "Choose a date": "日付を選択",
    # editor
    "Default ({value})": "既定値 ({value})", "Edit memo": "メモの編集", "Details": "基本",
    "Title": "タイトル", "Date": "日付", "Time": "時間", "All day / no time": "終日 / 時間指定なし",
    "Start": "開始", "End": "終了", "Has end time": "終了時刻あり", "Priority": "優先度",
    "Repeat": "繰り返し", "Until": "終了日", "Notes": "内容",
    "Notify me about this memo": "このメモの通知を有効にする",
    "Untick “Default” to use a different value for this memo only.":
        "「既定値」のチェックを外すと、このメモだけ個別の値を設定できます。",
    "Off": "なし", "Same day": "当日", "{n} days before": "{n}日前", "Play sound": "鳴らす", "Silent": "鳴らさない",
    "Reminders begin at this time": "その日のこの時刻から通知", "0 = on the day only": "0 = 当日のみ",
    "0 = until I close it": "0 = 閉じるまで表示", "Gap before it shows again": "消えてから再表示まで",
    "0 = no starting-soon alert": "0 = 直前通知なし", "Sound": "通知音", "Save  (Ctrl+Enter)": "保存  (Ctrl+Enter)",
    "Please enter a title.": "タイトルを入力してください。",
    "Please enter the date as YYYY-MM-DD.": "日付は YYYY-MM-DD 形式で入力してください。",
    "The repeat end date is not valid.": "繰り返しの終了日が正しくありません。",
    "The time is not valid.": "時刻が正しくありません。",
    "One of the notification values is not valid.": "通知設定の値が正しくありません。",
})

JA["__help__"] = """■ メモの追加
  カレンダーの日付をダブルクリック、または「+ 新しいメモ」(Ctrl+N)。

■ 通知の流れ (初期設定)
  予定日の 7:00 から画面右下に通知が表示されます。
  5分表示 → 自動で消える → 5分後に再表示… を、止めるまで繰り返します。
  時刻指定の予定は、開始15分前に「まもなく開始」通知も出ます。

■ 通知のボタン
  確認しました / × … その日の通知を止める
  10分後 / ▾ … スヌーズ (指定時間後に再表示)
  完了にする … 予定を完了にして通知を止める
  タイトルをクリック … メモを開く

■ キーボード
  Ctrl+N 新規 · Ctrl+F 検索 · Ctrl+T 今日 · ↑↓ 選択
  Enter 編集 · Space 完了切替 · Delete 削除

■ 設定
  「設定」で全体の既定値・言語・テーマ(ライト/ダーク)を変更できます。
  メモごとの「通知」タブで個別に上書きもできます。

■ 常駐
  ×ボタンで閉じてもタスクトレイで動き続け、通知を出します。
  完全に終了するには ファイル → 終了 (またはトレイメニュー)。"""
