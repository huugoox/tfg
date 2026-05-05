import pandas as pd
import numpy as np


class SimpleEventDetector:

    def detect_price_events(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = df.sort_values(["zone_id", "datetime"])

        # Price thresholds per zone
        p10 = df.groupby("zone_id")["price_value"].transform(lambda x: x.quantile(0.10))
        p90 = df.groupby("zone_id")["price_value"].transform(lambda x: x.quantile(0.90))
        p95 = df.groupby("zone_id")["price_value"].transform(lambda x: x.quantile(0.95))
        p99 = df.groupby("zone_id")["price_value"].transform(lambda x: x.quantile(0.99))

        # Hourly price change
        df["price_delta"] = df.groupby("zone_id")["price_value"].diff()
        df["abs_price_delta"] = df["price_delta"].abs()

        # Price change thresholds per zone
        delta_abs_p95 = df.groupby("zone_id")["abs_price_delta"].transform(lambda x: x.quantile(0.95))
        delta_up_p95 = df.groupby("zone_id")["price_delta"].transform(lambda x: x.quantile(0.95))
        delta_down_p05 = df.groupby("zone_id")["price_delta"].transform(lambda x: x.quantile(0.05))

        # Rolling volatility
        df["rolling_volatility_24h"] = (
            df.groupby("zone_id")["price_value"]
            .transform(lambda x: x.rolling(window=24, min_periods=6).std())
        )

        volatility_p90 = df.groupby("zone_id")["rolling_volatility_24h"].transform(
            lambda x: x.quantile(0.90)
        )

        # Price level events
        df["low_price"] = df["price_value"] < p10
        df["high_price"] = df["price_value"] > p90
        df["price_spike"] = df["price_value"] > p95
        df["extreme_price"] = df["price_value"] > p99

        # Dynamic price events
        df["rapid_price_change"] = df["abs_price_delta"] > delta_abs_p95
        df["price_ramp_up"] = df["price_delta"] > delta_up_p95
        df["price_ramp_down"] = df["price_delta"] < delta_down_p05

        # Volatility regime
        df["high_volatility"] = df["rolling_volatility_24h"] > volatility_p90

        return df


    def detect_volume_events(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = df.sort_values(["zone_id", "datetime"])

        # -------------------------
        # Volume level thresholds per zone
        # -------------------------

        buy_p10 = df.groupby("zone_id")["buy_volume_value"].transform(
            lambda x: x.quantile(0.10)
        )
        buy_p90 = df.groupby("zone_id")["buy_volume_value"].transform(
            lambda x: x.quantile(0.90)
        )

        sell_p10 = df.groupby("zone_id")["sell_volume_value"].transform(
            lambda x: x.quantile(0.10)
        )
        sell_p90 = df.groupby("zone_id")["sell_volume_value"].transform(
            lambda x: x.quantile(0.90)
        )

        # -------------------------
        # Basic volume events
        # -------------------------

        df["high_demand"] = df["buy_volume_value"] > buy_p90
        df["low_demand"] = df["buy_volume_value"] < buy_p10

        df["high_generation"] = df["sell_volume_value"] > sell_p90
        df["low_generation"] = df["sell_volume_value"] < sell_p10

        # -------------------------
        # Buy / sell pressure
        # -------------------------

        df["volume_imbalance"] = (
            df["buy_volume_value"] - df["sell_volume_value"]
        ) / (
            df["buy_volume_value"] + df["sell_volume_value"] + 1e-9
        )

        imbalance_p10 = df.groupby("zone_id")["volume_imbalance"].transform(
            lambda x: x.quantile(0.10)
        )
        imbalance_p90 = df.groupby("zone_id")["volume_imbalance"].transform(
            lambda x: x.quantile(0.90)
        )

        df["strong_buy_pressure"] = df["volume_imbalance"] > imbalance_p90
        df["strong_sell_pressure"] = df["volume_imbalance"] < imbalance_p10

        # -------------------------
        # Dynamic volume events
        # -------------------------

        df["buy_volume_delta"] = df.groupby("zone_id")["buy_volume_value"].diff()
        df["sell_volume_delta"] = df.groupby("zone_id")["sell_volume_value"].diff()

        df["abs_buy_volume_delta"] = df["buy_volume_delta"].abs()
        df["abs_sell_volume_delta"] = df["sell_volume_delta"].abs()

        buy_delta_p95 = df.groupby("zone_id")["abs_buy_volume_delta"].transform(
            lambda x: x.quantile(0.95)
        )
        sell_delta_p95 = df.groupby("zone_id")["abs_sell_volume_delta"].transform(
            lambda x: x.quantile(0.95)
        )

        df["buy_volume_spike"] = df["abs_buy_volume_delta"] > buy_delta_p95
        df["sell_volume_spike"] = df["abs_sell_volume_delta"] > sell_delta_p95

        return df

    def detect_flow_events(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = df.sort_values(["from_zone_id", "to_zone_id", "datetime"])

        group_cols = ["from_zone_id", "to_zone_id"]

        # -------------------------
        # Flow magnitude
        # -------------------------

        df["abs_flow"] = df["flow_value"].abs()

        flow_p90 = df.groupby(group_cols)["abs_flow"].transform(
            lambda x: x.quantile(0.90)
        )

        # -------------------------
        # Flow changes
        # -------------------------

        df["flow_delta"] = df.groupby(group_cols)["flow_value"].diff()
        df["abs_flow_delta"] = df["flow_delta"].abs()

        delta_p90 = df.groupby(group_cols)["abs_flow_delta"].transform(
            lambda x: x.quantile(0.90)
        )

        # -------------------------
        # Previous flow
        # -------------------------

        previous_flow = df.groupby(group_cols)["flow_value"].shift(1)

        # Threshold to avoid fake reversals around zero
        flow_min_threshold = df.groupby(group_cols)["abs_flow"].transform(
            lambda x: x.quantile(0.10)
        )

        # -------------------------
        # Flow events
        # -------------------------

        df["high_flow"] = df["abs_flow"] > flow_p90

        df["flow_spike"] = df["abs_flow_delta"] > delta_p90

        df["flow_reversal"] = (
            (np.sign(df["flow_value"]) != np.sign(previous_flow)) &
            (df["flow_value"].abs() > flow_min_threshold) &
            (previous_flow.abs() > flow_min_threshold)
        )

        df.loc[previous_flow.isna(), "flow_reversal"] = False

        return df