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
        """ Detects simple flow-based events for each directed interconnection.

        Expected columns:
        - from_zone_id
        - to_zone_id
        - datetime
        - flow_value
        """

        df = df.copy()

        # -------------------------
        # Handle datetime as column or index
        # -------------------------

        datetime_was_index = False

        if "datetime" not in df.columns:
            if isinstance(df.index, pd.DatetimeIndex):
                datetime_was_index = True
                df = df.reset_index()

                if "index" in df.columns:
                    df = df.rename(columns={"index": "datetime"})
            else:
                raise ValueError(
                    "Missing required column 'datetime', and index is not a DatetimeIndex."
                )

        required_columns = [
            "from_zone_id",
            "to_zone_id",
            "datetime",
            "flow_value",
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise ValueError(
                f"Missing required columns for flow event detection: {missing_columns}"
            )

        df = df.sort_values(["from_zone_id", "to_zone_id", "datetime"])

        # -------------------------
        # Absolute flow
        # -------------------------

        df["abs_flow_value"] = df["flow_value"].abs()

        # -------------------------
        # Flow thresholds per directed edge
        # -------------------------

        edge_group = df.groupby(["from_zone_id", "to_zone_id"])

        flow_p10 = edge_group["abs_flow_value"].transform(
            lambda x: x.quantile(0.10)
        )

        flow_p90 = edge_group["abs_flow_value"].transform(
            lambda x: x.quantile(0.90)
        )

        # -------------------------
        # Basic flow level events
        # -------------------------

        df["low_flow"] = df["abs_flow_value"] < flow_p10
        df["high_flow"] = df["abs_flow_value"] > flow_p90

        # -------------------------
        # Dynamic flow events
        # -------------------------

        df["flow_delta"] = edge_group["flow_value"].diff()
        df["abs_flow_delta"] = df["flow_delta"].abs()

        flow_delta_p95 = edge_group["abs_flow_delta"].transform(
            lambda x: x.quantile(0.95)
        )

        df["flow_spike"] = df["abs_flow_delta"] > flow_delta_p95

        # -------------------------
        # Flow reversal
        # -------------------------
        # A reversal happens when the sign of the flow changes
        # compared with the previous hour for the same directed edge.

        df["flow_sign"] = np.sign(df["flow_value"])
        df["previous_flow_sign"] = edge_group["flow_sign"].shift(1)

        df["flow_reversal"] = (
            (df["flow_sign"] != df["previous_flow_sign"]) &
            df["previous_flow_sign"].notna() &
            (df["flow_sign"] != 0) &
            (df["previous_flow_sign"] != 0)
        )

        # -------------------------
        # General flow event flag
        # -------------------------

        flow_event_columns = [
            "low_flow",
            "high_flow",
            "flow_spike",
            "flow_reversal",
        ]

        df["has_flow_event"] = df[flow_event_columns].any(axis=1)

        # -------------------------
        # Restore datetime index if needed
        # -------------------------

        if datetime_was_index:
            df = df.set_index("datetime")

        return df
    
    
class CombinedEventDetector:
    """
    Combined events based only on price and volume signals.

    Assumes that the dataframe already contains the columns generated by:
    - SimpleEventDetector.detect_price_events()
    - SimpleEventDetector.detect_volume_events()

    Flow / capacity related events are intentionally excluded.
    """

    def detect_combined_events(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        datetime_was_index = False

        # --------------------------------------------------
        # Handle datetime as column or index
        # --------------------------------------------------

        if "datetime" not in df.columns:
            if isinstance(df.index, pd.DatetimeIndex):
                datetime_was_index = True
                df = df.reset_index()

                if "index" in df.columns:
                    df = df.rename(columns={"index": "datetime"})
                elif df.columns[0] != "datetime":
                    df = df.rename(columns={df.columns[0]: "datetime"})
            else:
                raise ValueError(
                    "Missing required column 'datetime', and index is not a DatetimeIndex."
                )

        df = df.sort_values(["zone_id", "datetime"])

        required_columns = [
            "zone_id",
            "datetime",
            "price_value",
            "buy_volume_value",
            "sell_volume_value",
            "high_demand",
            "low_demand",
            "high_generation",
            "low_generation",
            "price_spike",
            "high_price",
            "low_price",
            "strong_buy_pressure",
            "strong_sell_pressure",
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(
                f"Missing required columns for combined event detection: {missing_columns}. "
                "Run detect_price_events() and detect_volume_events() first."
            )

        # --------------------------------------------------
        # Volume-based combined events
        # --------------------------------------------------

        df["generation_surplus"] = (
            df["high_generation"] &
            df["low_demand"]
        )

        df["demand_pressure"] = (
            df["high_demand"] &
            df["low_generation"]
        )

        df["strong_demand_pressure"] = (
            df["high_demand"] &
            df["strong_buy_pressure"]
        )

        df["strong_generation_pressure"] = (
            df["high_generation"] &
            df["strong_sell_pressure"]
        )

        # --------------------------------------------------
        # Price + volume combined events
        # --------------------------------------------------

        df["demand_driven_price_spike"] = (
            df["high_demand"] &
            df["price_spike"]
        )

        df["generation_driven_low_price"] = (
            df["high_generation"] &
            df["low_price"]
        )

        df["scarcity_price_event"] = (
            df["high_demand"] &
            df["low_generation"] &
            df["high_price"]
        )

        df["oversupply_price_event"] = (
            df["high_generation"] &
            df["low_demand"] &
            df["low_price"]
        )

        df["buy_pressure_price_spike"] = (
            df["price_spike"] &
            df["strong_buy_pressure"]
        )

        df["sell_pressure_low_price"] = (
            df["low_price"] &
            df["strong_sell_pressure"]
        )

        # --------------------------------------------------
        # Price separation across zones
        # --------------------------------------------------
        # With a single zone, these events will usually be False.

        df["system_price_max"] = df.groupby("datetime")["price_value"].transform("max")
        df["system_price_min"] = df.groupby("datetime")["price_value"].transform("min")
        df["system_price_spread"] = df["system_price_max"] - df["system_price_min"]

        spread_p90 = df["system_price_spread"].quantile(0.90)
        spread_p95 = df["system_price_spread"].quantile(0.95)

        df["price_separation"] = df["system_price_spread"] > spread_p90
        df["extreme_price_separation"] = df["system_price_spread"] > spread_p95

        df["system_price_median"] = df.groupby("datetime")["price_value"].transform("median")
        df["price_deviation_from_system"] = (
            df["price_value"] - df["system_price_median"]
        ).abs()

        deviation_p90 = df.groupby("zone_id")["price_deviation_from_system"].transform(
            lambda x: x.quantile(0.90)
        )

        df["zone_price_outlier"] = (
            df["price_separation"] &
            (df["price_deviation_from_system"] > deviation_p90)
        )

        # --------------------------------------------------
        # Combined event flag
        # --------------------------------------------------

        combined_event_columns = [
            "generation_surplus",
            "demand_pressure",
            "strong_demand_pressure",
            "strong_generation_pressure",
            "demand_driven_price_spike",
            "generation_driven_low_price",
            "scarcity_price_event",
            "oversupply_price_event",
            "buy_pressure_price_spike",
            "sell_pressure_low_price",
            "price_separation",
            "extreme_price_separation",
            "zone_price_outlier",
        ]

        df["has_combined_event"] = df[combined_event_columns].any(axis=1)

        # --------------------------------------------------
        # Restore datetime index if it was originally the index
        # --------------------------------------------------

        if datetime_was_index:
            df = df.set_index("datetime")

        return df
