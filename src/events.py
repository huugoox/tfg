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

        buy_p10 = df.groupby("zone_id")["buy_volume_value"].transform(lambda x: x.quantile(0.10))
        buy_p90 = df.groupby("zone_id")["buy_volume_value"].transform(lambda x: x.quantile(0.90))
        sell_p90 = df.groupby("zone_id")["sell_volume_value"].transform(lambda x: x.quantile(0.90))

        df["high_demand"] = df["buy_volume_value"] > buy_p90
        df["low_demand"] = df["buy_volume_value"] < buy_p10
        df["high_generation"] = df["sell_volume_value"] > sell_p90

        return df

    def detect_flow_events(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = df.sort_values(["from_zone_id", "to_zone_id", "datetime"])

        df["abs_flow"] = df["flow_value"].abs()

        flow_p90 = df.groupby(["from_zone_id", "to_zone_id"])["abs_flow"].transform(lambda x: x.quantile(0.90))

        df["flow_delta"] = df.groupby(["from_zone_id", "to_zone_id"])["flow_value"].diff()
        df["abs_flow_delta"] = df["flow_delta"].abs()

        delta_p90 = df.groupby(["from_zone_id", "to_zone_id"])["abs_flow_delta"].transform(lambda x: x.quantile(0.90))

        previous_flow = df.groupby(["from_zone_id", "to_zone_id"])["flow_value"].shift(1)

        df["high_flow"] = df["abs_flow"] > flow_p90
        df["flow_spike"] = df["abs_flow_delta"] > delta_p90
        df["flow_reversal"] = np.sign(df["flow_value"]) != np.sign(previous_flow)

        df.loc[previous_flow.isna(), "flow_reversal"] = False

        return df