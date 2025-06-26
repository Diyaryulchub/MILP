# models/rolling_model.py

import pulp
from pulp import LpProblem, LpMaximize

from config.settings import (
    campaigns,
    rolling1, rolling2, rolling3,
    prod_rate,
    reconf_matrix,
    cooling_time,
    PEN, repairs,
    total_nsi
)

def build_model(days_horizon: list[int]):
    """
    Трёхступенчатая модель оптимизированного планирования:
      этап 1 — выплавка,
      этап 2 — прокатка,
      этап 3 — прокатка.
    days_horizon: список дней.
    Возвращает: model, x1, x2, x3, y1, y2, y3, u1, u2, u3, z1, z2, z3
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
    z1 = pulp.LpVariable.dicts('z1', (rolling1, days_horizon), cat='Binary')

    # 1.1 Ограничение: на каждом агрегате — не более одной кампании в день
    for r in rolling1:
        for t in days_horizon:
            m += pulp.lpSum(x1[r][k][t] for k in campaigns) <= 1, f"Stage1_OneJob_{r}_{t}"

    # 1.2 Ограничение: фиксация смены кампании (y1=1, если была смена кампании)
    # ("Переналадки: Учитывать длительность переналадки при смене кампаний на одном агрегате.")
    for r in rolling1:
        for k1 in campaigns:
            for k2 in campaigns:
                if k1 == k2: continue
                for t in days_horizon[:-1]:
                    m += y1[r][k1][k2][t] >= x1[r][k1][t] + x1[r][k2][t+1] - 1, \
                         f"Stage1_Reconf_{r}_{k1}_to_{k2}_{t}"

    # 1.3 Ограничение: агрегат считается используемым, если работал хотя бы 1 раз
    # ("Минимум задействованных агрегатов: использовать минимальное число параллельных агрегатов без срыва плана.")
    for r in rolling1:
        total_act1 = pulp.lpSum(x1[r][k][t] for k in campaigns for t in days_horizon)
        m += u1[r] <= total_act1, f"Stage1_UseUpper_{r}"
        m += u1[r] >= total_act1/len(days_horizon), f"Stage1_UseLower_{r}"

    # 1.4 Ограничение: не превышать НСИ по каждой кампании (ограничение объема)
    # ("Общий объем кампании, ... Для каждой кампании на агрегате:")
    for k in campaigns:
        m += pulp.lpSum(x1[r][k][t] * prod_rate[(r,k)]
                        for r in rolling1 for t in days_horizon) <= total_nsi[k], \
             f"Stage1_NSI_Limit_{k}"

    # 1.5 Ограничение: в день ремонта агрегата — нельзя работать
    # ("Плановые простои: интервалы времени, когда запуск кампаний запрещен.")
    for r in rolling1:
        for t in repairs.get(r, []):
            for k in campaigns:
                m += x1[r][k][t] == 0, f"Stage1_Repair_{r}_{t}_{k}"

    # 1.6 Ограничение: работа запрещена в день перевалки
    # ("Переналадка выполняется сразу после завершения предыдущей кампании.")
    for r in rolling1:
        for t in days_horizon:
            for k in campaigns:
                m += x1[r][k][t] <= 1 - z1[r][t], f"Stage1_NoJobOnReconf_{r}_{k}_{t}"

    # 1.7 Ограничение: пометки перевалки на несколько дней (по длительности из reconf_matrix)
    # ("Учитывать длительность переналадки при смене кампаний на одном агрегате.")
    for r in rolling1:
        for t in days_horizon[1:]:
            for k1 in campaigns:
                for k2 in campaigns:
                    if k1 == k2: continue
                    days_req = int(reconf_matrix[r][(k1,k2)] / 24)
                    for d in range(1, days_req+1):
                        if (t+d) in days_horizon:
                            m += z1[r][t+d] >= y1[r][k1][k2][t], \
                                 f"Stage1_TagReconf_{r}_{k1}_{k2}_at_{t}_d{d}"

    # 1.8 Ограничение: нельзя ставить перевалку в дни ремонта
    # ("Плановые простои блокируют запуск кампаний.")
    for r in rolling1:
        for t in repairs.get(r, []):
            m += z1[r][t] == 0, f"Stage1_NoReconfOnRepair_{r}_{t}"

    # 1.9 Ограничение: запрет “нулевых” дней между двумя рабочими днями
    # ("Минимальная длительность кампании: равна длительности партии (рассчитывается как объем партии / производительность).")
    for r in rolling1:
        for idx in range(1, len(days_horizon)-1):
            t_prev = days_horizon[idx-1]
            t      = days_horizon[idx]
            t_next = days_horizon[idx+1]
            # пропускаем ремонты
            if t in repairs.get(r, []) or t_prev in repairs.get(r, []) or t_next in repairs.get(r, []):
                continue
            left  = pulp.lpSum(x1[r][k][t_prev] for k in campaigns)
            right = pulp.lpSum(x1[r][k][t_next] for k in campaigns)
            # если были работы в t-1 и в t+1, то либо перевалка в t, либо ремонт
            m += left + right <= z1[r][t] + 1, f"Stage1_NoIdleBetween_{r}_{t}"

    # ----------------------------
    # Этап 2: прокатка
    # ----------------------------
    x2 = pulp.LpVariable.dicts('x2', (rolling2, campaigns, days_horizon), cat='Binary')
    y2 = pulp.LpVariable.dicts('y2', (rolling2, campaigns, campaigns, days_horizon[:-1]), cat='Binary')
    u2 = pulp.LpVariable.dicts('u2', rolling2, cat='Binary')
    z2 = pulp.LpVariable.dicts('z2', (rolling2, days_horizon), cat='Binary')

    # 2.1 Ограничение: баланс материала между этапами
    # ("Кампания запускается, только если в достаточно ингредиентов.")
    for k in campaigns:
        m += (pulp.lpSum(x2[r][k][t]*prod_rate[(r,k)] for r in rolling2 for t in days_horizon)
              <= pulp.lpSum(x1[r1][k][t1]*prod_rate[(r1,k)] for r1 in rolling1 for t1 in days_horizon)
             ), f"Stage2_MaterialLimit_{k}"

    # 2.2 Ограничение: один агрегат — одна кампания в день
    for r in rolling2:
        for t in days_horizon:
            m += pulp.lpSum(x2[r][k][t] for k in campaigns) <= 1, f"Stage2_OneJob_{r}_{t}"

    # 2.2.1 Ограничение: максимум один ресурс на кампанию в день
    # ("Параллельные агрегаты: кампании выполняются независимо ...")
    #for k in campaigns:
        #for t in days_horizon:
            #m += pulp.lpSum(x2[r][k][t] for r in rolling2) <= 1, f"Stage2_SingleResourcePerCampaign_{k}_{t}"
    for k in campaigns:
        for t in days_horizon:
            # Объём, который можно прокатать к этому дню на 2 этапе — это сумма всего выплавленного К6 на 1 этапе с учетом времени (охлаждение)
            produced = pulp.lpSum(x2[r][k][tau]*prod_rate[(r,k)] for r in rolling2 for tau in days_horizon if tau<=t)
            available = pulp.lpSum(
                x1[r1][k][tau]*prod_rate[(r1,k)]
                for r1 in rolling1 for tau in days_horizon
                if tau + cooling_time[k] <= t
            )
            m += produced <= available, f"Stage2_Cooling_{k}_{t}"


    # 2.3 Ограничение: учёт охлаждения продукции между этапами
    # ("Макс. длительность хранения НЗП (опционально, на будущее).")
    for r in rolling2:
        for k in campaigns:
            for t in days_horizon:
                produced = pulp.lpSum(x2[r][k][tau]*prod_rate[(r,k)] for tau in days_horizon if tau<=t)
                available = pulp.lpSum(
                    x1[r1][k][tau]*prod_rate[(r1,k)]
                    for r1 in rolling1 for tau in days_horizon
                    if tau + cooling_time[k] <= t
                )
                m += produced <= available, f"Stage2_Cooling_{r}_{k}_{t}"

    # 2.4 Ограничение: фиксация смены кампании (см. 1.2)
    for r in rolling2:
        for k1 in campaigns:
            for k2 in campaigns:
                if k1 == k2: continue
                for t in days_horizon[:-1]:
                    m += y2[r][k1][k2][t] >= x2[r][k1][t] + x2[r][k2][t+1] - 1, \
                         f"Stage2_Reconf_{r}_{k1}_to_{k2}_{t}"

    # 2.5 Ограничение: агрегат считается используемым (см. 1.3)
    for r in rolling2:
        total_act2 = pulp.lpSum(x2[r][k][t] for k in campaigns for t in days_horizon)
        m += u2[r] <= total_act2, f"Stage2_UseUpper_{r}"
        m += u2[r] >= total_act2/len(days_horizon), f"Stage2_UseLower_{r}"

    # 2.6 Ограничение: ремонты
    # ("Плановые простои: интервалы времени, когда запуск кампаний запрещен.")
    for r in rolling2:
        for t in repairs.get(r, []):
            for k in campaigns:
                m += x2[r][k][t] == 0, f"Stage2_Repair_{r}_{t}_{k}"

    # 2.7 Ограничение: работа запрещена в день перевалки (см. 1.6)
    for r in rolling2:
        for t in days_horizon:
            for k in campaigns:
                m += x2[r][k][t] <= 1 - z2[r][t], f"Stage2_NoJobOnReconf_{r}_{k}_{t}"

    # 2.8 Ограничение: пометки перевалки (см. 1.7)
    for r in rolling2:
        for t in days_horizon[1:]:
            for k1 in campaigns:
                for k2 in campaigns:
                    if k1 == k2: continue
                    days_req = int(reconf_matrix[r][(k1,k2)] / 24)
                    for d in range(1, days_req+1):
                        if (t+d) in days_horizon:
                            m += z2[r][t+d] >= y2[r][k1][k2][t], \
                                 f"Stage2_TagReconf_{r}_{k1}_{k2}_at_{t}_d{d}"

    # 2.8.1 Ограничение: нельзя переваливать в дни ремонта (см. 1.8)
    for r in rolling2:
        for t in repairs.get(r, []):
            m += z2[r][t] == 0, f"Stage2_NoReconfOnRepair_{r}_{t}"

    # 2.9 Ограничение: запрет “нулевых” дней между двумя рабочими днями (см. 1.9)
    for r in rolling2:
        for idx in range(1, len(days_horizon)-1):
            t_prev = days_horizon[idx-1]
            t      = days_horizon[idx]
            t_next = days_horizon[idx+1]
            # пропускаем ремонты
            if t in repairs.get(r, []) or t_prev in repairs.get(r, []) or t_next in repairs.get(r, []):
                continue
            left  = pulp.lpSum(x2[r][k][t_prev] for k in campaigns)
            right = pulp.lpSum(x2[r][k][t_next] for k in campaigns)
            # если были работы в t-1 и в t+1, то либо перевалка в t, либо ремонт
            m += left + right <= z2[r][t] + 1, f"Stage2_NoIdleBetween_{r}_{t}"

    # ----------------------------
    # Этап 3: прокатка (аналогично)
    # ----------------------------
    x3 = pulp.LpVariable.dicts('x3', (rolling3, campaigns, days_horizon), cat='Binary')
    y3 = pulp.LpVariable.dicts('y3', (rolling3, campaigns, campaigns, days_horizon[:-1]), cat='Binary')
    u3 = pulp.LpVariable.dicts('u3', rolling3, cat='Binary')
    z3 = pulp.LpVariable.dicts('z3', (rolling3, days_horizon), cat='Binary')

    # 3.1 Ограничение: баланс между этапами (см. 2.1)
    for k in campaigns:
        for t in days_horizon:
            avail2 = pulp.lpSum(
                x2[r][k][tau]*prod_rate[(r,k)]
                for r in rolling2 for tau in days_horizon
                if tau + cooling_time[k] <= t
            )
            used3 = pulp.lpSum(x3[r][k][tau]*prod_rate[(r,k)] for r in rolling3 for tau in days_horizon if tau<=t)
            m += used3 <= avail2, f"Stage3_MaterialBalance_{k}_{t}"

    # 3.2 Ограничение: один агрегат — одна кампания в день (см. 1.1)
    for r in rolling3:
        for t in days_horizon:
            m += pulp.lpSum(x3[r][k][t] for k in campaigns) <= 1, f"Stage3_OneJob_{r}_{t}"

    # 3.3 Ограничение: фиксация смены кампании (см. 1.2)
    for r in rolling3:
        for k1 in campaigns:
            for k2 in campaigns:
                if k1 == k2: continue
                for t in days_horizon[:-1]:
                    m += y3[r][k1][k2][t] >= x3[r][k1][t] + x3[r][k2][t+1] - 1, \
                         f"Stage3_Reconf_{r}_{k1}_to_{k2}_{t}"

    # 3.4 Ограничение: агрегат считается используемым (см. 1.3)
    for r in rolling3:
        total_act3 = pulp.lpSum(x3[r][k][t] for k in campaigns for t in days_horizon)
        m += u3[r] <= total_act3, f"Stage3_UseUpper_{r}"
        m += u3[r] >= total_act3/len(days_horizon), f"Stage3_UseLower_{r}"

    # 3.5 Ограничение: ремонты (см. 2.6)
    for r in rolling3:
        for t in repairs.get(r, []):
            for k in campaigns:
                m += x3[r][k][t] == 0, f"Stage3_Repair_{r}_{t}_{k}"

    # 3.6 Ограничение: работа запрещена в день перевалки (см. 1.6)
    for r in rolling3:
        for t in days_horizon:
            for k in campaigns:
                m += x3[r][k][t] <= 1 - z3[r][t], f"Stage3_NoJobOnReconf_{r}_{k}_{t}"

    # 3.7 Ограничение: метки перевалки (см. 1.7)
    for r in rolling3:
        for t in days_horizon[1:]:
            for k1 in campaigns:
                for k2 in campaigns:
                    if k1 == k2: continue
                    days_req = int(reconf_matrix[r][(k1,k2)] // 24)
                    for d in range(1, days_req+1):
                        if (t+d) in days_horizon:
                            m += z3[r][t+d] >= y3[r][k1][k2][t], \
                                 f"Stage3_TagReconf_{r}_{k1}_{k2}_at_{t}_d{d}"

    # 3.8 Ограничение: нельзя переваливать в дни ремонта (см. 1.8)
    for r in rolling3:
        for t in repairs.get(r, []):
            m += z3[r][t] == 0, f"Stage3_NoReconfOnRepair_{r}_{t}"

    # 3.9 Ограничение: запрет “нулевых” дней между двумя рабочими днями (см. 1.9)
    for r in rolling3:
        for idx in range(1, len(days_horizon)-1):
            t_prev = days_horizon[idx-1]
            t      = days_horizon[idx]
            t_next = days_horizon[idx+1]
            # пропускаем ремонты
            if t in repairs.get(r, []) or t_prev in repairs.get(r, []) or t_next in repairs.get(r, []):
                continue
            left  = pulp.lpSum(x3[r][k][t_prev] for k in campaigns)
            right = pulp.lpSum(x3[r][k][t_next] for k in campaigns)
            # если были работы в t-1 и в t+1, то либо перевалка в t, либо ремонт
            m += left + right <= z3[r][t] + 1, f"Stage3_NoIdleBetween_{r}_{t}"

    # ----------------------------
    # Целевая функция
    # ----------------------------
    obj_prod1 = pulp.lpSum(x1[r][k][t]*prod_rate[(r,k)]
                           for r in rolling1 for k in campaigns for t in days_horizon)
    obj_prod2 = pulp.lpSum(x2[r][k][t]*prod_rate[(r,k)]
                           for r in rolling2 for k in campaigns for t in days_horizon)
    obj_prod3 = pulp.lpSum(x3[r][k][t]*prod_rate[(r,k)]
                           for r in rolling3 for k in campaigns for t in days_horizon)

    obj_conf1 = pulp.lpSum(y1[r][k1][k2][t]*reconf_matrix[r][(k1,k2)]
                           for r in rolling1 for k1 in campaigns for k2 in campaigns if k1!=k2 for t in days_horizon[:-1])
    obj_conf2 = pulp.lpSum(y2[r][k1][k2][t]*reconf_matrix[r][(k1,k2)]
                           for r in rolling2 for k1 in campaigns for k2 in campaigns if k1!=k2 for t in days_horizon[:-1])
    obj_conf3 = pulp.lpSum(y3[r][k1][k2][t]*reconf_matrix[r][(k1,k2)]
                           for r in rolling3 for k1 in campaigns for k2 in campaigns if k1!=k2 for t in days_horizon[:-1])

    obj_use1 = pulp.lpSum(u1[r] for r in rolling1)
    obj_use2 = pulp.lpSum(u2[r] for r in rolling2)
    obj_use3 = pulp.lpSum(u3[r] for r in rolling3)

    # ("Критерии оптимизации: ... минимум переналадок / максимум производства / минимум задействованных агрегатов ...")
    m += (obj_prod1 + obj_prod2 + obj_prod3
          - PEN * (obj_conf1 + obj_conf2 + obj_conf3)
          - (obj_use1 + obj_use2 + obj_use3))

    return m, x1, x2, x3, y1, y2, y3, u1, u2, u3, z1, z2, z3
