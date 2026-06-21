"""
Module 1: Demand Forecasting.

Predicts next-30-day unit demand from historical sales using Prophet,
with promotion, price, and weather as extra regressors.

Run: python src/demand_forecast.py
"""
import numpy as np
import pandas as pd
from prophet import Prophet

HOLDOUT_DAYS = 30
FORECAST_DAYS = 30
REGRESSORS = ["promotion_flag", "price", "avg_temp_f"]


def load_sales_history(path="data/sales_history.csv"):
    df = pd.read_csv(path, parse_dates=["date"])
    return df.rename(columns={"date": "ds", "units_sold": "y"})


def available_regressors(df):
    """Use whichever of the known regressor columns the data actually has - a minimal
    upload with just date/units_sold still works, just as plain Prophet with no regressors."""
    return [r for r in REGRESSORS if r in df.columns]


def build_model(regressors=REGRESSORS):
    m = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        interval_width=0.85,
    )
    for reg in regressors:
        m.add_regressor(reg)
    return m


def backtest(df, regressors=None):
    """Fit on all but the last HOLDOUT_DAYS, predict them, score against actuals."""
    if regressors is None:
        regressors = available_regressors(df)
    train = df.iloc[:-HOLDOUT_DAYS]
    test = df.iloc[-HOLDOUT_DAYS:]

    model = build_model(regressors)
    model.fit(train[["ds", "y"] + regressors])

    forecast = model.predict(test[["ds"] + regressors])
    actual = test["y"].to_numpy()
    predicted = forecast["yhat"].to_numpy()

    mape = np.mean(np.abs((actual - predicted) / actual)) * 100
    accuracy = 100 - mape
    within_interval = np.mean(
        (actual >= forecast["yhat_lower"]) & (actual <= forecast["yhat_upper"])
    ) * 100

    return accuracy, within_interval, predicted.sum(), actual.sum()


def forecast_next_period(df, regressors=None):
    """Fit on full history, forecast the next FORECAST_DAYS using assumed future regressors."""
    if regressors is None:
        regressors = available_regressors(df)
    model = build_model(regressors)
    model.fit(df[["ds", "y"] + regressors])

    future = model.make_future_dataframe(periods=FORECAST_DAYS)
    future = future.merge(df[["ds"] + regressors], on="ds", how="left")
    future_mask = future["ds"] > df["ds"].max()

    if "promotion_flag" in regressors:
        future.loc[future_mask, "promotion_flag"] = 0  # no promo planned by default
    if "price" in regressors:
        future.loc[future_mask, "price"] = df["price"].iloc[-1]  # assume price holds steady
    if "avg_temp_f" in regressors:
        future_doy = future.loc[future_mask, "ds"].dt.dayofyear
        seasonal_temp = 60 + 20 * np.sin(2 * np.pi * (future_doy - 80) / 365.25)
        future.loc[future_mask, "avg_temp_f"] = seasonal_temp.to_numpy()

    forecast = model.predict(future)
    return forecast.tail(FORECAST_DAYS)[["ds", "yhat", "yhat_lower", "yhat_upper"]]


if __name__ == "__main__":
    df = load_sales_history()

    accuracy, within_interval, forecast_total, actual_total = backtest(df)
    print(f"Backtest ({HOLDOUT_DAYS}-day holdout): accuracy = {accuracy:.1f}%, "
          f"{within_interval:.0f}% of actuals within forecast interval")
    print(f"  Forecasted: {forecast_total:,.0f} units | Actual: {actual_total:,.0f} units")

    result = forecast_next_period(df)
    result.to_csv("outputs/demand_forecast.csv", index=False)

    total = result["yhat"].sum()
    lower = result["yhat_lower"].sum()
    upper = result["yhat_upper"].sum()
    confidence = (upper - lower) / 2

    print(f"\nFORECAST (next {FORECAST_DAYS} days): {total:,.0f} units "
          f"(±{confidence:,.0f} confidence)")
    print(f"Range: {lower:,.0f} - {upper:,.0f} units")
    print("\nSaved daily forecast to outputs/demand_forecast.csv")
    print(result.head())
