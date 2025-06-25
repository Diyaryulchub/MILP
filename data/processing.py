# Здесь почти ничего не используется. Зачатки для перехода в часы

from config.settings import (
    nsi_schedule,
    campaigns,
    prod_rate,
    cooling_time,
    reconf_h,
    hours_per_day,
    reconf_d
)

def build_schedule_h(
    schedule_example: dict[int, tuple[str, float]]
) -> dict[int, tuple[str, float]]:
    """
    Переводит дневной план schedule_example в почасовой.
    Возвращает словарь: {hour_index: (campaign, tons_per_hour)}.
    """
    schedule_h: dict[int, tuple[str, float]] = {}
    for day, (camp, v_day) in schedule_example.items():
        v_hr = v_day / hours_per_day
        start = (day - 1) * hours_per_day + 1
        end   = day * hours_per_day
        for h in range(start, end + 1):
            schedule_h[h] = (camp, v_hr)
    return schedule_h

def compute_total_stage1(
    schedule_h: dict[int, tuple[str, float]],
    campaigns: list[str]
) -> dict[str, float]:
    """
    Считает, сколько тонн всего поступило на этапе 1 по каждой кампании.
    """
    total = {k: 0.0 for k in campaigns}
    for _, (camp, v_hr) in schedule_h.items():
        total[camp] += v_hr
    return total

def compute_prod_rate_h(
    prod_rate_per_day: dict[tuple[str, str], float],
    hours_per_day: int
) -> dict[tuple[str, str], float]:
    """
    Переводит производительность из т/день в т/час.
    """
    return {k: v / hours_per_day for k, v in prod_rate_per_day.items()}

def compute_cooling_time_h(
    cooling_days: dict[str, int],
    hours_per_day: int
) -> dict[str, int]:
    """
    Переводит время охлаждения из дней в часовые шаги.
    """
    return {camp: days * hours_per_day for camp, days in cooling_days.items()}

def build_reconf_pair(
    campaigns: list[str],
    reconfig_duration: int
) -> dict[tuple[str, str], int]:
    """
    Строит словарь переналадок между разными кампаниями:
    (camp1, camp2) → длительность переналадки в часах.
    """
    return {
        (k1, k2): reconfig_duration
        for k1 in campaigns
        for k2 in campaigns
        if k1 != k2
    }

def group_events_by_days(
    schedule_by_hour: dict[tuple[str, int], str],
    prod_rate: dict[tuple[str, str], float],
    reconf_h: dict[str, int],
    days: list[int],
    hours_per_day: int,
    resource: str
) -> list[list[dict]]:
    """
    Группирует почасовое расписание по дням, разбивает на блоки
    «кампания» и «переналадка», считает на каждом блоке часы и тонны.
    Возвращает список дней, каждый день — список блоков вида
      {"type":"campaign","code":..., "hours":..., "tons":...}
    или {"type":"reconf","hours":...}.
    """
    events: list[list[dict]] = []
    total_hours = hours_per_day * len(days)
    h_global = 1
    day: list[dict] = []
    block: dict | None = None

    def push_block():
        nonlocal block, day
        if block:
            day.append(block)
            block = None

    current_campaign: str | None = None

    while h_global <= total_hours:
        # код кампании в этот час
        campaign = schedule_by_hour.get((resource, h_global), "")
        # если старт новой кампании (или смена)
        if campaign and campaign != current_campaign:
            push_block()
            # вставляем переналадку перед новой кампанией
            if current_campaign is not None:
                left_reconf = reconf_h.get(resource, 0)
                while left_reconf > 0:
                    used = sum(e["hours"] for e in day) if day else 0
                    avail = hours_per_day - used
                    chunk = min(avail, left_reconf)
                    if chunk == 0:
                        events.append(day)
                        day = []
                        chunk = min(hours_per_day, left_reconf)
                    day.append({"type": "reconf", "hours": chunk})
                    left_reconf -= chunk
            current_campaign = campaign
            block = {"type": "campaign", "code": campaign, "hours": 0, "tons": 0.0}

        # если в этот час идёт кампания — наращиваем блок
        if campaign:
            if not block:
                block = {"type": "campaign", "code": campaign, "hours": 0, "tons": 0.0}
            block["hours"] += 1
            block["tons"]  += prod_rate[(resource, campaign)] / hours_per_day
        else:
            # простой — «закрываем» предыдущий блок
            push_block()

        # на границе дня сохраняем накопленные блоки
        if h_global % hours_per_day == 0:
            push_block()
            if day:
                events.append(day)
            day = []

        h_global += 1

    # после цикла — финальные блоки
    push_block()
    if day:
        events.append(day)

    return events

# === Глобальные вычисления ===
schedule_h     = build_schedule_h(nsi_schedule)
total_stage1  = compute_total_stage1(schedule_h, campaigns)
prod_rate_h    = compute_prod_rate_h(prod_rate, hours_per_day)
cooling_time_h = compute_cooling_time_h(cooling_time, hours_per_day)
reconf_pairs   = build_reconf_pair(campaigns, min(reconf_h.values()))

def count_reconfigurations(schedule: list[str], reconf_h: dict[str, float]) -> float:
    """
    Считает суммарное время переналадок для расписания кампаний по дням,
    пропуская «нулевые» дни и не считая последнюю висячую кампанию.

    :param schedule: список длины N, где schedule[d] = имя кампании в день d или "" для простоя
    :param reconf_h: словарь, дающий время переналадки для каждой кампании
    :return: суммарное время переналадок
    """
    total_reconf = 0.0
    N = len(schedule)

    for i, camp in enumerate(schedule):
        if not camp:
            continue

        # ищем следующий ненулевой день
        j = i + 1
        while j < N and schedule[j] == "":
            j += 1

        # если после camp всё-таки нашлась другая кампания — считаем переналадку
        if j < N:
            total_reconf += reconf_h.get(camp, 0.0)

    return total_reconf