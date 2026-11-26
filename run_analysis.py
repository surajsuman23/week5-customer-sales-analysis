"""
Week 5 - Customer Sales Analysis: full pipeline in one command.

    python run_analysis.py              # uses files in this folder
    python run_analysis.py --out build  # write outputs somewhere else

Steps: load -> clean -> build customer_data.csv -> merge -> analyse -> charts -> tables -> PDF report
"""

import argparse
import logging
import sys
from pathlib import Path

from src import analysis, charts, data_prep, insights
from src.pdf_report import build_pdf

BASE_DIR = Path(__file__).resolve().parent
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger("matplotlib").setLevel(logging.WARNING)
log = logging.getLogger("week5")


def load_and_prepare(base_dir=BASE_DIR, rebuild_customers=False):
    """Load both datasets, clean them, create/read customer_data.csv and merge."""
    base_dir = Path(base_dir)
    sales_raw = data_prep.load_csv(base_dir / "sales_data.csv", data_prep.SALES_COLUMNS)
    churn_raw = data_prep.load_csv(base_dir / "data" / "customer_churn.csv", data_prep.CHURN_COLUMNS)
    sales, sales_log = data_prep.clean_sales(sales_raw)
    churn = data_prep.clean_churn(churn_raw)

    customers_path = base_dir / "customer_data.csv"
    if rebuild_customers or not customers_path.exists():
        customers = data_prep.build_customer_data(churn, sales["Customer_ID"])
        customers.to_csv(customers_path, index=False)
        log.info("Wrote %s (%d customers)", customers_path.name, len(customers))
    customers = data_prep.load_csv(customers_path, ["Customer_ID"] + data_prep.PROFILE_COLUMNS)
    merged, unmatched = data_prep.merge_sales_customers(sales, customers)
    log.info("Sales: %d rows | churn: %d customers | merged: %d rows (%d unmatched)",
             len(sales), len(churn), len(merged), unmatched)
    return {"sales": sales, "sales_log": sales_log, "churn": churn,
            "customers": customers, "merged": merged, "unmatched": unmatched}


def save_tables(results, out_dir):
    """Save the main tables as CSV so they can be opened in Excel."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = ["customer_value", "region", "monthly", "product", "weekday", "region_product",
             "month_product_units", "affinity", "churn_contract", "churn_tenure", "churn_payment",
             "contract_tenure", "merged_contract"]
    for name in names:
        results[name].to_csv(out_dir / f"{name}.csv")
    results["at_risk"].to_csv(out_dir / "at_risk_customers.csv", index=False)
    return out_dir


def print_summary(results):
    k, c = results["kpis"], results["churn_kpis"]
    print("\n" + "=" * 60)
    print("              CUSTOMER SALES ANALYSIS REPORT")
    print("=" * 60)
    print(f"Total Revenue       : {insights.rupees(k['total_revenue'])}")
    print(f"Total Customers     : {k['unique_customers']}")
    print(f"Average Order Value : {insights.rupees(k['avg_order_value'])}")
    top = results["customer_value"].iloc[0]
    print(f"Top Customer        : {results['customer_value'].index[0]} - {insights.rupees(top['Revenue'])}")
    print(f"Top-10 Share        : {results['top10_share']}%")
    print(f"Retention Rate      : {c['retention_rate_%']}% (churn {c['churn_rate_%']}%, 500 customers)")
    print("-" * 60)
    for line in insights.sales_insights(results) + insights.churn_insights(results):
        print(f" * {line}")
    print("=" * 60 + "\n")


def run(base_dir=BASE_DIR, out_dir=None):
    base_dir = Path(base_dir)
    out_dir = Path(out_dir) if out_dir else base_dir
    data = load_and_prepare(base_dir)
    results = analysis.run_all(data["sales"], data["churn"], data["merged"])
    chart_paths = charts.make_all(results, out_dir / "visualizations")
    save_tables(results, out_dir / "report_tables")
    pdf = build_pdf(results, chart_paths, out_dir / "analysis_report.pdf")
    log.info("Charts: %d | PDF: %s", len(chart_paths), pdf.name)
    print_summary(results)
    return {"data": data, "results": results, "charts": chart_paths, "pdf": pdf}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Week 5 customer sales analysis")
    parser.add_argument("--out", default=None, help="Output folder (default: project folder)")
    args = parser.parse_args()
    try:
        run(BASE_DIR, args.out)
    except (FileNotFoundError, data_prep.DataValidationError) as err:
        log.error(err)
        sys.exit(1)
