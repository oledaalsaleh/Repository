"""Turkish date parsing ("13 Ekim 2026", "29 Eylül Salı", "3 EKİM") with year inference."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone, tzinfo

from .config import TIMEZONE


def _tz() -> tzinfo:
    """Europe/Istanbul; Turkey is permanently UTC+3 since 2016, so fall back safely on Windows."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(TIMEZONE)
    except Exception:
        return timezone(timedelta(hours=3), "TRT")


TZ = _tz()

_FOLD = str.maketrans("çğıöşüâîûİIÇĞÖŞÜ", "cgiosuaiuiicgosu")

MONTHS = {
    "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6,
    "temmuz": 7, "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
}

_DATE_RE = re.compile(
    r"(?<!\d)(\d{1,2})[\s\-\.]+(" + "|".join(MONTHS) + r")(?:[\s\-\.]+(\d{4}))?",
)


def fold(text: str) -> str:
    """Turkish-aware ASCII folding + lowercase ('Eylül' → 'eylul', 'EKİM' → 'ekim')."""
    return text.translate(_FOLD).lower()


def now_tr() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def today_tr() -> date:
    return now_tr().date()


def parse_tr_date(text: str, ref: date | None = None) -> date | None:
    """Return the first Turkish date found in `text`.

    When the year is missing (BİM posters: "29 Eylül Salı") the year closest to `ref`
    is chosen, so a "2 Ocak" label scraped on 28 Aralık resolves to next year.
    """
    if not text:
        return None
    m = _DATE_RE.search(fold(text))
    if not m:
        return None
    day, month = int(m.group(1)), MONTHS[m.group(2)]
    ref = ref or today_tr()
    try:
        if m.group(3):
            return date(int(m.group(3)), month, day)
        candidates = [date(ref.year + dy, month, day) for dy in (-1, 0, 1)]
    except ValueError:
        return None
    return min(candidates, key=lambda d: abs((d - ref).days))


def parse_tr_dates(text: str, ref: date | None = None) -> list[date]:
    """All dates in `text`, e.g. a range '28 Eylül - 4 Ekim 2026' → [2026-09-28, 2026-10-04]."""
    folded = fold(text or "")
    # "02-05 ekim" → "02 ekim - 05 ekim"
    folded = re.sub(r"(?<!\d)(\d{1,2})\s*[-–]\s*(\d{1,2})\s+(" + "|".join(MONTHS) + r")",
                    r"\1 \3 - \2 \3", folded)
    out: list[date] = []
    year_hint = next((m.group(3) for m in _DATE_RE.finditer(folded) if m.group(3)), None)
    for m in _DATE_RE.finditer(folded):
        chunk = f"{m.group(1)} {m.group(2)} {m.group(3) or year_hint or ''}"
        d = parse_tr_date(chunk, ref)
        if d:
            out.append(d)
    return out


def end_of_validity(start: date, days: int) -> date:
    return start + timedelta(days=days - 1)
