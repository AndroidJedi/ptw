from __future__ import annotations

from statistics import mean
from typing import Any


def generation_report(number: int, ranking: list[dict[str, Any]], previous_best: float | None,
                      historical: dict[str, Any] | None, owner_count: int, recoveries: int,
                      calls: int, tokens: int) -> tuple[str, dict[str, Any]]:
    scores = [float(row["aggregate_score"]) for row in ranking]
    best, worst, average = max(scores), min(scores), mean(scores)
    delta = None if previous_best is None else best - previous_best
    payload = {"generation": number, "ranking": ranking, "best": best, "average": average, "worst": worst,
               "delta_best": delta, "historical_best": historical, "owner_ideas": owner_count,
               "recoveries": recoveries, "model_calls": calls, "tokens": tokens}
    lines = [f"G{number} generation report", "", "Ranking:"]
    lines.extend(f"{index}. #{row['idea_id']} — {float(row['aggregate_score']):.2f} ({row['mode']}) {row['title']}"
                 for index, row in enumerate(ranking, 1))
    lines += ["", f"Best / average / worst: {best:.2f} / {average:.2f} / {worst:.2f}",
              f"Delta vs previous best: {'n/a' if delta is None else f'{delta:+.2f}'}",
              f"Owner ideas: {owner_count}; recoveries: {recoveries}; calls/tokens: {calls}/{tokens}"]
    return "\n".join(lines), payload
