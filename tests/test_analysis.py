"""Tests for the Week 5 pipeline. Run from the project folder:  python -m pytest -v"""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import analysis, data_prep  # noqa: E402
import run_analysis  # noqa: E402

SALES_HEADER = "Date,Product,Quantity,Price,Customer_ID,Region,Total_Sales\n"


@pytest.fixture(scope="module")
def prepared():
    return run_analysis.load_and_prepare(ROOT)


@pytest.fixture(scope="module")
def results(prepared):
    return analysis.run_all(prepared["sales"], prepared["churn"], prepared["merged"])


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return path


# ---------------- Loading ----------------
def test_load_shapes(prepared):
    assert prepared["sales"].shape[0] == 100
    assert prepared["churn"].shape[0] == 500


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        data_prep.load_csv("nope.csv", data_prep.SALES_COLUMNS)


def test_missing_columns_raise(tmp_path):
    path = write(tmp_path, "bad.csv", "Date,Product\n2024-01-01,Phone\n")
    with pytest.raises(data_prep.DataValidationError, match="missing columns"):
        data_prep.load_csv(path, data_prep.SALES_COLUMNS)


# ---------------- Cleaning, strings, dates ----------------
def test_dirty_sales_are_cleaned(tmp_path):
    path = write(tmp_path, "dirty.csv", SALES_HEADER
                 + "2024-01-01, phone ,2,100, cust001 , east ,200\n"
                 + "2024-01-01, phone ,2,100, cust001 , east ,200\n"   # duplicate
                 + "2024-01-06,LAPTOP,3,50,CUST002,West,\n"            # missing total
                 + "bad-date,Tablet,1,80,CUST003,North,80\n"           # bad date
                 + "2024-01-07,Tablet,-2,80,CUST004,North,-160\n")     # negative qty
    df, log = data_prep.clean_sales(data_prep.load_csv(path, data_prep.SALES_COLUMNS))
    assert len(df) == 2
    assert log["duplicates_removed"] == 1 and log["totals_recomputed"] == 1
    assert set(df["Product"]) == {"Phone", "Laptop"}
    assert set(df["Customer_ID"]) == {"CUST001", "CUST002"}
    assert set(df["Region"]) == {"East", "West"}


def test_date_parts(prepared):
    s = prepared["sales"]
    first = s.iloc[0]
    assert (first["Year"], first["Month"], first["Day"], first["Weekday"]) == (2024, "2024-01", 1, "Monday")
    assert s.loc[s["Weekday"].isin(["Saturday", "Sunday"]), "Is_Weekend"].all()


def test_churn_helper_columns(prepared):
    c = prepared["churn"]
    assert c["Tenure_Band"].notna().all()
    assert (c["Fixed_Term"] == c["Contract"].isin(["One year", "Two year"])).all()


# ---------------- customer_data.csv + merge ----------------
def test_customer_data_keys(prepared):
    cust = prepared["customers"]
    assert cust["Customer_ID"].is_unique and len(cust) == 100
    assert cust["Customer_ID"].iloc[0] == "CUST001" and cust["Source_Profile_ID"].iloc[0] == "C00001"


def test_merge_keeps_every_order(prepared):
    assert len(prepared["merged"]) == len(prepared["sales"])
    assert prepared["unmatched"] == 0
    assert prepared["merged"]["Contract"].notna().all()


def test_build_customer_data_needs_enough_profiles(prepared):
    with pytest.raises(data_prep.DataValidationError):
        data_prep.build_customer_data(prepared["churn"].head(5), prepared["sales"]["Customer_ID"])


# ---------------- Aggregations & pivots ----------------
def test_group_totals_match(results):
    total = results["kpis"]["total_revenue"]
    assert total == 12_365_048
    for key in ["region", "monthly", "product", "weekday"]:
        assert results[key]["Revenue"].sum() == total
    assert results["region_product"].loc["Total", "Total"] == total


def test_top_customers(results):
    value = results["customer_value"]
    assert value.index[0] == "CUST016"
    assert value["Revenue"].is_monotonic_decreasing
    assert results["top10_share"] == pytest.approx(27.1)


def test_mom_growth(results):
    m = results["monthly"]
    expected = (m["Revenue"].iloc[1] / m["Revenue"].iloc[0] - 1) * 100
    assert m["MoM_Growth_%"].iloc[1] == pytest.approx(expected, abs=0.1)


def test_affinity_is_weighted_to_one(results, prepared):
    # Revenue-weighted average lift of each product across regions equals 1
    pivot = prepared["sales"].pivot_table(index="Region", columns="Product", values="Total_Sales", aggfunc="sum")
    weights = pivot.sum(axis=1) / pivot.values.sum()
    weighted = (results["affinity"].mul(weights, axis=0)).sum()
    assert weighted.round(1).eq(1.0).all()


# ---------------- Filters ----------------
def test_and_filter(results):
    hv = results["high_value"]
    assert (hv["Total_Sales"] >= 200_000).all() and hv["Region"].isin(["North", "South"]).all()


def test_or_filter(results):
    lb = results["laptop_or_bulk"]
    assert ((lb["Product"] == "Laptop") | (lb["Quantity"] >= 8)).all()


def test_at_risk_filter(results):
    risk = results["at_risk"]
    assert (risk["Churn"] == 0).all()
    assert ((risk["Tenure"] <= 12) | ((risk["Contract"] == "Month-to-month") & (risk["Tenure"] <= 24))).all()


# ---------------- Churn ----------------
def test_churn_kpis(results):
    c = results["churn_kpis"]
    assert c["churned"] == 53 and c["churn_rate_%"] == 10.6 and c["retention_rate_%"] == 89.4
    assert c["max_tenure_of_churned"] == 11


def test_churn_by_contract_sums(results):
    t = results["churn_contract"]
    assert t["Customers"].sum() == 500 and t["Churned"].sum() == 53


# ---------------- End to end ----------------
def test_full_pipeline(tmp_path):
    out = run_analysis.run(ROOT, tmp_path)
    assert len(out["charts"]) == 5
    assert all(p.exists() and p.stat().st_size > 10_000 for p in out["charts"])
    assert out["pdf"].exists() and out["pdf"].stat().st_size > 50_000
    assert (tmp_path / "report_tables" / "region.csv").exists()
