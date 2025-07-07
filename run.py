# run.py

import os
import time

import config.settings as cfg
from solvers.solve import solve_main
from reports.report_excel import write_excel_report

def run_and_report():
    print("[INFO] === START run_and_report ===")
    t0 = time.time()

    # 1) Решаем модель
    result = solve_main()
    status_str    = result["status_str"]
    days          = result["days"]
    rolled_total  = result["rolled_total_3"]  # или "rolled_total", если вы унифицировали
    enough        = result["enough"]
    schedules     = result["schedules"]
    tonnages      = result["tonnages"]
    reconfs       = result["reconfs"]
    metrics       = result["metrics"]

    print(f"[DEBUG] Статус={status_str}, days={days}")

    # 2) Записываем отчёт
    out_dir = "output"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "report_full.xlsx")

    write_excel_report(
        path=path,
        prod_rate=cfg.prod_rate,
        cooling_time=cfg.cooling_time,
        nsi_schedule=cfg.nsi_schedule,
        total_nsi=cfg.total_nsi,
        metrics=metrics,
        days=days,
        campaigns=cfg.campaigns,
        stage_aggs=cfg.stage_aggs,
        schedules=schedules,
        tonnages=tonnages,
        reconfs=reconfs,
        rolled_total=rolled_total
    )

    print(f"[INFO] Отчёт сохранён в {path}")
    print(f"[INFO] TOTAL TIME: {time.time() - t0:.2f}s")

if __name__ == "__main__":
    run_and_report()
