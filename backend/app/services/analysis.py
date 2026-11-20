"""Deterministic variance / forecast / scenario calculations.

All numbers are computed here in plain Python. Narrative text elsewhere may only
describe these results; it never produces numbers.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta


def month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def next_month_key(key: str, steps: int = 1) -> str:
    year, month = int(key[:4]), int(key[5:7])
    index = year * 12 + (month - 1) + steps
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def monthly_totals(rows: list[dict]) -> dict[str, float]:
    """rows: [{date, amount}] -> {'2026-08': total}, sorted, gap months filled with 0."""
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        if row.get("date") is None or row.get("amount") is None:
            continue
        totals[month_key(row["date"])] += float(row["amount"])
    if not totals:
        return {}
    keys = sorted(totals)
    filled, cursor = {}, keys[0]
    while cursor <= keys[-1]:
        filled[cursor] = round(totals.get(cursor, 0.0), 2)
        cursor = next_month_key(cursor)
    return filled


def _group_total(rows, start, end, group_by) -> dict[str, float]:
    result: dict[str, float] = defaultdict(float)
    for row in rows:
        when, amount = row.get("date"), row.get("amount")
        if when is None or amount is None or when < start or when > end:
            continue
        result[str(row.get(group_by) or "Unspecified")] += float(amount)
    return result


def variance_analysis(
    rows: list[dict],
    current: tuple[date, date],
    base: tuple[date, date] | None = None,
    budget: dict[str, float] | None = None,
    group_by: str = "category",
) -> dict:
    """Compare a period against another period, or against a user-provided budget."""
    if group_by not in {"category", "vendor"}:
        raise ValueError("group_by must be 'category' or 'vendor'.")
    if current[0] > current[1]:
        raise ValueError("Current period start must not be after its end.")
    if base is None and not budget:
        raise ValueError("Provide a comparison period or a budget.")

    cur = _group_total(rows, current[0], current[1], group_by)
    if budget:
        reference = {str(k): float(v) for k, v in budget.items()}
        basis = "BUDGET"
    else:
        if base[0] > base[1]:
            raise ValueError("Comparison period start must not be after its end.")
        reference = _group_total(rows, base[0], base[1], group_by)
        basis = "PERIOD"

    lines = []
    for name in sorted(set(cur) | set(reference)):
        actual, ref = round(cur.get(name, 0.0), 2), round(reference.get(name, 0.0), 2)
        diff = round(actual - ref, 2)
        lines.append(
            {
                "group": name,
                "reference": ref,
                "actual": actual,
                "variance": diff,
                "variancePct": round(diff / ref * 100, 1) if ref else None,
            }
        )
    lines.sort(key=lambda r: abs(r["variance"]), reverse=True)
    total_ref = round(sum(r["reference"] for r in lines), 2)
    total_act = round(sum(r["actual"] for r in lines), 2)
    total_var = round(total_act - total_ref, 2)
    return {
        "basis": basis,
        "groupBy": group_by,
        "lines": lines,
        "totals": {
            "reference": total_ref,
            "actual": total_act,
            "variance": total_var,
            "variancePct": round(total_var / total_ref * 100, 1) if total_ref else None,
        },
        "dataPoints": sum(1 for r in rows if r.get("date") and r.get("amount") is not None),
    }


def _linear_fit(values: list[float]) -> tuple[float, float]:
    n = len(values)
    xs = list(range(n))
    mean_x, mean_y = sum(xs) / n, sum(values) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / denom if denom else 0.0
    return slope, mean_y - slope * mean_x


def forecast_series(monthly: dict[str, float], periods: int = 3, method: str = "moving_average") -> dict:
    """Explainable forecasts only: moving average or linear trend."""
    if method not in {"moving_average", "linear_trend"}:
        raise ValueError("method must be 'moving_average' or 'linear_trend'.")
    if not 1 <= periods <= 12:
        raise ValueError("periods must be between 1 and 12.")
    keys = sorted(monthly)
    values = [monthly[k] for k in keys]
    minimum = 3 if method == "moving_average" else 2
    if len(values) < minimum:
        raise ValueError(
            f"Insufficient data: {method.replace('_', ' ')} needs at least {minimum} months of history; found {len(values)}."
        )

    warnings = []
    if len(values) < 6:
        warnings.append(f"Only {len(values)} month(s) of history: treat this forecast as indicative.")

    forecast = []
    if method == "moving_average":
        window = min(3, len(values))
        series = list(values)
        for step in range(1, periods + 1):
            value = sum(series[-window:]) / window
            series.append(value)
            forecast.append({"period": next_month_key(keys[-1], step), "value": round(max(value, 0.0), 2)})
        explanation = f"Average of the last {window} months, rolled forward."
    else:
        slope, intercept = _linear_fit(values)
        for step in range(1, periods + 1):
            value = intercept + slope * (len(values) - 1 + step)
            forecast.append({"period": next_month_key(keys[-1], step), "value": round(max(value, 0.0), 2)})
        explanation = f"Straight-line trend ({slope:+,.2f} per month) fitted to {len(values)} months."
    return {
        "method": method,
        "explanation": explanation,
        "history": [{"period": k, "value": monthly[k]} for k in keys],
        "forecast": forecast,
        "warnings": warnings,
    }


def scenario_analysis(
    revenue_total: float,
    expense_total: float,
    receivables: list[dict],
    revenue_change_pct: float = 0.0,
    expense_change_pct: float = 0.0,
    collection_delay_days: int = 0,
    today: date | None = None,
    weeks: int = 12,
) -> dict:
    """Base vs scenario. receivables: [{amount, due_date}] still unpaid."""
    for label, value in (("revenue_change_pct", revenue_change_pct), ("expense_change_pct", expense_change_pct)):
        if not -100 <= value <= 1000:
            raise ValueError(f"{label} must be between -100 and 1000.")
    if not 0 <= collection_delay_days <= 365:
        raise ValueError("collection_delay_days must be between 0 and 365.")

    today = today or date.today()
    revenue = revenue_total * (1 + revenue_change_pct / 100)
    expenses = expense_total * (1 + expense_change_pct / 100)

    def inflows(delay: int) -> list[float]:
        buckets = [0.0] * weeks
        for item in receivables:
            due, amount = item.get("due_date"), item.get("amount")
            if due is None or amount is None:
                continue
            expected = due + timedelta(days=delay)
            offset = (expected - today).days
            if offset < 0:
                offset = 0  # already late: expected as soon as possible
            week = offset // 7
            if week < weeks:
                buckets[week] += float(amount)
        return [round(b, 2) for b in buckets]

    base_in, scen_in = inflows(0), inflows(collection_delay_days)
    return {
        "base": {
            "revenue": round(revenue_total, 2),
            "expenses": round(expense_total, 2),
            "net": round(revenue_total - expense_total, 2),
            "inflowsNext12Weeks": round(sum(base_in), 2),
        },
        "scenario": {
            "revenue": round(revenue, 2),
            "expenses": round(expenses, 2),
            "net": round(revenue - expenses, 2),
            "inflowsNext12Weeks": round(sum(scen_in), 2),
        },
        "weeklyInflows": [
            {"week": i + 1, "base": base_in[i], "scenario": scen_in[i]} for i in range(weeks)
        ],
        "parameters": {
            "revenueChangePct": revenue_change_pct,
            "expenseChangePct": expense_change_pct,
            "collectionDelayDays": collection_delay_days,
        },
    }
