# report_excel.py

import math
import os
import pandas as pd
import config.settings as cfg

def write_excel_report(
    path: str,
    prod_rate: dict[tuple[str, str], float],
    cooling_time: dict[str, int],
    nsi_schedule: dict[int, tuple[str, float]],
    total_nsi: dict[str, float],
    metrics: dict[str, float],
    days: list[int],
    campaigns: list[str],
    stage_aggs: dict[int, list[str]],
    schedules: dict[int, dict[tuple[str, int], str]],
    tonnages: dict[int, dict[tuple[str, int], float]],
    reconfs: dict[int, dict[str, float]],
    rolled_total: dict[str, float],
):
    """
    Формирует полный отчёт в Excel:
      — параметры задачи,
      — метрики,
      — НСИ (этап 1),
      — динамические расписания всех этапов,
      — итоговый тоннаж последнего этапа.
    """
    # Цвета кампаний
    campaign_colors = {
        'K1': '#FFA07A', 'K2': '#90EE90', 'K3': '#ADD8E6',
        'K4': '#FFFF99', 'K5': '#FFB6C1', 'K6': '#C0C0C0',
    }
    formats: dict[str, any] = {}

    os.makedirs(os.path.dirname(path) or "output", exist_ok=True)
    with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
        book  = writer.book
        sheet = book.add_worksheet("Report")
        writer.sheets["Report"] = sheet
        row = 0

        # Параметры
        sheet.write(row, 0, "ПАРАМЕТРЫ ЗАДАЧИ:"); row += 1
        sheet.write(row, 0, "prod_rate:");    sheet.write(row, 1, str(prod_rate));    row += 1
        sheet.write(row, 0, "cooling_time:"); sheet.write(row, 1, str(cooling_time)); row += 1
        sheet.write(row, 0, "total_nsi:");   sheet.write(row, 1, str(total_nsi));   row += 2

        # Метрики
        sheet.write(row, 0, "МЕТРИКИ:"); row += 1
        for name, val in metrics.items():
            sheet.write(row, 0, name); sheet.write(row, 1, val); row += 1
        row += 1

        # НСИ (этап 1)
        sheet.write(row, 0, "НСИ: выплавка"); row += 1
        sheet.write(row, 0, "День")
        for i, d in enumerate(days):
            sheet.write(row, 1 + i, d)
        row += 1
        sheet.write(row, 0, "Код")
        for i, d in enumerate(days):
            sheet.write(row, 1 + i, nsi_schedule.get(d, ("", 0.0))[0])
        row += 1
        sheet.write(row, 0, "Тонны")
        for i, d in enumerate(days):
            sheet.write(row, 1 + i, nsi_schedule.get(d, ("", 0.0))[1])
        row += 2

        # По каждой стадии
        for stage in sorted(stage_aggs):
            aggs = stage_aggs[stage]
            sheet.write(row, 0, f"Этап {stage}"); row += 1

            # Заголовок дней
            sheet.write(row, 0, "День")
            for i, d in enumerate(days):
                sheet.write(row, 1 + i, d)
            row += 1

            # Расписание и тоннаж для каждого агрегата
            for r in aggs:
                # — коды / перевалка
                sheet.write(row, 0, f"{r} (код)")
                for i, d in enumerate(days):
                    val = schedules[stage].get((r, d), "")
                    if val in campaign_colors:
                        if val not in formats:
                            formats[val] = book.add_format({'bg_color': campaign_colors[val]})
                        sheet.write(row, 1 + i, val, formats[val])
                    else:
                        sheet.write(row, 1 + i, val)
                row += 1

                # — тоннаж
                sheet.write(row, 0, f"{r} (т)")
                for i, d in enumerate(days):
                    sheet.write(row, 1 + i, tonnages[stage].get((r, d), 0.0))
                row += 1

                # — дни перевалок
                days_reconf = math.ceil(reconfs[stage].get(r, 0.0) / cfg.hours_per_day)
                sheet.write(row, 0, f"{days_reconf} дн перевалок")
                row += 1

            # Итоговый тоннаж последнего этапа
            if stage == max(stage_aggs):
                row += 1
                sheet.write(row, 0, "Итоговый тоннаж (последний этап):")
                for i, k in enumerate(campaigns):
                    sheet.write(row, 1 + i, rolled_total.get(k, 0.0))
                row += 2
            else:
                row += 1

        # Ограничения (ТЗ)
        sheet.write(row, 0, "ОГРАНИЧЕНИЯ (из ТЗ):"); row += 1
        for text in [
            "Одна кампания на агрегат в день.",
            "Ремонты блокируют работу и перевалку.",
            "Смена кампании → перевалка по матрице.",
            "Запрет работы в день перевалки.",
            "Запрет «нулевых» дней между рабочими без перевалки.",
            "Баланс материалов с учётом охлаждения."
        ]:
            sheet.write(row, 0, text)
            row += 1

    print(f"Отчёт сохранён: {path}")
