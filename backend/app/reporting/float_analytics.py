"""
Schedule float analytics for report output only.

Does NOT affect acceptability, evidence logic, or Clause 31 decision.
Read-only descriptive analytics from programme_summary (XER-derived).
Primavera stores total float in hours; we convert to working days for display.
"""

from typing import Dict, Any, List, Optional

WORKING_HOURS_PER_DAY = 8


# Histogram bucket boundaries (working days): <0, 0-10, 10-20, 20-40, 40-80, 80+
BUCKET_LABELS = ["< 0", "0–10", "10–20", "20–40", "40–80", "80+"]


def compute_float_profile(programme_summary: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Compute float profile from programme_summary.activities (non-completed; exclude missing float).
    Uses working days as stored in XER. Returns None if no activities or no valid float data.
    """
    activities = programme_summary.get("activities") or []
    if not activities:
        return None

    # Collect (float, activity_dict) for activities with float present (programme_summary uses 0 for missing in validator)
    floats_and_acts: List[tuple] = []
    for act in activities:
        if not isinstance(act, dict):
            continue
        f = act.get("float")
        if f is None:
            continue
        try:
            f_val = float(f)
        except (TypeError, ValueError):
            continue
        floats_and_acts.append((f_val, act))

    if not floats_and_acts:
        return None

    total_activities_count = len(floats_and_acts)
    count_float_lt_40 = sum(1 for f, _ in floats_and_acts if f < 40)
    count_float_ge_40 = total_activities_count - count_float_lt_40
    percentage_lt_40 = round(100.0 * count_float_lt_40 / total_activities_count, 1) if total_activities_count else 0
    percentage_ge_40 = round(100.0 * count_float_ge_40 / total_activities_count, 1) if total_activities_count else 0

    # Histogram buckets: < 0, 0–10, 10–20, 20–40, 40–80, 80+
    def bucket(f_val: float) -> int:
        if f_val < 0:
            return 0
        if f_val < 10:
            return 1
        if f_val < 20:
            return 2
        if f_val < 40:
            return 3
        if f_val < 80:
            return 4
        return 5

    histogram = [0] * 6
    for f_val, _ in floats_and_acts:
        histogram[bucket(f_val)] += 1

    return {
        "total_activities_count": total_activities_count,
        "count_float_lt_40": count_float_lt_40,
        "count_float_ge_40": count_float_ge_40,
        "percentage_lt_40": percentage_lt_40,
        "percentage_ge_40": percentage_ge_40,
        "histogram_buckets": BUCKET_LABELS,
        "histogram_counts": histogram,
    }


def build_activity_float_details(
    programme_summary: Dict[str, Any],
    max_rows: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Build sorted list of { activity_id, activity_name, total_float_days, critical } for appendix.
    Sort ascending by total float. Truncate to max_rows.
    """
    activities = programme_summary.get("activities") or []
    rows: List[Dict[str, Any]] = []
    for act in activities:
        if not isinstance(act, dict):
            continue
        f = act.get("float")
        if f is None:
            continue
        try:
            f_val = float(f)
        except (TypeError, ValueError):
            continue
        rows.append({
            "activity_id": str(act.get("id", "")),
            "activity_name": str(act.get("name", "")),
            "total_float_days": round(f_val, 1),
            "critical": act.get("critical", False) or f_val <= 0,
        })
    rows.sort(key=lambda r: r["total_float_days"])
    return rows[:max_rows]


def activity_float_details_truncated(programme_summary: Dict[str, Any], max_rows: int = 1000) -> bool:
    """True if there are more than max_rows activities with float (table was truncated)."""
    activities = programme_summary.get("activities") or []
    count = 0
    for act in activities:
        if not isinstance(act, dict):
            continue
        if act.get("float") is None:
            continue
        count += 1
        if count > max_rows:
            return True
    return False


def build_appendix_float_trimmed(programme_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build appendix list: critical activities (0 float days) + top 5 highest float only.
    Raw float from XER is in hours; convert to days (÷ WORKING_HOURS_PER_DAY), round to 1 decimal.
    Presentation only; no full dump. Each row: activity_name, total_float_days, critical.
    """
    activities = programme_summary.get("activities") or []
    rows: List[Dict[str, Any]] = []
    for act in activities:
        if not isinstance(act, dict):
            continue
        f = act.get("float")
        if f is None:
            continue
        try:
            raw_hours = float(f)
        except (TypeError, ValueError):
            continue
        float_days = round(raw_hours / WORKING_HOURS_PER_DAY, 1)
        rows.append({
            "activity_name": str(act.get("name", "")),
            "total_float_days": float_days,
            "critical": act.get("critical", False) or float_days <= 0,
        })
    # Critical (0 float days) first, then top 5 by float descending
    critical_only = [r for r in rows if r["total_float_days"] == 0]
    non_critical = [r for r in rows if r["total_float_days"] > 0]
    non_critical.sort(key=lambda r: -r["total_float_days"])
    top5 = non_critical[:5]
    result = critical_only + top5
    return result
