def group_events_by_days(schedule_by_hour, prod_rate, reconf_h, days, hours_per_day, resource):
    """
    Группирует события по дням:
      - каждое событие (кампания/перевалка) режется на границе 24ч,
      - если процесс не умещается, остаток переносится на следующий день.
    Возвращает: List[List[dict]]
        (список дней, в каждом — список событий-блоков {"type":..., "code":..., "hours":..., "tons":...})
    """
    events = []
    cur_campaign = None
    left = 0
    block_hours = 0
    block_tons = 0.0
    h_global = 1
    total_hours = hours_per_day * len(days)
    day = []
    d = 0
    while h_global <= total_hours:
        campaign = schedule_by_hour.get((resource, h_global), "")
        if campaign == "":
            # Простой/ничего — если был открытый блок, сохраняем и сбрасываем
            if block_hours > 0:
                # фиксируем блок (кампания)
                day.append({"type": "campaign", "code": cur_campaign, "hours": block_hours, "tons": block_tons})
                block_hours = 0
                block_tons = 0.0
            cur_campaign = None
        else:
            # Кампания сменилась?
            if campaign != cur_campaign:
                # Завершаем старую кампанию (если была)
                if block_hours > 0:
                    day.append({"type": "campaign", "code": cur_campaign, "hours": block_hours, "tons": block_tons})
                # Если не первое событие — между кампаниями перевалка!
                if cur_campaign is not None:
                    day.append({"type": "reconf", "hours": reconf_h[resource]})
                    # продвигаем время на длительность перевалки (по часам!)
                    h_global += reconf_h[resource]
                    # перескочили ли границу дня?
                    while h_global > (d+1)*hours_per_day:
                        # закрываем день и переносим остаток перевалки в следующий
                        hours_in_day = (d+1)*hours_per_day - (h_global - reconf_h[resource]) + 1
                        if hours_in_day > 0:
                            day.append({"type": "reconf", "hours": hours_in_day})
                        events.append(day)
                        day = []
                        d += 1
                        reconf_left = reconf_h[resource] - hours_in_day
                        if reconf_left > 0:
                            day.append({"type": "reconf", "hours": reconf_left})
                        h_global = d*hours_per_day + 1 + reconf_left
                    # после перевалки всё сброшено
                cur_campaign = campaign
                block_hours = 0
                block_tons = 0.0
            # накапливаем часы и тоннаж кампании
            block_hours += 1
            block_tons += prod_rate[(resource, campaign)] / 24.0

        # проверяем границу дня
        if (h_global % hours_per_day) == 0:
            if block_hours > 0:
                day.append({"type": "campaign", "code": cur_campaign, "hours": block_hours, "tons": block_tons})
                block_hours = 0
                block_tons = 0.0
            events.append(day)
            day = []
            d += 1
        h_global += 1
    # добиваем последнюю часть, если осталась
    if day:
        if block_hours > 0:
            day.append({"type": "campaign", "code": cur_campaign, "hours": block_hours, "tons": block_tons})
        events.append(day)
    return events
