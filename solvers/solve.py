# solve.py

import pulp
from pulp import LpStatus, PULP_CBC_CMD
import pandas as pd

import config.settings as cfg
from data.processing import count_reconfigurations
from models.rolling_model import build_model
from solvers.recommend_days import recommend_days

def solve_main() -> dict:
    """
    Решает полную трёхступенчатую модель по дням (cfg.days).
    Возвращает словарь с результатами:
      model, status_str, days,
      rolled_total_3, enough, recommended_days,
      x1, x2, x3, y1, y2, y3, u1, u2, u3,
      rolling1_schedule, rolling1_tonnage, rolling1_reconf,
      rolling2_schedule, rolling2_tonnage, rolling2_reconf,
      rolling3_schedule, rolling3_tonnage, rolling3_reconf,
      metrics
    """
    # 1) Горизонт по дням
    days = cfg.days  # [1, 2, ..., horizon_days]

    # 2) Построение и решение модели
    model, x1, x2, x3, y1, y2, y3, u1, u2, u3 = build_model(days)
    solver = PULP_CBC_CMD(msg=True, timeLimit=5)
    status_code = model.solve(solver)
    status_str  = LpStatus[status_code]

    # 3) Сколько прокатано на этапе 3 по кампаниям
    rolled_total_3 = {
        k: sum(
            cfg.prod_rate[(r, k)] * pulp.value(x3[r][k][d])
            for r in cfg.rolling3 for d in days
        )
        for k in cfg.campaigns
    }

    # 4) Флаг «достаточно прокатано» (сравнение с НСИ выплавки)
    enough = all(
        rolled_total_3[k] >= cfg.total_nsi[k]
        for k in cfg.campaigns
    )

    # 5) Рекомендация горизонта в днях (если не Optimal или не хватает тоннажа)
    #recommended_days = None
    #if status_str != "Optimal" or not enough:
    #    recommended_days = recommend_days(len(days), limit_days=60)

    # ----------------------------
    # 6. Сбор решения и метрик
    # ----------------------------

    # 6.0. Оптимизированная выплавка (этап 1)
    rolling1_schedule = {
        (r, t): next((k for k in cfg.campaigns if pulp.value(x1[r][k][t]) > 0.5), "")
        for r in cfg.rolling1 for t in days
    }
    rolling1_tonnage = {
        (r, t): sum(cfg.prod_rate[(r, k)] * pulp.value(x1[r][k][t])
                   for k in cfg.campaigns)
        for r in cfg.rolling1 for t in days
    }
    rolling1_reconf = {}
    for r in cfg.rolling1:
        sched = [rolling1_schedule[(r, t)] for t in days]
        rolling1_reconf[r] = count_reconfigurations(sched, cfg.reconf_h)

    # 6.1. Расписание и тоннаж прокатки этапа 2
    rolling2_schedule = {
        (r, t): next((k for k in cfg.campaigns if pulp.value(x2[r][k][t]) > 0.5), "")
        for r in cfg.rolling2 for t in days
    }
    rolling2_tonnage = {
        (r, t): sum(cfg.prod_rate[(r, k)] * pulp.value(x2[r][k][t])
                   for k in cfg.campaigns)
        for r in cfg.rolling2 for t in days
    }
    rolling2_reconf = {}
    for r in cfg.rolling2:
        sched = [rolling2_schedule[(r, t)] for t in days]
        rolling2_reconf[r] = count_reconfigurations(sched, cfg.reconf_h)

    # 6.2. Расписание и тоннаж прокатки этапа 3
    rolling3_schedule = {
        (r, t): next((k for k in cfg.campaigns if pulp.value(x3[r][k][t]) > 0.5), "")
        for r in cfg.rolling3 for t in days
    }
    rolling3_tonnage = {
        (r, t): sum(cfg.prod_rate[(r, k)] * pulp.value(x3[r][k][t])
                   for k in cfg.campaigns)
        for r in cfg.rolling3 for t in days
    }
    rolling3_reconf = {}
    for r in cfg.rolling3:
        sched = [rolling3_schedule[(r, t)] for t in days]
        rolling3_reconf[r] = count_reconfigurations(sched, cfg.reconf_h)

    # 6.3. Финальная метрика
    total_reconf = round(
        sum(rolling1_reconf.values())
      + sum(rolling2_reconf.values())
      + sum(rolling3_reconf.values()), 2
    )
    total_prod_stage1 = round(
        sum(
            cfg.prod_rate[(r, k)] * pulp.value(x1[r][k][d])
            for r in cfg.rolling1 for k in cfg.campaigns for d in days
        ), 2
    )
    total_prod_3 = sum(rolled_total_3.values())
    used_agg = (
        sum(int(pulp.value(u1[r])) for r in cfg.rolling1)
      + sum(int(pulp.value(u2[r])) for r in cfg.rolling2)
      + sum(int(pulp.value(u3[r])) for r in cfg.rolling3)
    )
    loads = [
        sum(int(pulp.value(x1[r][k][d])) for k in cfg.campaigns for d in days)
        for r in cfg.rolling1
    ] + [
        sum(int(pulp.value(x2[r][k][d])) for k in cfg.campaigns for d in days)
        for r in cfg.rolling2
    ] + [
        sum(int(pulp.value(x3[r][k][d])) for k in cfg.campaigns for d in days)
        for r in cfg.rolling3
    ]
    evenness = round(pd.Series(loads).std(), 2) if loads else 0

    metrics = {
        "Суммарно перевалок, ч": total_reconf,
        "Суммарно выплавлено, т": total_prod_stage1,
        "Суммарно прокатано, т": total_prod_3,
        "Задействовано агрегатов": used_agg,
        "Отклонение загрузки": evenness
    }

    # 7) Итоговый словарь
    return {
        "model": model,
        "status_str": status_str,
        "days": days,
        "rolled_total_3": rolled_total_3,
        "enough": enough,
        #"recommended_days": recommended_days,
        "x1": x1, "x2": x2, "x3": x3,
        "y1": y1, "y2": y2, "y3": y3,
        "u1": u1, "u2": u2, "u3": u3,
        "rolling1_schedule": rolling1_schedule,
        "rolling1_tonnage": rolling1_tonnage,
        "rolling1_reconf": rolling1_reconf,
        "rolling2_schedule": rolling2_schedule,
        "rolling2_tonnage": rolling2_tonnage,
        "rolling2_reconf": rolling2_reconf,
        "rolling3_schedule": rolling3_schedule,
        "rolling3_tonnage": rolling3_tonnage,
        "rolling3_reconf": rolling3_reconf,
        "metrics": metrics,
    }

if __name__ == "__main__":
    res = solve_main()
    print("Статус:", res["status_str"])
    if not res["enough"]:
        print("Не хватает тоннажа, рекомендовано дней:", res["recommended_days"])
