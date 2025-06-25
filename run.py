# run.py

import os
import time

from solvers.solve import solve_main    # если у вас solve.py лежит в папке solvers
import config.settings as cfg
from reports.report_excel import write_excel_report

def run_and_report():
    print("[INFO] === START run_and_report ===")
    t0 = time.time()

    # 1) Решаем всю трехступенчатую модель
    result = solve_main()
    status_str         = result["status_str"]
    days               = result["days"]
    rolled_total_3     = result["rolled_total_3"]
    enough             = result["enough"]
    #recommended_days   = result["recommended_days"]
    rolling1_schedule  = result["rolling1_schedule"]
    rolling1_tonnage   = result["rolling1_tonnage"]
    rolling1_reconf    = result["rolling1_reconf"]
    rolling2_schedule  = result["rolling2_schedule"]
    rolling2_tonnage   = result["rolling2_tonnage"]
    rolling2_reconf    = result["rolling2_reconf"]
    rolling3_schedule  = result["rolling3_schedule"]
    rolling3_tonnage   = result["rolling3_tonnage"]
    rolling3_reconf    = result["rolling3_reconf"]
    metrics            = result["metrics"]

    print(f"[DEBUG] Статус={status_str}, горизонт={days} дн.")

    # 2) Записываем отчет в Excel
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
        #recommended_days=recommended_days,
        days=cfg.days,
        campaigns=cfg.campaigns,
        rolling1=cfg.rolling1,
        rolling1_schedule=rolling1_schedule,
        rolling1_tonnage=rolling1_tonnage,
        rolling1_reconf=rolling1_reconf,
        rolling2=cfg.rolling2,
        rolling2_schedule=rolling2_schedule,
        rolling2_tonnage=rolling2_tonnage,
        rolling2_reconf=rolling2_reconf,
        rolling3=cfg.rolling3,
        rolling3_schedule=rolling3_schedule,
        rolling3_tonnage=rolling3_tonnage,
        rolling3_reconf=rolling3_reconf,
        rolled_total_3=rolled_total_3
    )
    print(f"[INFO] Отчет сохранён в {path}")
    print(f"[INFO] TOTAL: {time.time() - t0:.2f}s")

if __name__ == "__main__":
    run_and_report()
