"""
Aggregations, filters, pivot tables and churn/retention metrics.

All functions are pure: they take DataFrames and return new DataFrames or dicts.
"""

import pandas as pd

WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# --------------------------------------------------------------------------- #
# Sales KPIs and aggregations
# --------------------------------------------------------------------------- #
def sales_kpis(sales):
    return {
        "total_revenue": int(sales["Total_Sales"].sum()),
        "total_orders": int(len(sales)),
        "total_units": int(sales["Quantity"].sum()),
        "unique_customers": int(sales["Customer_ID"].nunique()),
        "avg_order_value": round(float(sales["Total_Sales"].mean()), 2),
        "median_order_value": round(float(sales["Total_Sales"].median()), 2),
        "date_start": sales["Date"].min().date().isoformat(),
        "date_end": sales["Date"].max().date().isoformat(),
    }


def customer_value(sales):
    """Revenue per customer (customer value over the period), ranked."""
    table = (
        sales.groupby("Customer_ID")
        .agg(Revenue=("Total_Sales", "sum"), Orders=("Total_Sales", "count"),
             Units=("Quantity", "sum"), Region=("Region", "first"), Product=("Product", "first"))
        .sort_values("Revenue", ascending=False)
    )
    table["Rank"] = range(1, len(table) + 1)
    table["Cumulative_Share_%"] = (table["Revenue"].cumsum() / table["Revenue"].sum() * 100).round(1)
    return table


def top_customer_share(value_table, n=10):
    return round(float(value_table["Revenue"].head(n).sum() / value_table["Revenue"].sum() * 100), 1)


def region_summary(sales):
    """Aggregation type 1: several named aggregations per region."""
    table = (
        sales.groupby("Region")
        .agg(Revenue=("Total_Sales", "sum"), Orders=("Total_Sales", "size"),
             Customers=("Customer_ID", "nunique"), Avg_Order=("Total_Sales", "mean"),
             Max_Order=("Total_Sales", "max"))
        .sort_values("Revenue", ascending=False)
    )
    table["Share_%"] = (table["Revenue"] / table["Revenue"].sum() * 100).round(1)
    table["Avg_Order"] = table["Avg_Order"].round(0)
    return table


def monthly_summary(sales):
    """Aggregation type 2: monthly totals, per-day rate and month-on-month growth."""
    table = sales.groupby("Month").agg(
        Revenue=("Total_Sales", "sum"), Orders=("Total_Sales", "size"),
        Units=("Quantity", "sum"), Active_Days=("Date", "nunique"),
    )
    table["Revenue_per_Day"] = (table["Revenue"] / table["Active_Days"]).round(0)
    table["MoM_Growth_%"] = (table["Revenue"].pct_change() * 100).round(1)
    return table


def product_summary(sales):
    """Aggregation type 3: product performance with rank."""
    table = (
        sales.groupby("Product")
        .agg(Revenue=("Total_Sales", "sum"), Units=("Quantity", "sum"),
             Orders=("Total_Sales", "size"), Avg_Price=("Price", "mean"))
        .sort_values("Revenue", ascending=False)
    )
    table["Avg_Price"] = table["Avg_Price"].round(0)
    table["Revenue_Rank"] = table["Revenue"].rank(ascending=False).astype(int)
    table["Units_Rank"] = table["Units"].rank(ascending=False, method="min").astype(int)
    return table


def weekday_summary(sales):
    """Aggregation type 4: transform() adds each weekday's share back onto the table."""
    table = sales.groupby("Weekday").agg(Revenue=("Total_Sales", "sum"), Orders=("Total_Sales", "size"))
    table = table.reindex([d for d in WEEKDAY_ORDER if d in table.index])
    table["Avg_Order"] = (table["Revenue"] / table["Orders"]).round(0)
    return table


def add_order_share_within_region(sales):
    """groupby().transform(): each order's share of its region's revenue."""
    out = sales.copy()
    out["Region_Revenue"] = out.groupby("Region")["Total_Sales"].transform("sum")
    out["Share_of_Region_%"] = (out["Total_Sales"] / out["Region_Revenue"] * 100).round(2)
    return out


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #
def high_value_orders(sales, min_value=200_000, regions=("North", "South")):
    """AND filter: big orders that also come from the chosen regions."""
    mask = (sales["Total_Sales"] >= min_value) & (sales["Region"].isin(regions))
    return sales.loc[mask].sort_values("Total_Sales", ascending=False)


def laptop_or_bulk_orders(sales, min_qty=8):
    """OR filter: any Laptop order, or any order of at least `min_qty` units."""
    mask = (sales["Product"] == "Laptop") | (sales["Quantity"] >= min_qty)
    return sales.loc[mask]


def weekend_large_orders(sales, min_value=150_000):
    """AND + NOT filter: weekend orders above a value, excluding Headphones."""
    mask = sales["Is_Weekend"] & (sales["Total_Sales"] > min_value) & ~(sales["Product"] == "Headphones")
    return sales.loc[mask]


# --------------------------------------------------------------------------- #
# Pivot tables
# --------------------------------------------------------------------------- #
def region_product_pivot(sales):
    return sales.pivot_table(index="Region", columns="Product", values="Total_Sales",
                             aggfunc="sum", fill_value=0, margins=True, margins_name="Total")


def month_product_units_pivot(sales):
    return sales.pivot_table(index="Month", columns="Product", values="Quantity",
                             aggfunc="sum", fill_value=0)


def region_month_orders_pivot(sales):
    return sales.pivot_table(index="Region", columns="Month", values="Total_Sales",
                             aggfunc=["count", "mean"], fill_value=0).round(0)


def region_product_affinity(sales):
    """
    Lift of each product in each region: (product share in region) / (product share overall).
    > 1 means the product sells better than average in that region.
    Used instead of basket analysis because every customer has a single order.
    """
    pivot = sales.pivot_table(index="Region", columns="Product", values="Total_Sales", aggfunc="sum", fill_value=0)
    region_mix = pivot.div(pivot.sum(axis=1), axis=0)
    overall_mix = pivot.sum() / pivot.values.sum()
    return (region_mix / overall_mix).round(2)


# --------------------------------------------------------------------------- #
# Churn / retention (full 500-customer dataset - real data)
# --------------------------------------------------------------------------- #
def churn_kpis(churn):
    churn_rate = float(churn["Churn"].mean())
    churned = churn[churn["Churn"] == 1]
    return {
        "customers": int(len(churn)),
        "churned": int(churned.shape[0]),
        "churn_rate_%": round(churn_rate * 100, 1),
        "retention_rate_%": round((1 - churn_rate) * 100, 1),
        "max_tenure_of_churned": int(churned["Tenure"].max()) if len(churned) else 0,
        "avg_tenure_churned": round(float(churned["Tenure"].mean()), 1) if len(churned) else 0.0,
        "avg_tenure_retained": round(float(churn.loc[churn["Churn"] == 0, "Tenure"].mean()), 1),
        "avg_monthly_charge": round(float(churn["MonthlyCharges"].mean()), 1),
    }


def churn_by(churn, column):
    table = churn.groupby(column, observed=True).agg(
        Customers=("Churn", "size"), Churned=("Churn", "sum"),
        Avg_Monthly=("MonthlyCharges", "mean"),
    )
    table["Churn_Rate_%"] = (table["Churned"] / table["Customers"] * 100).round(1)
    table["Retention_%"] = (100 - table["Churn_Rate_%"]).round(1)
    table["Avg_Monthly"] = table["Avg_Monthly"].round(1)
    return table


def contract_tenure_pivot(churn):
    return churn.pivot_table(index="Tenure_Band", columns="Contract", values="Churn",
                             aggfunc="mean", observed=False).mul(100).round(1)


def at_risk_customers(churn, early_tenure=12, flexible_tenure=24):
    """
    AND/OR filter for active customers worth a retention call:
    still active AND (in their first `early_tenure` months
                      OR on a month-to-month contract with tenure <= `flexible_tenure`).
    """
    early = churn["Tenure"] <= early_tenure
    flexible = (churn["Contract"] == "Month-to-month") & (churn["Tenure"] <= flexible_tenure)
    mask = (churn["Churn"] == 0) & (early | flexible)
    return churn.loc[mask].sort_values("Tenure")


def total_charges_check(churn):
    """
    Data-quality flag: % of customers whose TotalCharges is less than half of
    MonthlyCharges x Tenure (we would expect TotalCharges to be close to that product).
    """
    expected = churn["MonthlyCharges"] * churn["Tenure"]
    inconsistent = churn["TotalCharges"] < expected * 0.5
    return round(float(inconsistent.mean() * 100), 1)


# --------------------------------------------------------------------------- #
# Merged data (simulated link - illustrative only)
# --------------------------------------------------------------------------- #
def merged_contract_summary(merged):
    table = merged.groupby("Contract").agg(
        Customers=("Customer_ID", "nunique"), Revenue=("Total_Sales", "sum"),
        Avg_Order=("Total_Sales", "mean"), Churned=("Churn", "sum"),
    )
    table["Avg_Order"] = table["Avg_Order"].round(0)
    table["Revenue_Share_%"] = (table["Revenue"] / table["Revenue"].sum() * 100).round(1)
    return table.sort_values("Revenue", ascending=False)


def revenue_at_risk(merged):
    """Revenue from (illustratively) churned customers."""
    churned_rev = merged.loc[merged["Churn"] == 1, "Total_Sales"].sum()
    return int(churned_rev), round(float(churned_rev / merged["Total_Sales"].sum() * 100), 1)


# --------------------------------------------------------------------------- #
# One call that runs everything
# --------------------------------------------------------------------------- #
def run_all(sales, churn, merged):
    value = customer_value(sales)
    return {
        "kpis": sales_kpis(sales),
        "customer_value": value,
        "top10_share": top_customer_share(value, 10),
        "region": region_summary(sales),
        "monthly": monthly_summary(sales),
        "product": product_summary(sales),
        "weekday": weekday_summary(sales),
        "high_value": high_value_orders(sales),
        "laptop_or_bulk": laptop_or_bulk_orders(sales),
        "weekend_large": weekend_large_orders(sales),
        "region_product": region_product_pivot(sales),
        "month_product_units": month_product_units_pivot(sales),
        "region_month": region_month_orders_pivot(sales),
        "affinity": region_product_affinity(sales),
        "churn_kpis": churn_kpis(churn),
        "churn_contract": churn_by(churn, "Contract"),
        "churn_tenure": churn_by(churn, "Tenure_Band"),
        "churn_payment": churn_by(churn, "PaymentMethod"),
        "churn_senior": churn_by(churn, "SeniorCitizen"),
        "contract_tenure": contract_tenure_pivot(churn),
        "at_risk": at_risk_customers(churn),
        "total_charges_flag_%": total_charges_check(churn),
        "merged_contract": merged_contract_summary(merged),
        "revenue_at_risk": revenue_at_risk(merged),
    }
