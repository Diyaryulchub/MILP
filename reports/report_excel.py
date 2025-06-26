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
    rolling1: list[str],
    rolling1_schedule: dict[tuple[str, int], str],
    rolling1_tonnage: dict[tuple[str, int], float],
    rolling1_reconf: dict[str, float],
    rolling2: list[str],
    rolling2_schedule: dict[tuple[str, int], str],
    rolling2_tonnage: dict[tuple[str, int], float],
    rolling2_reconf: dict[str, float],
    rolling3: list[str],
    rolling3_schedule: dict[tuple[str, int], str],
    rolling3_tonnage: dict[tuple[str, int], float],
    rolling3_reconf: dict[str, float],
    rolled_total_3: dict[str, float],
):
    """
    Формирует полный отчет в формате Excel:
      — параметры задачи,
      — ограничения (из технического задания),
      — метрики и рекомендованный горизонт,
      — НСИ по выплавке (этап 1),
      — оптимизированная выплавка (этап 1),
      — прокатка этапов 2 и 3,
      — итоги по прокатке.
    """

    # Цвета для кампаний
    campaign_colors = {
        'K1': '#FFA07A',  # светло-красный
        'K2': '#90EE90',  # светло-зелёный
        'K3': '#ADD8E6',  # светло-синий
        'K4': '#FFFF99',  # светло-жёлтый
        'K5': '#FFB6C1',  # розовый
        'K6': '#C0C0C0',  # серый
    }
    formats = {}

    output_dir = os.path.dirname(path) or "output"
    os.makedirs(output_dir, exist_ok=True)
    full_path = os.path.join(output_dir, os.path.basename(path))

    with pd.ExcelWriter(full_path, engine='xlsxwriter') as writer:
        sheet = writer.book.add_worksheet("Report")
        writer.sheets["Report"] = sheet
        row = 0

        # Параметры задачи
        sheet.write(row, 0, "ПАРАМЕТРЫ ЗАДАЧИ:"); row += 1
        sheet.write(row, 0, "prod_rate (этапы 1/2/3):");    sheet.write(row, 1, str(prod_rate));  row += 1
        sheet.write(row, 0, "cooling_time:");               sheet.write(row, 1, str(cooling_time)); row += 1
        sheet.write(row, 0, "nsi_schedule (НСИ выплавки):");sheet.write(row, 1, str(nsi_schedule));row += 1
        sheet.write(row, 0, "total_nsi (объемы НСИ):");     sheet.write(row, 1, str(total_nsi));   row += 2

        # Метрики решения
        sheet.write(row, 0, "МЕТРИКИ:"); row += 1
        for name, value in metrics.items():
            sheet.write(row, 0, name); sheet.write(row, 1, value); row += 1
        row += 1

        # Нормативно-справочная информация (НСИ) по выплавке (этап 1)
        sheet.write(row, 0, "НСИ: выплавка"); row += 1

        sheet.write(row, 0, "Код кампании")
        for i, d in enumerate(days):
            code = nsi_schedule.get(d, ("", ""))[0]
            sheet.write(row, 1 + i, code)
        row += 1

        sheet.write(row, 0, "Тонны")
        for i, d in enumerate(days):
            ton = nsi_schedule[d][1] if d in nsi_schedule else ""
            sheet.write(row, 1 + i, ton)
        row += 2

        # Выплавка этап 1 (цвет для кодов)
        sheet.write(row, 0, "Выплавка (этап 1)"); row += 1
        sheet.write(row, 0, "День")
        for i, d in enumerate(days):
            sheet.write(row, 1 + i, d)
        row += 1
        for r in rolling1:
            sheet.write(row, 0, f"{r} (код)")
            for i, d in enumerate(days):
                val = rolling1_schedule.get((r, d), "")
                if val in campaign_colors:
                    if val not in formats:
                        formats[val] = writer.book.add_format({'bg_color': campaign_colors[val]})
                    sheet.write(row, 1 + i, val, formats[val])
                else:
                    sheet.write(row, 1 + i, val if val in ["РЕМОНТ", "ПЕРЕВАЛКА"] else val)
            row += 1
            sheet.write(row, 0, f"{r} (т)")
            for i, d in enumerate(days):
                val = rolling1_schedule.get((r, d), "")
                ton = 0.0 if val in ["РЕМОНТ", "ПЕРЕВАЛКА"] else rolling1_tonnage.get((r, d), 0.0)
                sheet.write(row, 1 + i, ton)
            row += 1
            days_reconf = math.ceil(rolling1_reconf.get(r, 0) / cfg.hours_per_day)
            sheet.write(row, 0, f"{days_reconf} дн перевалок")
            row += 1
        row += 1

        # Прокатка этапа 2 (цвет для кодов)
        for r in rolling2:
            sheet.write(row, 0, f"{r} (код)")
            for i, d in enumerate(days):
                val = rolling2_schedule.get((r, d), "")
                if val in campaign_colors:
                    if val not in formats:
                        formats[val] = writer.book.add_format({'bg_color': campaign_colors[val]})
                    sheet.write(row, 1 + i, val, formats[val])
                else:
                    sheet.write(row, 1 + i, val if val in ["РЕМОНТ", "ПЕРЕВАЛКА"] else val)
            row += 1
            sheet.write(row, 0, f"{r} (т)")
            for i, d in enumerate(days):
                val = rolling2_schedule.get((r, d), "")
                ton = 0.0 if val in ["РЕМОНТ", "ПЕРЕВАЛКА"] else rolling2_tonnage.get((r, d), 0.0)
                sheet.write(row, 1 + i, ton)
            row += 1
            days_reconf = math.ceil(rolling2_reconf.get(r, 0) / cfg.hours_per_day)
            sheet.write(row, 0, f"{days_reconf} дн перевалок")
            row += 1
        row += 1

        # Прокатка этапа 3 (цвет для кодов)
        for r in rolling3:
            sheet.write(row, 0, f"{r} (код)")
            for i, d in enumerate(days):
                val = rolling3_schedule.get((r, d), "")
                if val in campaign_colors:
                    if val not in formats:
                        formats[val] = writer.book.add_format({'bg_color': campaign_colors[val]})
                    sheet.write(row, 1 + i, val, formats[val])
                else:
                    sheet.write(row, 1 + i, val if val in ["РЕМОНТ", "ПЕРЕВАЛКА"] else val)
            row += 1
            sheet.write(row, 0, f"{r} (т)")
            for i, d in enumerate(days):
                val = rolling3_schedule.get((r, d), "")
                ton = 0.0 if val in ["РЕМОНТ", "ПЕРЕВАЛКА"] else rolling3_tonnage.get((r, d), 0.0)
                sheet.write(row, 1 + i, ton)
            row += 1
            days_reconf = math.ceil(rolling3_reconf.get(r, 0) / cfg.hours_per_day)
            sheet.write(row, 0, f"{days_reconf} дн перевалок")
            row += 1
        row += 1

        # Ограничения (из ТЗ)
        sheet.write(row, 0, "ОГРАНИЧЕНИЯ:"); row += 1
        for c in [
            "Горизонт планирования: до выполнения всех кампаний.",
            "Приоритеты кампаний: нестрогие (можно игнорировать при необходимости).",
            "Минимальная длительность кампании: равна длительности партии (рассчитывается как объем партии / производительность).",
            "Ресурсы переналадки: не ограничены.",
            "Калибровки/ТО: учтены в плановых простоях/переналадках.",
            "Точность времени: целочисленные интервалы (минуты/часы).",
            "Утилизация НЗП: продукты из НЗП могут использоваться в нескольких параллельных кампаниях.",
            "Параллельные агрегаты: кампании выполняются независимо (синхронизация не требуется)."
        ]:
            sheet.write(row, 0, c)
            row += 1
        row += 1

    print(f"Отчет сохранён в {full_path}")
