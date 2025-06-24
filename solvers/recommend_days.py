# solvers/recommend_days.py

import math
import pulp
from pulp import LpStatus, PULP_CBC_CMD

import config.settings as cfg
from models.rolling_model import build_model

def recommend_days(initial_days: int, limit_days: int = None) -> int | None:
    """
    Рекомендует минимальный горизонт D (initial_days < D ≤ limit_days), в днях, при котором:
      1) модель решается со статусом Optimal,
      2) на этапе 3 прокатано ≥ NSI-объёмы (cfg.total_nsi).
    """
    if limit_days is None:
        limit_days = len(cfg.days)

    # Lower bound: дни, необходимые для прокатки NSI
    lb = initial_days
    days_needed = []
    for k in cfg.campaigns:
        if cfg.total_nsi.get(k, 0) > 0:
            max_rate = max(cfg.prod_rate.get((r, k), 0) for r in cfg.rolling3)
            if max_rate > 0:
                days_needed.append(math.ceil(cfg.total_nsi[k] / max_rate))
    if days_needed:
        lb = max(lb, max(days_needed))

    lo = max(initial_days + 1, lb + 1)
    if lo > limit_days:
        return None

    def is_feasible(D: int) -> bool:
        days_horizon = cfg.days[:D]
        model, x1, x2, x3, y1, y2, y3, u1, u2, u3 = build_model(days_horizon)
        status = model.solve(PULP_CBC_CMD(msg=False, timeLimit=30))
        if LpStatus[status] != "Optimal":
            return False
        rolled3 = {
            k: sum(
                cfg.prod_rate[(r, k)] * pulp.value(x3[r][k][d])
                for r in cfg.rolling3 for d in days_horizon
            )
            for k in cfg.campaigns
        }
        return all(rolled3[k] >= cfg.total_nsi.get(k, 0) for k in cfg.campaigns)

    if is_feasible(lo):
        return lo

    hi = lo
    while hi < limit_days:
        hi = min(limit_days, hi * 2)
        if is_feasible(hi):
            break
    else:
        return None

    best = None
    left, right = lo, hi
    while left <= right:
        mid = (left + right) // 2
        if is_feasible(mid):
            best = mid
            right = mid - 1
        else:
            left = mid + 1

    return best