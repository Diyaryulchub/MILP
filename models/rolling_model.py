# models/rolling_model.py

import pulp
from pulp import LpProblem, LpMaximize
import config.settings as cfg

def build_model(days_horizon: list[int]):
    """
    Гибкая модель планирования для произвольного числа стадий и агрегатов.
    days_horizon: список дней.
    Возвращает: m, x_vars, y_vars, u_vars, z_vars
    """
    m = LpProblem("RollingScheduling", LpMaximize)

    # 1) Создаём переменные для каждой стадии из cfg.stage_aggs
    stage_aggs = cfg.stage_aggs  # e.g. {1:rolling1,2:rolling2,3:rolling3,4:rolling4}
    x_vars = {}
    y_vars = {}
    u_vars = {}
    z_vars = {}
    for stage, aggs in stage_aggs.items():
        x_vars[stage] = pulp.LpVariable.dicts(
            f"x{stage}", (aggs, cfg.campaigns, days_horizon),
            lowBound=0, upBound=1, cat="Binary"
        )
        y_vars[stage] = pulp.LpVariable.dicts(
            f"y{stage}", (aggs, cfg.campaigns, cfg.campaigns, days_horizon[:-1]),
            lowBound=0, upBound=1, cat="Binary"
        )
        u_vars[stage] = pulp.LpVariable.dicts(
            f"u{stage}", aggs, lowBound=0, upBound=1, cat="Binary"
        )
        z_vars[stage] = pulp.LpVariable.dicts(
            f"z{stage}", (aggs, days_horizon), lowBound=0, upBound=1, cat="Binary"
        )

    # 2) Общие ограничения для всех стадий
    for stage, aggs in stage_aggs.items():
        x = x_vars[stage]
        y = y_vars[stage]
        u = u_vars[stage]
        z = z_vars[stage]

        # 2.0. Последовательность vs параллельность на уровне ресурса
        seq_aggs = [r for r in aggs if not cfg.can_parallel.get(r, False)]
        if seq_aggs:
            for k in cfg.campaigns:
                for t in days_horizon:
                    m += (
                        pulp.lpSum(x[r][k][t] for r in seq_aggs) <= 1,
                        f"Stage{stage}_SequentialPerResource_{k}_{t}"
                    )

        for r in aggs:
            # 2.1. Не более одной кампании на агрегат в день
            for t in days_horizon:
                m += (
                    pulp.lpSum(x[r][k][t] for k in cfg.campaigns) <= 1,
                    f"OneJob_stage{stage}_{r}_{t}"
                )

            # 2.2. Ремонты блокируют и x, и z
            for t in cfg.repairs.get(r, []):
                for k in cfg.campaigns:
                    m += (x[r][k][t] == 0, f"Repair_stage{stage}_{r}_{k}_{t}")
                m += (z[r][t] == 0,    f"NoReconfOnRepair_stage{stage}_{r}_{t}")

            # 2.3. Фиксация смены кампании + тэг перевалки
            for k1 in cfg.campaigns:
                for k2 in cfg.campaigns:
                    if k1 == k2: continue
                    for t in days_horizon[:-1]:
                        # смена
                        m += (
                            y[r][k1][k2][t] >= x[r][k1][t] + x[r][k2][t+1] - 1,
                            f"Reconf_stage{stage}_{r}_{k1}_to_{k2}_{t}"
                        )
                        # длительность
                        days_req = cfg.reconf_matrix[r][(k1, k2)] // cfg.hours_per_day
                        for d in range(1, days_req+1):
                            if (t+d) in days_horizon:
                                m += (
                                    z[r][t+d] >= y[r][k1][k2][t],
                                    f"TagReconf_stage{stage}_{r}_{k1}_{k2}_{t}_d{d}"
                                )

            # 2.4. Запрет работы в день перевалки
            for t in days_horizon:
                for k in cfg.campaigns:
                    m += (
                        x[r][k][t] <= 1 - z[r][t],
                        f"NoJobOnReconf_stage{stage}_{r}_{k}_{t}"
                    )

            # 2.5. Запрет “нулевых” дней без перевалки
            for idx in range(1, len(days_horizon)-1):
                tp, tc, tn = days_horizon[idx-1], days_horizon[idx], days_horizon[idx+1]
                if any(d in cfg.repairs.get(r, []) for d in (tp,tc,tn)):
                    continue
                left  = pulp.lpSum(x[r][k][tp] for k in cfg.campaigns)
                right = pulp.lpSum(x[r][k][tn] for k in cfg.campaigns)
                m += (
                    left + right <= z[r][tc] + 1,
                    f"NoIdle_stage{stage}_{r}_{tc}"
                )

            # 2.6. Использование агрегата
            total_act = pulp.lpSum(x[r][k][t] for k in cfg.campaigns for t in days_horizon)
            m += (u[r] <= total_act,                f"UseUpper_stage{stage}_{r}")
            m += (u[r] >= total_act/len(days_horizon), f"UseLower_stage{stage}_{r}")

    # 3) Специфичные для стадии ограничения
    for stage, aggs in stage_aggs.items():
        x = x_vars[stage]

        if stage == 1:
            # NSI-ограничение
            for k in cfg.campaigns:
                m += (
                    pulp.lpSum(x[r][k][t]*cfg.prod_rate[(r,k)]
                               for r in aggs for t in days_horizon)
                    <= cfg.total_nsi[k],
                    f"NSI_Limit_{k}"
                )
        else:
            # Материал-баланс с предыдущей стадии
            prev = stage_aggs[stage-1]
            for k in cfg.campaigns:
                for t in days_horizon:
                    prod  = pulp.lpSum(
                        x[r][k][tau]*cfg.prod_rate[(r,k)]
                        for r in aggs for tau in days_horizon if tau <= t
                    )
                    avail = pulp.lpSum(
                        x_vars[stage-1][r_prev][k][tau]*cfg.prod_rate[(r_prev,k)]
                        for r_prev in prev for tau in days_horizon
                        if tau + cfg.cooling_time[k] <= t
                    )
                    m += (
                        prod <= avail,
                        f"MatBal_stage{stage}_{k}_{t}"
                    )

    # 4) Целевая функция (как было)
    obj_prod = pulp.lpSum(
        x_vars[s][r][k][t]*cfg.prod_rate[(r,k)]
        for s in stage_aggs for r in stage_aggs[s]
        for k in cfg.campaigns for t in days_horizon
    )
    obj_conf = pulp.lpSum(
        y_vars[s][r][k1][k2][t]*cfg.reconf_matrix[r][(k1,k2)]
        for s in stage_aggs for r in stage_aggs[s]
        for k1 in cfg.campaigns for k2 in cfg.campaigns if k1!=k2
        for t in days_horizon[:-1]
    )
    obj_use = pulp.lpSum(
        u_vars[s][r]
        for s in stage_aggs for r in stage_aggs[s]
    )
    m += obj_prod - cfg.pen_reconf*obj_conf - cfg.pen_resource*obj_use

    # 5) Возвращаем универсальные словари
    return m, x_vars, y_vars, u_vars, z_vars
