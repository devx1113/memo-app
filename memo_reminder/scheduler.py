"""通知スケジューリング (UI に依存しない純粋なロジック)

通知の種類
  day : 当日 (または N 日前) の「通知開始時刻」から表示される通常リマインダー
  pre : 予定開始の N 分前から表示される直前リマインダー

1 回のリマインダーは「表示時間」表示 → 自動で隠れる → 「再表示間隔」後に再表示…を
手動で止める(確認)・完了にする・期限が過ぎる まで繰り返す。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Callable

from .models import Memo, parse_time


@dataclass
class Alert:
    key: str
    memo_id: str
    occ_date: date           # 予定の日付
    kind: str                # "day" / "pre"
    window_start: datetime
    window_end: datetime
    event_start: datetime | None
    days_until: int          # 予定日まで何日あるか


@dataclass
class AlertState:
    next_show: datetime
    handle: object = None    # UI 側のポップアップ
    hide_at: datetime | None = None
    alert: Alert | None = None
    shown_count: int = 0


def make_key(memo_id: str, occ: date, kind: str, notify_day: date) -> str:
    return f"{memo_id}|{occ.isoformat()}|{kind}|{notify_day.isoformat()}"


def compute_alerts(memos: list[Memo], settings, now: datetime) -> list[Alert]:
    """現在時刻において通知すべきリマインダーの一覧を返す"""
    if not settings["notify_enabled"]:
        return []
    today = now.date()
    alerts: list[Alert] = []
    for m in memos:
        if not m.notify:
            continue
        try:
            m.base_date
        except ValueError:
            continue

        # ---- 直前通知 (当日分) ----
        pre_active_today = False
        pre_min = int(m.eff(settings, "pre_alert_minutes") or 0)
        if pre_min > 0 and m.start and m.occurs_on(today) and not m.is_done(today):
            ev_start = m.event_start_dt(today)
            ws = ev_start - timedelta(minutes=pre_min)
            if ws <= now < ev_start:
                key = make_key(m.id, today, "pre", today)
                if key not in m.acknowledged:
                    pre_active_today = True
                    alerts.append(Alert(key, m.id, today, "pre", ws, ev_start, ev_start, 0))

        # ---- 通常通知 (当日 ・ N日前) ----
        days_before = max(0, int(m.eff(settings, "days_before") or 0))
        try:
            nt = parse_time(m.eff(settings, "notify_time")) or time(7, 0)
        except ValueError:
            nt = time(7, 0)
        for k in range(days_before + 1):
            occ = today + timedelta(days=k)
            if not m.occurs_on(occ) or m.is_done(occ):
                continue
            if k == 0 and pre_active_today:
                continue  # 直前通知中は通常通知を出さない
            ws = datetime.combine(today, nt)
            we = datetime.combine(today + timedelta(days=1), time(0, 0))
            if k == 0 and m.start:
                until = settings["notify_until"]
                if until == "start":
                    we = min(we, m.event_start_dt(occ))
                elif until == "end":
                    we = min(we, m.event_end_dt(occ))
            if not (ws <= now < we):
                continue
            key = make_key(m.id, occ, "day", today)
            if key in m.acknowledged:
                continue
            alerts.append(Alert(key, m.id, occ, "day", ws, we, m.event_start_dt(occ), k))
    return alerts


class AlertManager:
    """リマインダーの表示/非表示サイクルを管理する。

    show_cb(alert, memo) -> handle   : ポップアップを表示してハンドルを返す
    hide_cb(handle)                  : ポップアップを閉じる
    save_cb()                        : 状態をファイルへ保存
    """

    def __init__(self, store, settings, show_cb: Callable, hide_cb: Callable, save_cb: Callable):
        self.store = store
        self.settings = settings
        self.show_cb = show_cb
        self.hide_cb = hide_cb
        self.save_cb = save_cb
        self.states: dict[str, AlertState] = {}
        self.paused_until: datetime | None = None

    # ---------- 一時停止 ----------
    def pause(self, minutes: int | None) -> None:
        """minutes=None で無期限停止"""
        self.paused_until = datetime.max if minutes is None else datetime.now() + timedelta(minutes=minutes)
        self._hide_all()

    def resume(self) -> None:
        self.paused_until = None

    def is_paused(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        if self.paused_until and now < self.paused_until:
            return True
        self.paused_until = None
        return False

    # ---------- メインループ ----------
    def tick(self, now: datetime | None = None) -> None:
        now = now or datetime.now()
        if self.is_paused(now):
            return
        alerts = compute_alerts(self.store.all(), self.settings, now)
        active = {a.key: a for a in alerts}

        # 期限切れ・無効になったものを片付ける
        for key in list(self.states):
            if key not in active:
                self._drop(key)

        for key, a in active.items():
            memo = self.store.get(a.memo_id)
            st = self.states.get(key)
            if st is None:
                st = self.states[key] = AlertState(next_show=now, alert=a)
            st.alert = a
            display = int(memo.eff(self.settings, "display_minutes") or 0)
            interval = max(1, int(memo.eff(self.settings, "interval_minutes") or 1))
            if st.handle is None:
                if now >= st.next_show:
                    st.handle = self.show_cb(a, memo)
                    st.shown_count += 1
                    st.hide_at = now + timedelta(minutes=display) if display > 0 else None
            elif st.hide_at is not None and now >= st.hide_at:
                self.hide_cb(st.handle)
                st.handle = None
                st.hide_at = None
                st.next_show = now + timedelta(minutes=interval)

    # ---------- ユーザー操作 ----------
    def acknowledge(self, key: str) -> None:
        """手動で閉じた: このリマインダーを止める"""
        memo_id = key.split("|")[0]
        memo = self.store.get(memo_id)
        if memo and key not in memo.acknowledged:
            memo.acknowledged.append(key)
            self.save_cb()
        self._drop(key)

    def snooze(self, key: str, minutes: int) -> None:
        st = self.states.get(key)
        if not st:
            return
        if st.handle is not None:
            self.hide_cb(st.handle)
            st.handle = None
        st.hide_at = None
        st.next_show = datetime.now() + timedelta(minutes=minutes)

    def complete(self, key: str) -> None:
        memo_id, occ = key.split("|")[:2]
        memo = self.store.get(memo_id)
        if memo:
            memo.set_done(date.fromisoformat(occ), True)
            self.save_cb()
        self.reset_memo(memo_id)

    def reset_memo(self, memo_id: str) -> None:
        """メモが編集・削除されたときに表示中のポップアップを作り直す"""
        for key in list(self.states):
            if key.startswith(memo_id + "|"):
                self._drop(key)

    def next_events(self, now: datetime | None = None) -> datetime | None:
        """表示待ち中で最も早い再表示時刻"""
        times = [s.next_show for s in self.states.values() if s.handle is None]
        return min(times) if times else None

    def visible_count(self) -> int:
        return sum(1 for s in self.states.values() if s.handle is not None)

    # ---------- 内部 ----------
    def _drop(self, key: str) -> None:
        st = self.states.pop(key, None)
        if st and st.handle is not None:
            self.hide_cb(st.handle)

    def _hide_all(self) -> None:
        for key in list(self.states):
            self._drop(key)
