# models/rolling_model.py

import pulp
from pulp import LpProblem, LpMaximize

from config.settings import (
    campaigns,
    rolling1, rolling2, rolling3,
    prod_rate,
    reconf_d,
    cooling_time,
    PEN, repairs,
    total_nsi
)

# x1, x2, x3 — бинарные переменные: 1, если кампания k выполняется на ресурсе r в день t на этапе 1, 2 или 3
# y1, y2, y3 — бинарные переменные: 1, если между днями t и t+1 на ресурсе r произошла смена кампании с k1 на k2 (перевалка)
# u1, u2, u3 — бинарные переменные: 1, если ресурс r был задействован хотя бы один день на соответствующем этапе

def build_model(days_horizon: list[int]):
    """
    Трёхступенчатая модель оптимизированного планирования:
      этап 1 — выплавка,
      этап 2 — прокатка,
      этап 3 — прокатка.
    days_horizon: список дней.
    Возвращает: model, x1, x2, x3, y1, y2, y3, u1, u2, u3
    """
    m = LpProblem('ThreeStageRolling', LpMaximize)

    # ----------------------------
    # Этап 1: выплавка
    # ----------------------------
    x1 = pulp.LpVariable.dicts(
        'x1', (rolling1, campaigns, days_horizon), cat='Binary'
    )
    y1 = pulp.LpVariable.dicts(
        'y1', (rolling1, campaigns, campaigns, days_horizon[:-1]), cat='Binary'
    )
    u1 = pulp.LpVariable.dicts('u1', rolling1, cat='Binary')

    # 1.1 Один агрегат — одна кампания в день (этап 1)
    for r in rolling1:
        for t in days_horizon:
            m += (
                pulp.lpSum(x1[r][k][t] for k in campaigns) <= 1
            ), f"Stage1_OneJob_{r}_{t}"

    # 1.2 Переналадки на этапе 1
    for r in rolling1:
        for k1 in campaigns:
            for k2 in campaigns:
                if k1 == k2:
                    continue
                for t in days_horizon[:-1]:
                    m += (
                        y1[r][k1][k2][t]
                        >= x1[r][k1][t] + x1[r][k2][t+1] - 1
                    ), f"Stage1_Reconf_{r}_{k1}_to_{k2}_{t}"

    # 1.3 Агрегат этапа 1 задействован ⇔ работал хоть раз
    for r in rolling1:
        total_act1 = pulp.lpSum(
            x1[r][k][t] for k in campaigns for t in days_horizon
        )
        m += (u1[r] <= total_act1), f"Stage1_UseUpper_{r}"
        m += (u1[r] >= total_act1/len(days_horizon)), f"Stage1_UseLower_{r}"

    # 1.4 НЕ ВЫПЛАВЛЯТЬ больше, чем НСИ (total_nsi)
    for k in campaigns:
        m += (
            pulp.lpSum(
                x1[r][k][t] * prod_rate[(r, k)]
                for r in rolling1 for t in days_horizon
            )
            <= total_nsi[k]
        ), f"Stage1_NSI_Limit_{k}"

    # 1.5 Нельзя выплавлять в ремонт
    for r in rolling1:
        for t in days_horizon:
            if t in repairs.get(r, []):
                for k in campaigns:
                    m += x1[r][k][t] == 0, f"Stage1_Repair_{r}_{t}_{k}"

    # ----------------------------
    # Этап 2: прокатка
    # ----------------------------
    x2 = pulp.LpVariable.dicts(
        'x2', (rolling2, campaigns, days_horizon), cat='Binary'
    )
    y2 = pulp.LpVariable.dicts(
        'y2', (rolling2, campaigns, campaigns, days_horizon[:-1]), cat='Binary'
    )
    u2 = pulp.LpVariable.dicts('u2', rolling2, cat='Binary')

    # 2.1 Материальный баланс: не прокатать больше, чем выплавлено
    for k in campaigns:
        m += (
            pulp.lpSum(
                x2[r][k][t] * prod_rate[(r, k)]
                for r in rolling2 for t in days_horizon
            )
            <= pulp.lpSum(
                x1[r1][k][t1] * prod_rate[(r1, k)]
                for r1 in rolling1 for t1 in days_horizon
            )
        ), f"Stage2_MaterialLimit_{k}"

    # 2.2 Один агрегат — одна кампания в день (этап 2)
    for r in rolling2:
        for t in days_horizon:
            m += (
                pulp.lpSum(x2[r][k][t] for k in campaigns) <= 1
            ), f"Stage2_OneJob_{r}_{t}"

    # 2.? В каждый момент времени одну кампанию обрабатывает максимум один ресурс (этап 2)
    for k in campaigns:
        for t in days_horizon:
            m += (
                pulp.lpSum(x2[r][k][t] for r in rolling2) <= 1
            ), f"Stage2_SingleResourcePerCampaign_{k}_{t}"

    # 2.3 Учет охлаждения между этапами 1 и 2
    for r in rolling2:
        for k in campaigns:
            for t in days_horizon:
                produced_to_t = pulp.lpSum(
                    x2[r][k][τ] * prod_rate[(r, k)]
                    for τ in days_horizon if τ <= t
                )
                available_to_t = pulp.lpSum(
                    x1[r1][k][τ] * prod_rate[(r1, k)]
                    for r1 in rolling1 for τ in days_horizon
                    if τ + cooling_time[k] <= t
                )
                m += (
                    produced_to_t <= available_to_t
                ), f"Stage2_Cooling_{r}_{k}_{t}"

    # 2.4 Переналадки на этапе 2
    for r in rolling2:
        for k1 in campaigns:
            for k2 in campaigns:
                if k1 == k2:
                    continue
                for t in days_horizon[:-1]:
                    m += (
                        y2[r][k1][k2][t]
                        >= x2[r][k1][t] + x2[r][k2][t+1] - 1
                    ), f"Stage2_Reconf_{r}_{k1}_to_{k2}_{t}"

    # 2.5 Агрегат этапа 2 задействован, если работал хоть раз
    for r in rolling2:
        total_act2 = pulp.lpSum(
            x2[r][k][t] for k in campaigns for t in days_horizon
        )
        m += (u2[r] <= total_act2), f"Stage2_UseUpper_{r}"
        m += (u2[r] >= total_act2/len(days_horizon)), f"Stage2_UseLower_{r}"
    
    # 2.6 Нельзя выплавлять в ремонт
    for r in rolling2:
       for t in days_horizon:
           if t in repairs.get(r, []):
               for k in campaigns:
                    m += x2[r][k][t] == 0, f"Stage2_Repair_{r}_{t}_{k}"

    # ----------------------------
    # Этап 3: прокатка
    # ----------------------------
    x3 = pulp.LpVariable.dicts(
        'x3', (rolling3, campaigns, days_horizon), cat='Binary'
    )
    y3 = pulp.LpVariable.dicts(
        'y3', (rolling3, campaigns, campaigns, days_horizon[:-1]), cat='Binary'
    )
    u3 = pulp.LpVariable.dicts('u3', rolling3, cat='Binary')

    # 3.1 Материальный баланс этап 2→3
    for k in campaigns:
        for t in days_horizon:
            available_stage2 = pulp.lpSum(
                x2[r][k][τ] * prod_rate[(r, k)]
                for r in rolling2 for τ in days_horizon
                if τ + cooling_time[k] <= t
            )
            used_stage3 = pulp.lpSum(
                x3[r][k][τ] * prod_rate[(r, k)]
                for r in rolling3 for τ in days_horizon if τ <= t
            )
            m += (
                used_stage3 <= available_stage2
            ), f"Stage3_MaterialBalance_{k}_{t}"

    # 3.2 Один агрегат — одна кампания в день (этап 3)
    for r in rolling3:
        for t in days_horizon:
            m += (
                pulp.lpSum(x3[r][k][t] for k in campaigns) <= 1
            ), f"Stage3_OneJob_{r}_{t}"

    # 3.3 Переналадки на этапе 3
    for r in rolling3:
        for k1 in campaigns:
            for k2 in campaigns:
                if k1 == k2:
                    continue
                for t in days_horizon[:-1]:
                    m += (
                        y3[r][k1][k2][t]
                        >= x3[r][k1][t] + x3[r][k2][t+1] - 1
                    ), f"Stage3_Reconf_{r}_{k1}_to_{k2}_{t}"

    # 3.4 Агрегат этапа 3 задействован ⇔ работал хоть раз
    for r in rolling3:
        total_act3 = pulp.lpSum(
            x3[r][k][t] for k in campaigns for t in days_horizon
        )
        m += (u3[r] <= total_act3), f"Stage3_UseUpper_{r}"
        m += (u3[r] >= total_act3/len(days_horizon)), f"Stage3_UseLower_{r}"

    # 3.5 Нельзя выплавлять в ремонт
    for r in rolling3:
        for t in days_horizon:
            if t in repairs.get(r, []):
                for k in campaigns:
                    m += x3[r][k][t] == 0, f"Stage3_Repair_{r}_{t}_{k}"

    # ----------------------------
    # Целевая функция
    # ----------------------------
    obj_prod1 = pulp.lpSum(
        x1[r][k][t] * prod_rate[(r, k)]
        for r in rolling1 for k in campaigns for t in days_horizon
    )
    obj_prod2 = pulp.lpSum(
        x2[r][k][t] * prod_rate[(r, k)]
        for r in rolling2 for k in campaigns for t in days_horizon
    )
    obj_prod3 = pulp.lpSum(
        x3[r][k][t] * prod_rate[(r, k)]
        for r in rolling3 for k in campaigns for t in days_horizon
    )
    obj_conf1 = pulp.lpSum(
        y1[r][k1][k2][t] * reconf_d[r]
        for r in rolling1 for k1 in campaigns for k2 in campaigns if k1 != k2 for t in days_horizon[:-1]
    )
    obj_conf2 = pulp.lpSum(
        y2[r][k1][k2][t] * reconf_d[r]
        for r in rolling2 for k1 in campaigns for k2 in campaigns if k1 != k2 for t in days_horizon[:-1]
    )
    obj_conf3 = pulp.lpSum(
        y3[r][k1][k2][t] * reconf_d[r]
        for r in rolling3 for k1 in campaigns for k2 in campaigns if k1 != k2 for t in days_horizon[:-1]
    )
    obj_use1 = pulp.lpSum(u1[r] for r in rolling1)
    obj_use2 = pulp.lpSum(u2[r] for r in rolling2)
    obj_use3 = pulp.lpSum(u3[r] for r in rolling3)

    m += (
        (obj_prod1 + obj_prod2 + obj_prod3)
        - PEN * (obj_conf1 + obj_conf2 + obj_conf3)
        - (obj_use1 + obj_use2 + obj_use3)
    )

    return m, x1, x2, x3, y1, y2, y3, u1, u2, u3
