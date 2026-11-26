"""
Loading, validation, cleaning and merging.

Every function returns a new DataFrame and never edits the input in place.
"""

from pathlib import Path

import pandas as pd

SALES_COLUMNS = ["Date", "Product", "Quantity", "Price", "Customer_ID", "Region", "Total_Sales"]
CHURN_COLUMNS = [
    "CustomerID", "Tenure", "MonthlyCharges", "TotalCharges", "Contract",
    "PaymentMethod", "PaperlessBilling", "SeniorCitizen", "Churn",
]
PROFILE_COLUMNS = [
    "Tenure", "MonthlyCharges", "TotalCharges", "Contract",
    "PaymentMethod", "PaperlessBilling", "SeniorCitizen", "Churn",
]
TENURE_BINS = [0, 6, 12, 24, 48, 72]
TENURE_LABELS = ["0-6 months", "7-12 months", "13-24 months", "25-48 months", "49-72 months"]


class DataValidationError(Exception):
    """Raised when an input file cannot be used for the analysis."""


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_csv(path, required_columns):
    """Read a CSV and check that every required column is present."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError(f"Data file is empty: {path}") from exc

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise DataValidationError(f"{path.name} is missing columns: {missing}")
    if df.empty:
        raise DataValidationError(f"{path.name} has headers but no rows")
    return df


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #
def clean_sales(df):
    """
    Clean the order-level sales data and add date parts.

    Returns (clean_df, log) where log counts what was changed.
    """
    df = df.copy()
    log = {"rows_in": len(df)}

    # String operations: trim spaces, standardise casing, normalise IDs
    for col in ["Product", "Region", "Customer_ID"]:
        df[col] = df[col].astype("string").str.strip()
    df["Product"] = df["Product"].str.title()
    df["Region"] = df["Region"].str.title()
    df["Customer_ID"] = df["Customer_ID"].str.upper().str.replace(" ", "", regex=False)

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for col in ["Quantity", "Price", "Total_Sales"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    log["missing_values"] = int(df.isna().sum().sum())

    before = len(df)
    df = df.drop_duplicates()
    log["duplicates_removed"] = before - len(df)

    before = len(df)
    df = df.dropna(subset=["Date", "Product", "Region", "Customer_ID", "Quantity", "Price"])
    df = df[(df["Quantity"] > 0) & (df["Price"] > 0)]
    log["invalid_rows_removed"] = before - len(df)

    expected = df["Quantity"] * df["Price"]
    wrong_total = df["Total_Sales"].isna() | (df["Total_Sales"] != expected)
    df.loc[wrong_total, "Total_Sales"] = expected[wrong_total]
    log["totals_recomputed"] = int(wrong_total.sum())

    if df.empty:
        raise DataValidationError("No valid sales rows left after cleaning")

    df["Quantity"] = df["Quantity"].astype(int)
    df = add_date_parts(df)
    df = df.sort_values("Date").reset_index(drop=True)
    log["rows_out"] = len(df)
    return df, log


def add_date_parts(df):
    """Extract year, month, day, weekday and ISO week from the Date column."""
    df = df.copy()
    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    df["Month_Name"] = df["Date"].dt.month_name()
    df["Day"] = df["Date"].dt.day
    df["Weekday"] = df["Date"].dt.day_name()
    df["Is_Weekend"] = df["Date"].dt.dayofweek >= 5
    df["Week"] = df["Date"].dt.isocalendar().week.astype(int)
    return df


def clean_churn(df):
    """Clean the customer churn data and add helper columns."""
    df = df.copy()
    for col in ["CustomerID", "Contract", "PaymentMethod", "PaperlessBilling"]:
        df[col] = df[col].astype("string").str.strip()
    df["Contract"] = df["Contract"].str.capitalize()            # "month-to-month" -> "Month-to-month"
    df["PaymentMethod"] = df["PaymentMethod"].str.title()
    df["PaperlessBilling"] = df["PaperlessBilling"].str.title()

    for col in ["Tenure", "MonthlyCharges", "TotalCharges", "SeniorCitizen", "Churn"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.drop_duplicates(subset="CustomerID").dropna(subset=["CustomerID", "Tenure", "Churn"])
    if df.empty:
        raise DataValidationError("No valid churn rows left after cleaning")

    df["Tenure_Band"] = pd.cut(df["Tenure"], bins=TENURE_BINS, labels=TENURE_LABELS, include_lowest=True)
    # String operation: does the contract name mention a fixed term ("year")?
    df["Fixed_Term"] = df["Contract"].str.contains("year", case=False)
    df["Auto_Pay"] = df["PaymentMethod"].str.contains("Transfer|Card", regex=True)
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# customer_data.csv and merging
# --------------------------------------------------------------------------- #
def build_customer_data(churn, customer_ids):
    """
    Create a customer profile table for the sales customers.

    The two supplied datasets share no customer key, so the first N churn
    profiles are re-keyed to the sales Customer_IDs in order. This is a
    SIMULATED link to practise merging - findings that use it are illustrative.
    """
    customer_ids = sorted(pd.Series(customer_ids).dropna().unique())
    if len(churn) < len(customer_ids):
        raise DataValidationError("Not enough churn profiles to link to every sales customer")

    profiles = churn.head(len(customer_ids)).reset_index(drop=True)
    customers = pd.DataFrame({"Customer_ID": customer_ids, "Source_Profile_ID": profiles["CustomerID"]})
    for col in PROFILE_COLUMNS:
        customers[col] = profiles[col]
    return customers


def merge_sales_customers(sales, customers):
    """Left-join customer profiles onto orders; every order must keep its row."""
    merged = sales.merge(customers, on="Customer_ID", how="left", validate="many_to_one", indicator=True)
    unmatched = int((merged["_merge"] == "left_only").sum())
    merged = merged.drop(columns="_merge")
    if len(merged) != len(sales):
        raise DataValidationError("Merge changed the number of order rows")
    return merged, unmatched
