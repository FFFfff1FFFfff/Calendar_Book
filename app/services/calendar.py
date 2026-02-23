from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone


def compute_available_slots(
    busy_blocks: list[dict],
    target_date: date,
    business_start: time,
    business_end: time,
    slot_duration_minutes: int,
) -> list[dict]:
    """Return available booking slots for *target_date*.

    Args:
        busy_blocks: list of dicts each with ``start_time`` and ``end_time``
                     as Unix timestamps (seconds).
        target_date: the calendar date to compute slots for.
        business_start: daily opening time (e.g. 09:00).
        business_end: daily closing time (e.g. 17:00).
        slot_duration_minutes: length of each slot in minutes.

    Returns:
        list of ``{"start_time": <unix>, "end_time": <unix>}`` dicts
        representing each free slot.
    """
    day_start = datetime.combine(target_date, business_start, tzinfo=timezone.utc)
    day_end = datetime.combine(target_date, business_end, tzinfo=timezone.utc)
    slot_delta = timedelta(minutes=slot_duration_minutes)

    busy_intervals: list[tuple[datetime, datetime]] = []
    for block in busy_blocks:
        b_start = datetime.fromtimestamp(block["start_time"], tz=timezone.utc)
        b_end = datetime.fromtimestamp(block["end_time"], tz=timezone.utc)
        busy_intervals.append((b_start, b_end))

    busy_intervals.sort(key=lambda iv: iv[0])

    slots: list[dict] = []
    cursor = day_start
    while cursor + slot_delta <= day_end:
        slot_end = cursor + slot_delta
        conflict = any(b_start < slot_end and b_end > cursor for b_start, b_end in busy_intervals)
        if not conflict:
            slots.append({
                "start_time": int(cursor.timestamp()),
                "end_time": int(slot_end.timestamp()),
            })
        cursor += slot_delta

    return slots
