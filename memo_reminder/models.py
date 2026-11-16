"""Memo data model and storage."""
from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .config import data_dir
from .i18n import time_range, tr


def parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def parse_time(s: str) -> time | None:
    s = (s or "").strip()
    if not s:
        return None
    h, m = s.split(":")
    return time(int(h), int(m))


def fmt_time(t: time | None) -> str:
    return t.strftime("%H:%M") if t else ""


@dataclass
class Memo:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    content: str = ""
    date: str = ""                  # YYYY-MM-DD (繰り返しの場合は開始日)
    all_day: bool = True
    start_time: str = ""            # HH:MM
    end_time: str = ""              # HH:MM
    priority: str = "normal"        # high / normal / low
    repeat: str = "none"            # none / daily / weekdays / weekly / monthly / yearly
    repeat_until: str = ""          # 繰り返しの終了日 (空 = 無期限)
    notify: bool = True
    # 以下 None = 設定画面の既定値を使う
    notify_time: str | None = None
    days_before: int | None = None
    display_minutes: int | None = None
    interval_minutes: int | None = None
    pre_alert_minutes: int | None = None   # 0 = 直前通知なし
    sound: bool | None = None
    # 状態
    done_dates: list = field(default_factory=list)     # 完了済みの日付 (YYYY-MM-DD)
    acknowledged: list = field(default_factory=list)   # 通知を手動で止めたキー
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    # ---------- 生成・変換 ----------
    @classmethod
    def from_dict(cls, d: dict) -> "Memo":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    def to_dict(self) -> dict:
        return asdict(self)

    def copy(self) -> "Memo":
        return Memo.from_dict(json.loads(json.dumps(self.to_dict())))

    # ---------- 日時 ----------
    @property
    def base_date(self) -> date:
        return parse_date(self.date)

    @property
    def start(self) -> time | None:
        return None if self.all_day else parse_time(self.start_time)

    @property
    def end(self) -> time | None:
        return None if self.all_day else parse_time(self.end_time)

    def time_label(self) -> str:
        if self.all_day or not self.start_time:
            return tr("All day")
        return time_range(self.start_time, self.end_time)

    def occurs_on(self, d: date) -> bool:
        base = self.base_date
        if d < base:
            return False
        if self.repeat_until:
            try:
                if d > parse_date(self.repeat_until):
                    return False
            except ValueError:
                pass
        r = self.repeat
        if r == "none":
            return d == base
        if r == "daily":
            return True
        if r == "weekdays":
            return d.weekday() < 5
        if r == "weekly":
            return (d - base).days % 7 == 0
        if r == "monthly":
            return d.day == base.day
        if r == "yearly":
            return (d.month, d.day) == (base.month, base.day)
        return d == base

    def occurrences_between(self, start: date, end: date):
        d = start
        while d <= end:
            if self.occurs_on(d):
                yield d
            d += timedelta(days=1)

    def event_start_dt(self, d: date) -> datetime | None:
        t = self.start
        return datetime.combine(d, t) if t else None

    def event_end_dt(self, d: date) -> datetime:
        """予定の終了日時。時刻未指定ならその日の終わり。"""
        s, e = self.start, self.end
        if e:
            end = datetime.combine(d, e)
            if s and e <= s:
                end += timedelta(days=1)
            return end
        if s:
            return datetime.combine(d, s)
        return datetime.combine(d + timedelta(days=1), time(0, 0))

    def is_done(self, d: date) -> bool:
        return d.isoformat() in self.done_dates

    def set_done(self, d: date, done: bool) -> None:
        k = d.isoformat()
        if done and k not in self.done_dates:
            self.done_dates.append(k)
        elif not done and k in self.done_dates:
            self.done_dates.remove(k)

    # ---------- 設定値の解決 ----------
    def eff(self, settings, name: str):
        v = getattr(self, name)
        if v is None:
            if name == "pre_alert_minutes":
                return settings["pre_alert_minutes"] if settings["pre_alert_enabled"] else 0
            if name == "sound":
                return settings["sound_enabled"]
            return settings[name]
        return v


class MemoStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / "memos.json")
        self.memos: dict[str, Memo] = {}
        self.load()

    def load(self) -> None:
        self.memos = {}
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # 壊れていたらバックアップから復元を試みる
            bak = self.path.with_suffix(".json.bak")
            if not bak.exists():
                return
            raw = json.loads(bak.read_text(encoding="utf-8"))
        for d in raw.get("memos", []):
            m = Memo.from_dict(d)
            self.memos[m.id] = m
        self._prune()

    def _prune(self) -> None:
        """古い通知停止キーを削除してファイル肥大化を防ぐ"""
        limit = (date.today() - timedelta(days=60)).isoformat()
        for m in self.memos.values():
            m.acknowledged = [k for k in m.acknowledged if k.split("|")[1] >= limit]

    def save(self) -> None:
        data = {"version": 1, "memos": [m.to_dict() for m in self.memos.values()]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        if self.path.exists():
            shutil.copy2(self.path, self.path.with_suffix(".json.bak"))
        os.replace(tmp, self.path)

    def add(self, memo: Memo) -> None:
        memo.updated_at = datetime.now().isoformat(timespec="seconds")
        self.memos[memo.id] = memo
        self.save()

    def delete(self, memo_id: str) -> None:
        self.memos.pop(memo_id, None)
        self.save()

    def get(self, memo_id: str) -> Memo | None:
        return self.memos.get(memo_id)

    def all(self) -> list[Memo]:
        return list(self.memos.values())

    def on_date(self, d: date) -> list[Memo]:
        items = [m for m in self.memos.values() if m.occurs_on(d)]
        return sorted(items, key=lambda m: (m.all_day is False, m.start_time or "", m.title))

    def export_to(self, path: str) -> None:
        data = {"version": 1, "memos": [m.to_dict() for m in self.memos.values()]}
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def import_from(self, path: str) -> int:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        n = 0
        for d in raw.get("memos", []):
            m = Memo.from_dict(d)
            parse_date(m.date)  # 不正データなら例外
            self.memos[m.id] = m
            n += 1
        self.save()
        return n
