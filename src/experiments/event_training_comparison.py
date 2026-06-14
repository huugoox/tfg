from pathlib import Path
import sqlite3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.metrics import mean_squared_error, mean_squared_log_error
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor

from statsmodels.tsa.arima.model import ARIMA

try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False


# ============================================================
# DATA LOADING
# ============================================================

def load_train_test_prices(
    db_path,
    zone_code,
    train_start,
    train_end,
    test_start,
    test_end,
):
    conn = sqlite3.connect(db_path)

    query = """
    SELECT 
        p.price_id,
        p.zone_id,
        bz.zone_code,
        p.delivery_day,
        p.hour,
        p.price_value
    FROM Prices p
    JOIN BiddingZones bz 
        ON p.zone_id = bz.zone_id
    WHERE bz.zone_code = ?
      AND (
            (p.delivery_day >= ? AND p.delivery_day <= ?)
            OR
            (p.delivery_day >= ? AND p.delivery_day <= ?)
          )
    ORDER BY p.delivery_day, p.hour
    """

    df_prices = pd.read_sql_query(
        query,
        conn,
        params=(zone_code, train_start, train_end, test_start, test_end),
    )

    conn.close()

    return df_prices

def load_calibration_train_test_prices(
    db_path,
    zone_code,
    calibration_start,
    calibration_end,
    train_start,
    train_end,
    test_start,
    test_end,
):
    conn = sqlite3.connect(db_path)

    query = """
    SELECT 
        p.price_id,
        p.zone_id,
        bz.zone_code,
        p.delivery_day,
        p.hour,
        p.price_value
    FROM Prices p
    JOIN BiddingZones bz 
        ON p.zone_id = bz.zone_id
    WHERE bz.zone_code = ?
      AND (
            (p.delivery_day >= ? AND p.delivery_day <= ?)
            OR
            (p.delivery_day >= ? AND p.delivery_day <= ?)
            OR
            (p.delivery_day >= ? AND p.delivery_day <= ?)
          )
    ORDER BY p.delivery_day, p.hour
    """

    df_prices = pd.read_sql_query(
        query,
        conn,
        params=(
            zone_code,
            calibration_start,
            calibration_end,
            train_start,
            train_end,
            test_start,
            test_end,
        ),
    )

    conn.close()

    return df_prices


# ============================================================
# DATASET PREPARATION
# ============================================================

def prepare_model_dataset(df_prices, target_horizon=1):
    df_model = df_prices.copy()

    df_model["delivery_day"] = pd.to_datetime(df_model["delivery_day"])
    df_model["hour"] = pd.to_numeric(df_model["hour"], errors="coerce")

    df_model["datetime"] = (
        df_model["delivery_day"] + pd.to_timedelta(df_model["hour"], unit="h")
    )

    df_model = df_model.sort_values("datetime").reset_index(drop=True)

    # Target: price one hour ahead.
    # Use datetime merge instead of shift(-1), because train/test periods
    # may not be continuous.
    target_df = df_model[["datetime", "price_value"]].copy()
    target_df["datetime"] = target_df["datetime"] - pd.Timedelta(hours=target_horizon)
    target_df = target_df.rename(columns={"price_value": "target_price_1h"})

    df_model = df_model.merge(
        target_df,
        on="datetime",
        how="left",
    )

    # Time features
    df_model["hour_of_day"] = df_model["datetime"].dt.hour
    df_model["day_of_week"] = df_model["datetime"].dt.dayofweek
    df_model["month"] = df_model["datetime"].dt.month

    df_model = df_model.dropna(subset=["target_price_1h"]).copy()

    return df_model


def split_train_test_periods(
    df_model,
    train_start,
    train_end,
    test_start,
    test_end,
):
    train_start_ts = pd.Timestamp(train_start)
    train_end_ts = pd.Timestamp(train_end + " 23:00:00")

    test_start_ts = pd.Timestamp(test_start)
    test_end_ts = pd.Timestamp(test_end + " 23:00:00")

    df_train_full = df_model[
        (df_model["datetime"] >= train_start_ts)
        & (df_model["datetime"] <= train_end_ts)
    ].copy()

    df_test_common = df_model[
        (df_model["datetime"] >= test_start_ts)
        & (df_model["datetime"] <= test_end_ts)
    ].copy()

    return df_train_full, df_test_common

def split_calibration_train_test_periods(
    df_model,
    calibration_start,
    calibration_end,
    train_start,
    train_end,
    test_start,
    test_end,
):
    calibration_start_ts = pd.Timestamp(calibration_start)
    calibration_end_ts = pd.Timestamp(calibration_end + " 23:00:00")

    train_start_ts = pd.Timestamp(train_start)
    train_end_ts = pd.Timestamp(train_end + " 23:00:00")

    test_start_ts = pd.Timestamp(test_start)
    test_end_ts = pd.Timestamp(test_end + " 23:00:00")

    df_calibration = df_model[
        (df_model["datetime"] >= calibration_start_ts)
        & (df_model["datetime"] <= calibration_end_ts)
    ].copy()

    df_train_full = df_model[
        (df_model["datetime"] >= train_start_ts)
        & (df_model["datetime"] <= train_end_ts)
    ].copy()

    df_test_common = df_model[
        (df_model["datetime"] >= test_start_ts)
        & (df_model["datetime"] <= test_end_ts)
    ].copy()

    return df_calibration, df_train_full, df_test_common


# ============================================================
# EVENT TRAINING DATASETS
# ============================================================

# ============================================================
# CALIBRATED PRICE EVENTS
# ============================================================

def calibrate_price_event_thresholds(df_calibration):
    """
    Computes event thresholds using only the calibration period.
    """

    df = df_calibration.copy()
    df = df.sort_values("datetime").reset_index(drop=True)

    df["price_delta"] = df["price_value"].diff()
    df["abs_price_delta"] = df["price_delta"].abs()

    df["rolling_volatility_24h"] = (
        df["price_value"]
        .rolling(window=24, min_periods=12)
        .std()
    )

    thresholds = {
        "low_price": df["price_value"].quantile(0.10),
        "high_price": df["price_value"].quantile(0.90),
        "extreme_price": df["price_value"].quantile(0.95),
        "price_spike": df["price_delta"].quantile(0.90),
        "rapid_price_change": df["abs_price_delta"].quantile(0.95),
        "price_ramp_up": df["price_delta"].quantile(0.95),
        "price_ramp_down": df["price_delta"].quantile(0.05),
        "high_volatility": df["rolling_volatility_24h"].quantile(0.90),
    }

    return thresholds

def apply_calibrated_price_events(df, thresholds):
    """
    Applies frozen event thresholds to a new period.
    """

    df_events = df.copy()
    df_events = df_events.sort_values("datetime").reset_index(drop=True)

    df_events["price_delta"] = df_events["price_value"].diff()
    df_events["abs_price_delta"] = df_events["price_delta"].abs()

    df_events["rolling_volatility_24h"] = (
        df_events["price_value"]
        .rolling(window=24, min_periods=12)
        .std()
    )

    df_events["low_price"] = (
        df_events["price_value"] < thresholds["low_price"]
    )

    df_events["high_price"] = (
        df_events["price_value"] > thresholds["high_price"]
    )

    df_events["extreme_price"] = (
        df_events["price_value"] > thresholds["extreme_price"]
    )

    df_events["price_spike"] = (
        df_events["price_delta"] > thresholds["price_spike"]
    )

    df_events["rapid_price_change"] = (
        df_events["abs_price_delta"] > thresholds["rapid_price_change"]
    )

    df_events["price_ramp_up"] = (
        df_events["price_delta"] > thresholds["price_ramp_up"]
    )

    df_events["price_ramp_down"] = (
        df_events["price_delta"] < thresholds["price_ramp_down"]
    )

    df_events["high_volatility"] = (
        df_events["rolling_volatility_24h"] > thresholds["high_volatility"]
    )

    own_event_cols = [
        "low_price",
        "high_price",
        "price_spike",
        "extreme_price",
        "rapid_price_change",
        "price_ramp_up",
        "price_ramp_down",
        "high_volatility",
    ]

    df_events["own_event"] = df_events[own_event_cols].any(axis=1)

    return df_events, own_event_cols


def build_rbatheta_train_dataset(df_train_full, rbatheta_events_path):
    df_rba = pd.read_csv(rbatheta_events_path)
    df_rba["datetime"] = pd.to_datetime(df_rba["datetime"])

    rba_train_times = df_rba["datetime"].drop_duplicates()

    df_train_rbatheta = df_train_full[
        df_train_full["datetime"].isin(rba_train_times)
    ].copy()

    return df_train_rbatheta


def build_own_event_train_dataset(df_train_full, detector):
    df_train_own_all = detector.detect_price_events(df_train_full.copy())

    own_event_cols = [
        "low_price",
        "high_price",
        "price_spike",
        "extreme_price",
        "rapid_price_change",
        "price_ramp_up",
        "price_ramp_down",
        "high_volatility",
    ]

    own_event_cols = [
        col for col in own_event_cols
        if col in df_train_own_all.columns
    ]

    df_train_own_all["own_event"] = (
        df_train_own_all[own_event_cols].any(axis=1)
    )

    df_train_own = df_train_own_all[
        df_train_own_all["own_event"]
    ].copy()

    return df_train_own, own_event_cols, df_train_own_all


def build_training_datasets(
    df_train_full,
    rbatheta_events_path,
    detector,
):
    df_train_rbatheta = build_rbatheta_train_dataset(
        df_train_full=df_train_full,
        rbatheta_events_path=rbatheta_events_path,
    )

    df_train_own, own_event_cols, df_train_own_all = build_own_event_train_dataset(
        df_train_full=df_train_full,
        detector=detector,
    )

    train_datasets = {
        "full_prices": df_train_full.copy(),
        "rbatheta_events": df_train_rbatheta,
        "own_events": df_train_own,
    }

    diagnostics = {
        "own_event_cols": own_event_cols,
        "own_event_counts": df_train_own_all[own_event_cols].sum().sort_values(ascending=False),
        "n_full_train": len(df_train_full),
        "n_rbatheta_train": len(df_train_rbatheta),
        "n_own_train": len(df_train_own),
    }

    return train_datasets, diagnostics


# ============================================================
# METRICS
# ============================================================

def compute_rmse(y_true, y_pred):
    return np.sqrt(mean_squared_error(y_true, y_pred))


def compute_rmsle_safe(y_true, y_pred):
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    # RMSLE does not accept negative values.
    # Electricity prices can be negative, so we clip only for this metric.
    y_true_clip = np.clip(y_true, a_min=0, a_max=None)
    y_pred_clip = np.clip(y_pred, a_min=0, a_max=None)

    return np.sqrt(mean_squared_log_error(y_true_clip, y_pred_clip))


def compute_metrics(y_true, y_pred):
    return {
        "RMSE": compute_rmse(y_true, y_pred)
        # "RMSLE": compute_rmsle_safe(y_true, y_pred)
    }


# ============================================================
# MODELS
# ============================================================

def get_default_models():
    models = {
        "Linear Regression": lambda: LinearRegression(),
        "Decision Tree": lambda: DecisionTreeRegressor(
            random_state=42,
        ),
        "Random Forest": lambda: RandomForestRegressor(
            n_estimators=200,
            random_state=42,
            n_jobs=-1,
        ),
    }

    if XGBOOST_AVAILABLE:
        models["XGBoost"] = lambda: XGBRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=-1,
        )

    return models


def train_single_model_with_training_sets(
    model_name,
    model_factory,
    train_datasets,
    df_test,
    feature_cols,
    target_col,
    full_train_size,
):
    model_results = []
    model_predictions = {}

    X_test = df_test[feature_cols]
    y_test = df_test[target_col]

    for dataset_name, train_data in train_datasets.items():
        X_train = train_data[feature_cols]
        y_train = train_data[target_col]

        model = model_factory()
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        metrics = compute_metrics(y_test, y_pred)

        model_results.append({
            "model": model_name,
            "training_dataset": dataset_name,
            "n_train": len(train_data),
            "n_test": len(df_test),
            "train_data_used_pct": len(train_data) / full_train_size * 100,
            "n_features": len(feature_cols),
            **metrics,
        })

        pred_df = pd.DataFrame({
            "datetime": df_test["datetime"].values,
            "y_true": y_test.values,
            "y_pred": y_pred,
        })

        pred_df["error"] = pred_df["y_true"] - pred_df["y_pred"]
        pred_df["abs_error"] = pred_df["error"].abs()

        model_predictions[dataset_name] = pred_df

    return model_results, model_predictions

# ============================================================
# ARIMA MODEL
# ============================================================

def rolling_arima_forecast(train_y, test_y, order=(3, 0, 3)):
    """
    Rolling one-step-ahead ARIMA forecast.

    The model is fitted on the current history and predicts the next value.
    Then, the real observed test value is added to the history.

    For event-based datasets, the training sequence is not continuous.
    This is intentional in this experiment, because the goal is to test
    whether ARIMA can work under the same dataset-reduction setting.
    """

    history = list(train_y)
    predictions = []

    for real_value in test_y:
        try:
            model = ARIMA(history, order=order)
            model_fit = model.fit()

            yhat = model_fit.forecast(steps=1)[0]

        except Exception:
            # Fallback if ARIMA fails with short or unstable event-based data
            yhat = history[-1]

        predictions.append(yhat)
        history.append(real_value)

    return np.array(predictions)


def train_arima_with_training_sets(
    train_datasets,
    df_test,
    target_col,
    full_train_size,
    arima_order=(3, 0, 3),
):
    """
    Trains/evaluates ARIMA using the same training datasets as the ML models:
    - full_prices
    - rbatheta_events
    - own_events
    """

    model_results = []
    model_predictions = {}

    y_test = df_test[target_col].astype(float)

    for dataset_name, train_data in train_datasets.items():

        y_train = train_data[target_col].astype(float)

        if len(y_train) < 30:
            print(f"Skipping ARIMA - {dataset_name}: not enough training samples.")
            continue

        y_pred = rolling_arima_forecast(
            train_y=y_train.values,
            test_y=y_test.values,
            order=arima_order,
        )

        metrics = compute_metrics(y_test, y_pred)

        model_results.append({
            "model": "ARIMA",
            "training_dataset": dataset_name,
            "n_train": len(train_data),
            "n_test": len(df_test),
            "train_data_used_pct": len(train_data) / full_train_size * 100,
            "n_features": 1,
            **metrics,
        })

        pred_df = pd.DataFrame({
            "datetime": df_test["datetime"].values,
            "y_true": y_test.values,
            "y_pred": y_pred,
        })

        pred_df["error"] = pred_df["y_true"] - pred_df["y_pred"]
        pred_df["abs_error"] = pred_df["error"].abs()

        model_predictions[dataset_name] = pred_df

    return model_results, model_predictions


def build_results_table(model_results):
    results_table = pd.DataFrame(model_results)

    results_table = results_table[
        [
            "model",
            "training_dataset",
            "n_train",
            "n_test",
            "train_data_used_pct",
            "RMSE",
            #"RMSLE"
        ]
    ].copy()

    results_table = results_table.rename(columns={
        "model": "Model",
        "training_dataset": "Training dataset",
        "n_train": "Training samples",
        "n_test": "Test samples",
        "train_data_used_pct": "Train data used (%)"
    })

    full_train_samples = results_table.loc[
        results_table["Training dataset"] == "full_prices",
        "Training samples"
    ].iloc[0]

    results_table["Data reduction (%)"] = (
        1 - results_table["Training samples"] / full_train_samples
    ) * 100

    results_table["Train data used (%)"] = results_table["Train data used (%)"].round(2)
    results_table["Data reduction (%)"] = results_table["Data reduction (%)"].round(2)
    results_table["RMSE"] = results_table["RMSE"].round(4)
    #results_table["RMSLE"] = results_table["RMSLE"].round(4)

    return results_table


# ============================================================
# FULL EXPERIMENT
# ============================================================

def run_event_training_comparison(
    db_path,
    rbatheta_events_path,
    detector,
    zone_code,
    train_start,
    train_end,
    test_start,
    test_end,
    models=None,
    feature_cols=None,
    target_col="target_price_1h",
    target_horizon=1,
    include_arima=True,
    arima_order=(3, 0, 3),
):
    if feature_cols is None:
        feature_cols = [
            "price_value",
            "hour_of_day",
            "day_of_week",
            "month",
        ]

    if models is None:
        models = get_default_models()

    df_prices = load_train_test_prices(
        db_path=db_path,
        zone_code=zone_code,
        train_start=train_start,
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
    )

    df_model = prepare_model_dataset(
        df_prices=df_prices,
        target_horizon=target_horizon,
    )

    df_train_full, df_test_common = split_train_test_periods(
        df_model=df_model,
        train_start=train_start,
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
    )

    train_datasets, diagnostics = build_training_datasets(
        df_train_full=df_train_full,
        rbatheta_events_path=rbatheta_events_path,
        detector=detector,
    )

    all_results = []
    all_predictions = {}

    for model_name, model_factory in models.items():
        model_results, model_predictions = train_single_model_with_training_sets(
            model_name=model_name,
            model_factory=model_factory,
            train_datasets=train_datasets,
            df_test=df_test_common,
            feature_cols=feature_cols,
            target_col=target_col,
            full_train_size=len(df_train_full),
        )

        all_results.extend(model_results)
        all_predictions[model_name] = model_predictions
        
    if include_arima:
        arima_results, arima_predictions = train_arima_with_training_sets(
            train_datasets=train_datasets,
            df_test=df_test_common,
            target_col=target_col,
            full_train_size=len(df_train_full),
            arima_order=arima_order,
        )

        all_results.extend(arima_results)
        all_predictions["ARIMA"] = arima_predictions

    results_table = build_results_table(all_results)

    results_table["Zone"] = zone_code
    results_table["Train period"] = f"{train_start} to {train_end}"
    results_table["Test period"] = f"{test_start} to {test_end}"

    ordered_cols = [
        "Zone",
        "Train period",
        "Test period",
        "Model",
        "Training dataset",
        "Training samples",
        "Test samples",
        "Train data used (%)",
        "Data reduction (%)",
        "RMSE",
        #"RMSLE",
    ]

    results_table = results_table[ordered_cols]

    experiment_objects = {
        "df_prices": df_prices,
        "df_model": df_model,
        "df_train_full": df_train_full,
        "df_test_common": df_test_common,
        "train_datasets": train_datasets,
        "diagnostics": diagnostics,
        "predictions": all_predictions,
    }

    return results_table, experiment_objects

# ============================================================
# PLOTTING
# ============================================================

def plot_metric_vs_training_samples_by_model(
    results_table,
    metric="RMSE",
    figsize=(10, 6),
    save_dir=None,
):
    """
    Creates one plot per model showing the selected metric against
    the number of training samples.

    If save_dir is provided, the plots are also saved as PNG files.
    """

    plot_df = results_table.copy()

    if metric not in plot_df.columns:
        raise ValueError(f"Metric '{metric}' not found in results table.")

    if save_dir is not None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

    models = plot_df["Model"].unique()

    for model_name in models:
        model_df = plot_df[plot_df["Model"] == model_name].copy()
        model_df = model_df.sort_values(metric)

        plt.figure(figsize=figsize)

        plt.plot(
            model_df[metric],
            model_df["Training samples"],
            marker="o",
            label=model_name,
        )

        for _, row in model_df.iterrows():
            plt.annotate(
                row["Training dataset"],
                (row[metric], row["Training samples"]),
                textcoords="offset points",
                xytext=(5, 5),
                ha="left",
            )

        plt.title(f"{model_name}: {metric} vs Training Samples")
        plt.xlabel(metric)
        plt.ylabel("Number of training samples")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()

        if save_dir is not None:
            safe_model_name = (
                model_name
                .replace(" ", "_")
                .replace("/", "_")
                .replace("\\", "_")
            )

            output_path = save_dir / f"{safe_model_name}_{metric}_vs_training_samples.png"

            plt.savefig(
                output_path,
                dpi=300,
                bbox_inches="tight",
            )

            print("Saved:", output_path)

        plt.show()


def plot_metric_vs_training_samples_all_models(
    results_table,
    metric="RMSE",
    figsize=(12, 7),
):
    """
    Creates a single summary plot with all models together.

    Parameters
    ----------
    results_table : pd.DataFrame
        Output table returned by run_event_training_comparison().
    metric : str
        Metric to plot. Usually "RMSE" or "RMSLE".
    figsize : tuple
        Figure size.
    """

    plot_df = results_table.copy()

    if metric not in plot_df.columns:
        raise ValueError(f"Metric '{metric}' not found in results table.")

    models = plot_df["Model"].unique()

    plt.figure(figsize=figsize)

    for model_name in models:
        model_df = plot_df[plot_df["Model"] == model_name].copy()
        model_df = model_df.sort_values("Training samples")

        plt.plot(
            model_df[metric],
            model_df["Training samples"],
            marker="o",
            label=model_name,
        )

    plt.title(f"{metric} vs Training Samples - All Models")
    plt.xlabel(metric)
    plt.ylabel("Number of training samples")
    plt.grid(True, alpha=0.3)
    plt.legend(loc="upper left", bbox_to_anchor=(1.02, 1))
    plt.tight_layout()
    plt.show()


def plot_rmse_and_rmsle_by_model(results_table):
    """
    Convenience function that creates separated RMSE and RMSLE plots
    for each model.
    """

    plot_metric_vs_training_samples_by_model(
        results_table=results_table,
        metric="RMSE",
    )

    # plot_metric_vs_training_samples_by_model(
    #     results_table=results_table,
    #     metric="RMSLE",
    # )


def plot_rmse_and_rmsle_all_models(results_table):
    """
    Convenience function that creates summary RMSE and RMSLE plots
    with all models together.
    """

    plot_metric_vs_training_samples_all_models(
        results_table=results_table,
        metric="RMSE",
    )

    # plot_metric_vs_training_samples_all_models(
    #     results_table=results_table,
    #     metric="RMSLE",
    # )