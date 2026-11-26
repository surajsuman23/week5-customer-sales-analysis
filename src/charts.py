"""Matplotlib charts. Each function saves one PNG and returns its path."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

PALETTE = {"North": "#2E86AB", "South": "#F18F01", "East": "#C73E1D", "West": "#3B8B5A"}
PRIMARY, ACCENT, MUTED = "#2E86AB", "#F18F01", "#8A8A8A"


def lakh(x, _pos=None):
    """1250000 -> '₹12.5L' (Indian lakh notation)."""
    return f"₹{x / 1e5:.1f}L"


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.3)


def _save(fig, out_dir, name):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def top_customers_bar(value_table, out_dir, n=10):
    """Horizontal bar: top-N customers by revenue, coloured by region."""
    top = value_table.head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    colors = [PALETTE.get(r, MUTED) for r in top["Region"]]
    bars = ax.barh(top.index, top["Revenue"], color=colors)
    for bar, prod in zip(bars, top["Product"]):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f"  {lakh(bar.get_width())} · {prod}",
                va="center", fontsize=8.5)
    share = value_table["Revenue"].head(n).sum() / value_table["Revenue"].sum() * 100
    ax.set_title(f"Top {n} Customers by Revenue ({share:.1f}% of total)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Revenue (₹ lakh)")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lakh))
    ax.set_xlim(0, top["Revenue"].max() * 1.35)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in PALETTE.values()]
    ax.legend(handles, PALETTE.keys(), title="Region", loc="lower right", fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.3)
    return _save(fig, out_dir, "1_top_customers_bar.png")


def monthly_trend_combo(monthly, out_dir):
    """Bars = monthly revenue; line = revenue per active day (fair for the partial month)."""
    fig, ax1 = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(monthly))
    bars = ax1.bar(x, monthly["Revenue"], color=PRIMARY, alpha=0.85, label="Total revenue")
    ax1.set_xticks(x, monthly.index)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lakh))
    ax1.set_ylabel("Total revenue (₹ lakh)")
    for bar, days in zip(bars, monthly["Active_Days"]):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{days} days",
                 ha="center", va="bottom", fontsize=8, color=MUTED)

    ax2 = ax1.twinx()
    ax2.plot(x, monthly["Revenue_per_Day"], color=ACCENT, marker="o", linewidth=2.5, label="Revenue per day")
    ax2.set_ylabel("Revenue per day (₹)")
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"₹{v / 1e3:.0f}K"))
    ax2.set_ylim(0, monthly["Revenue_per_Day"].max() * 1.25)

    lines = ax1.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    labels = ax1.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    ax1.legend(lines, labels, loc="upper right", fontsize=9)
    ax1.set_title("Monthly Revenue and Daily Run-Rate", fontsize=13, fontweight="bold")
    ax1.set_xlabel("Month")
    _style(ax1)
    return _save(fig, out_dir, "2_monthly_trend_combo.png")


def affinity_heatmap(affinity, region_product, out_dir):
    """Heatmap of region x product lift (cross-selling proxy), annotated with revenue."""
    fig, ax = plt.subplots(figsize=(9.5, 5))
    im = ax.imshow(affinity.values, cmap="RdBu_r", vmin=0, vmax=2)
    ax.set_xticks(range(affinity.shape[1]), affinity.columns)
    ax.set_yticks(range(affinity.shape[0]), affinity.index)
    for i, region in enumerate(affinity.index):
        for j, product in enumerate(affinity.columns):
            lift = affinity.iat[i, j]
            rev = region_product.loc[region, product]
            color = "white" if abs(lift - 1) > 0.6 else "black"
            ax.text(j, i, f"{lift:.2f}x\n{lakh(rev)}", ha="center", va="center", fontsize=8.5, color=color)
    fig.colorbar(im, ax=ax, label="Lift vs overall product mix (1.0 = average)")
    ax.set_title("Region × Product Affinity (which products over-sell where)", fontsize=13, fontweight="bold")
    return _save(fig, out_dir, "3_region_product_affinity_heatmap.png")


def churn_by_tenure_contract(contract_tenure, churn_contract, out_dir):
    """Grouped bars: churn rate by tenure band for each contract type, plus overall by contract."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [2.2, 1]})
    bands = contract_tenure.index.astype(str)
    x = np.arange(len(bands))
    width = 0.27
    colors = [ACCENT, PRIMARY, "#3B8B5A"]
    for k, (contract, color) in enumerate(zip(contract_tenure.columns, colors)):
        ax1.bar(x + (k - 1) * width, contract_tenure[contract].fillna(0), width, label=contract, color=color)
    ax1.set_xticks(x, bands)
    zero_bands = [i for i, b in enumerate(contract_tenure.index) if contract_tenure.loc[b].fillna(0).sum() == 0]
    for i in zero_bands:
        ax1.text(i, 3, "0% churn", ha="center", fontsize=9, color=MUTED)
    ax1.set_ylabel("Churn rate (%)")
    ax1.set_ylim(0, 110)
    ax1.set_title("Churn Rate by Tenure and Contract", fontsize=12, fontweight="bold")
    ax1.legend(title="Contract", fontsize=8)
    _style(ax1)

    bars = ax2.bar(churn_contract.index, churn_contract["Churn_Rate_%"], color=colors[: len(churn_contract)])
    for bar in bars:
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{bar.get_height():.1f}%",
                 ha="center", va="bottom", fontsize=9)
    ax2.set_title("Overall Churn by Contract", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Churn rate (%)")
    ax2.tick_params(axis="x", labelsize=8)
    _style(ax2)
    return _save(fig, out_dir, "4_churn_by_tenure_contract.png")


def regional_distribution_donut(region, out_dir):
    """Donut chart: revenue share by region, with customer counts in the labels."""
    fig, ax = plt.subplots(figsize=(7, 7))
    labels = [f"{r}\n{c} customers" for r, c in zip(region.index, region["Customers"])]
    ax.pie(region["Revenue"], labels=labels, autopct="%1.1f%%", startangle=90, pctdistance=0.8,
           colors=[PALETTE.get(r, MUTED) for r in region.index],
           wedgeprops={"width": 0.4, "edgecolor": "white", "linewidth": 2}, textprops={"fontsize": 10})
    ax.text(0, 0, f"{lakh(region['Revenue'].sum())}\ntotal", ha="center", va="center", fontsize=13, fontweight="bold")
    ax.set_title("Regional Revenue Distribution", fontsize=13, fontweight="bold")
    return _save(fig, out_dir, "5_regional_distribution_donut.png")


def make_all(results, out_dir):
    return [
        top_customers_bar(results["customer_value"], out_dir),
        monthly_trend_combo(results["monthly"], out_dir),
        affinity_heatmap(results["affinity"], results["region_product"], out_dir),
        churn_by_tenure_contract(results["contract_tenure"], results["churn_contract"], out_dir),
        regional_distribution_donut(results["region"], out_dir),
    ]
