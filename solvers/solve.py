# solve.py

import pulp
from pulp import LpStatus, PULP_CBC_CMD, value
import pandas as pd
import math

import config.settings as cfg
from models.rolling_model import build_model
from data.processing import count_reconfigurations

def _extract_stage(days: list[int],
                   aggs: list[str],
                   x: dict,
                   z: dict,
                   y: dict,
                   repairs: dict[str, list[int]]
                  ) -> tuple[
                      dict[tuple[str,int], str],
                      dict[tuple[str,int], float],
                      dict[str, float]
                  ]:
    """
    Извлекает для одной стадии:
      — расписание (код/РЕМОНТ/ПЕРЕВАЛКА или пусто),
      — тоннаж,
      — суммарное время переналадок (часов) на каждом агрегате.
    """
    schedule: dict[tuple[str,int], str] = {}
    tonnage:  dict[tuple[str,int], float] = {}
    reconf:   dict[str, float] = {r: 0.0 for r in aggs}

    # Базовая раскладка: ремонт, флаг перевалки, кампании
    for r in aggs:
        for t in days:
            if t in repairs.get(r, []):
                schedule[(r, t)] = "РЕМОНТ"
                tonnage[(r, t)] = 0.0
            elif value(z[r][t]) > 0.5:
                schedule[(r, t)] = "ПЕРЕВАЛКА"
                tonnage[(r, t)] = 0.0
            else:
                found = False
                for k in cfg.campaigns:
                    if value(x[r][k][t]) > 0.5:
                        schedule[(r, t)] = k
                        tonnage[(r, t)] = cfg.prod_rate[(r, k)]
                        found = True
                        break
                if not found:
                    schedule[(r, t)] = ""
                    tonnage[(r, t)] = 0.0

        # Суммируем время переналадок по y
        for k1 in cfg.campaigns:
            for k2 in cfg.campaigns:
                if k1 == k2: continue
                for t in days[:-1]:
                    if value(y[r][k1][k2][t]) > 0.5:
                        reconf[r] += cfg.reconf_matrix[r][(k1, k2)]

    # Собираем задачи перевалок из y
    reconf_tasks: list[tuple[str,str,str,int,int]] = []
    for r in aggs:
        for k1 in cfg.campaigns:
            for k2 in cfg.campaigns:
                if k1 == k2: continue
                for t in days[:-1]:
                    if value(y[r][k1][k2][t]) > 0.5:
                        hours    = cfg.reconf_matrix[r][(k1, k2)]
                        days_req = math.ceil(hours / cfg.hours_per_day)
                        start    = t + 1
                        end      = start + days_req - 1
                        reconf_tasks.append((r, k1, k2, start, end))

    # Убираем все старые метки "ПЕРЕВАЛКА"
    #for (r, t), v in list(schedule.items()):
        #if v == "ПЕРЕВАЛКА":
            #schedule[(r, t)] = ""

    # Склеиваем блоки перевалок как "ПЕРЕВАЛКА k1→k2"
    for r, k1, k2, start, end in reconf_tasks:
        for tt in range(start, end + 1):
            if (r, tt) in schedule:
                schedule[(r, tt)] = f"ПЕРЕВАЛКА {k1}→{k2}"
                tonnage[(r, tt)] = 0.0

    return schedule, tonnage, reconf


def solve_main() -> dict:
    """
    Решает модель для произвольного числа стадий и агрегатов из cfg.stage_aggs.
    Возвращает словарь с результатами, включая backward‐compatibility keys:
      model, status_str, days,
      rolled_total_3, enough,
      x_vars, y_vars, u_vars, z_vars,
      schedules, tonnages, reconfs,
      rolling1_schedule, rolling1_tonnage, rolling1_reconf, ...
      metrics
    """
    days = cfg.days

    # 1) Построение и решение модели
    model, x_vars, y_vars, u_vars, z_vars = build_model(days)
    solver     = PULP_CBC_CMD(msg=True, timeLimit=60
    ,gapRel=0.2
    )
    status     = model.solve(solver)
    status_str = LpStatus[status]

    # 2) Итоговый тоннаж по кампаниям на последней стадии
    final_stage = max(cfg.stage_aggs.keys())
    rolled_total = {
        k: sum(cfg.prod_rate[(r, k)] * value(x_vars[final_stage][r][k][d])
               for r in cfg.stage_aggs[final_stage] for d in days)
        for k in cfg.campaigns
    }
    enough = all(rolled_total[k] >= cfg.total_nsi[k] for k in cfg.campaigns)

    # 3) Извлечение расписания/тоннажа/перевалок для каждой стадии
    schedules = {}
    tonnages  = {}
    reconfs    = {}
    for stage, aggs in cfg.stage_aggs.items():
        sched, ton, rec = _extract_stage(days, aggs,
                                         x_vars[stage],
                                         z_vars[stage],
                                         y_vars[stage],
                                         cfg.repairs)
        schedules[stage] = sched
        tonnages[stage]  = ton
        reconfs[stage]   = rec
        print(sched, ton, rec)

    # 4) Метрики
    total_reconf = sum(sum(v.values()) for v in reconfs.values())
    total_prod1  = sum(cfg.prod_rate[(r, k)] * value(x_vars[1][r][k][d])
                       for r in cfg.stage_aggs[1] for k in cfg.campaigns for d in days)
    total_prodN  = sum(rolled_total.values())
    used_aggs    = sum(int(value(u_vars[s][r]))
                       for s in cfg.stage_aggs for r in cfg.stage_aggs[s])
    loads = [sum(int(value(x_vars[s][r][k][d]))
                 for k in cfg.campaigns for d in days)
             for s in cfg.stage_aggs for r in cfg.stage_aggs[s]]
    evenness = round(pd.Series(loads).std(), 2) if loads else 0.0

    metrics = {
        "Суммарно перевалок, ч":    round(total_reconf, 2),
        "Суммарно выплавлено, т":   round(total_prod1, 2),
        "Суммарно прокатано, т":    round(total_prodN, 2),
        "Задействовано агрегатов":  used_aggs,
        "Отклонение загрузки":      evenness
    }

    # 5) Собираем результат и backward-compatible keys
    result = {
        "model": model,
        "status_str": status_str,
        "days": days,
        "rolled_total_3": rolled_total,
        "enough": enough,
        "x_vars": x_vars,
        "y_vars": y_vars,
        "u_vars": u_vars,
        "z_vars": z_vars,
        "schedules": schedules,
        "tonnages": tonnages,
        "reconfs": reconfs,
        "metrics": metrics,
    }
    # backward compatibility: rolling{n}_schedule, rolling{n}_tonnage, rolling{n}_reconf
    for stage in cfg.stage_aggs:
        result[f"rolling{stage}_schedule"] = schedules[stage]
        result[f"rolling{stage}_tonnage"]  = tonnages[stage]
        result[f"rolling{stage}_reconf"]   = reconfs[stage]

    return result


if __name__ == "__main__":
    res = solve_main()
    print("Статус:", res["status_str"])
