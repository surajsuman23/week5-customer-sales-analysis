"""Turn the computed tables into plain-English findings and recommendations."""


def rupees(value):
    return f"₹{value:,.0f}"


def sales_insights(r):
    k = r["kpis"]
    region, monthly, product = r["region"], r["monthly"], r["product"]
    affinity = r["affinity"]
    top_cust = r["customer_value"].iloc[0]

    full = monthly[monthly["Active_Days"] >= 28]
    slow, best = full["Revenue_per_Day"].idxmin(), full["Revenue_per_Day"].idxmax()
    dip = (1 - full.loc[slow, "Revenue_per_Day"] / full.loc[best, "Revenue_per_Day"]) * 100

    stacked = affinity.stack()
    best_pair, worst_pair = stacked.idxmax(), stacked.idxmin()
    weak = region.index[-1]

    return [
        f"Top customer {r['customer_value'].index[0]} spent {rupees(top_cust['Revenue'])} "
        f"({top_cust['Product']}, {top_cust['Region']}). The top 10 customers bring in {r['top10_share']}% "
        f"of revenue - every customer placed exactly one order, so value comes from order size, not repeat buying.",
        f"{product.index[0]} is the best-selling product by both revenue ({rupees(product['Revenue'].iloc[0])}) "
        f"and units ({int(product['Units'].iloc[0])}).",
        f"{region.index[0]} and {region.index[1]} generate {region['Share_%'].iloc[:2].sum():.1f}% of revenue. "
        f"{weak} has {int(region.loc[weak, 'Orders'])} orders but the lowest average order "
        f"({rupees(region.loc[weak, 'Avg_Order'])} vs {rupees(k['avg_order_value'])} overall).",
        f"{slow} was the slowest full month: revenue per day was {dip:.0f}% below {best}.",
        f"Strongest regional fit: {best_pair[1]} in {best_pair[0]} sells at {stacked.max():.2f}x its normal share; "
        f"weakest: {worst_pair[1]} in {worst_pair[0]} at {stacked.min():.2f}x.",
    ]


def churn_insights(r):
    c = r["churn_kpis"]
    contract = r["churn_contract"]
    tenure = r["churn_tenure"]
    pay = r["churn_payment"]
    mtm = contract.loc["Month-to-month", "Churn_Rate_%"] if "Month-to-month" in contract.index else None
    early = tenure.iloc[:2]
    early_rate = early["Churned"].sum() / early["Customers"].sum() * 100
    lines = [
        f"Retention rate is {c['retention_rate_%']}% ({c['churned']} of {c['customers']} customers churned, "
        f"churn rate {c['churn_rate_%']}%).",
        f"All churn happens early: no customer with tenure above {c['max_tenure_of_churned']} months churned, "
        f"and customers in their first 12 months churn at {early_rate:.1f}%. Churned customers averaged "
        f"{c['avg_tenure_churned']} months of tenure vs {c['avg_tenure_retained']} for retained customers.",
    ]
    if mtm is not None:
        ratio = mtm / contract.drop("Month-to-month")["Churn_Rate_%"].mean()
        text = f"Month-to-month contracts churn at {mtm}% - about {ratio:.0f}x the fixed-term contracts."
        first_year = r["contract_tenure"].iloc[:2].get("Month-to-month")
        if first_year is not None and (first_year == 100).all():
            text += " In this data every month-to-month customer in their first year churned."
        lines.append(text)
    lines.append(
        f"By payment method, {pay['Churn_Rate_%'].idxmax()} has the highest churn ({pay['Churn_Rate_%'].max()}%) "
        f"and {pay['Churn_Rate_%'].idxmin()} the lowest ({pay['Churn_Rate_%'].min()}%)."
    )
    lines.append(f"{len(r['at_risk'])} active customers match the at-risk filter for a retention call.")
    return lines


def merged_insights(r):
    m = r["merged_contract"]
    rev, pct = r["revenue_at_risk"]
    return [
        f"(Illustrative - simulated link) {m.index[0]}-contract customers account for "
        f"{m['Revenue_Share_%'].iloc[0]}% of sales revenue; customers flagged as churned account for "
        f"{rupees(rev)} ({pct}%).",
    ]


def recommendations(r):
    product, region = r["product"], r["region"]
    stacked = r["affinity"].stack()
    best_pair = stacked.idxmax()
    contract = r["churn_contract"]["Churn_Rate_%"]
    best_contract = contract.idxmin()
    return [
        f"Run an onboarding programme for the first {r['churn_kpis']['max_tenure_of_churned'] + 1} months - "
        f"that is where all churn happens in this data.",
        f"Offer an incentive to move month-to-month customers onto {best_contract.lower()} contracts "
        f"({contract[best_contract]}% churn vs {contract.get('Month-to-month', float('nan'))}%).",
        f"Prioritise {product.index[0]} stock and promotion; it leads revenue and units.",
        f"Use regional strengths: push {best_pair[1]} in {best_pair[0]} and test bundles in {region.index[-1]} "
        f"to lift its low average order value.",
        "Run a VIP programme for the top 10 customers and track repeat purchases - the current data has none.",
        "Collect a shared customer ID across sales and CRM systems so real customer-level merges are possible.",
    ]
