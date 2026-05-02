from pathlib import Path
import sqlite3
import pandas as pd


class DatabaseManager:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.connection = None

    def connect(self):
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        self.connection = sqlite3.connect(self.db_path)
        return self.connection

    def query(self, sql: str) -> pd.DataFrame:
        if self.connection is None:
            self.connect()

        return pd.read_sql_query(sql, self.connection)

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None


class DataLoader:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def load_table(self, table_name: str) -> pd.DataFrame:
        return self.db.query(f"SELECT * FROM {table_name}")

    def load_prices(self) -> pd.DataFrame:
        return self.load_table("Prices")

    def load_volumes(self) -> pd.DataFrame:
        return self.load_table("Volumes")

    def load_flows(self) -> pd.DataFrame:
        return self.load_table("Flows")

    def load_capacities(self) -> pd.DataFrame:
        return self.load_table("Capacities")

    def load_bidding_zones(self) -> pd.DataFrame:
        return self.load_table("BiddingZones")


class DataPreprocessor:
    def create_datetime_index(
        self,
        df: pd.DataFrame,
        date_col: str = "delivery_day",
        hour_col: str = "hour",
        timezone: str = "Europe/Oslo",
        convert_to_utc: bool = True
    ) -> pd.DataFrame:

        df = df.copy()

        df["datetime"] = (
            pd.to_datetime(df[date_col])
            + pd.to_timedelta(df[hour_col], unit="h")
        )

        df = df.sort_values("datetime")

        if convert_to_utc:
            df["datetime"] = (
                df["datetime"]
                .dt.tz_localize(
                    timezone,
                    ambiguous="infer",
                    nonexistent="shift_forward"
                )
                .dt.tz_convert("UTC")
                .dt.tz_localize(None)
            )

        df = df.sort_values("datetime")
        df = df.set_index("datetime")

        return df

    def filter_zones(
        self,
        df: pd.DataFrame,
        zone_col: str,
        zones: int | list[int]
    ) -> pd.DataFrame:

        df = df.copy()

        if isinstance(zones, int):
            zones = [zones]

        return df[df[zone_col].isin(zones)].copy()

    def filter_dates(
        self,
        df: pd.DataFrame,
        start_date: str | None = None,
        end_date: str | None = None
    ) -> pd.DataFrame:

        df = df.copy()

        if start_date is not None:
            df = df[df.index >= start_date]

        if end_date is not None:
            df = df[df.index <= end_date]

        return df

    def clean_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.dropna().copy()


class FeatureEngineer:
    def add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        df["year"] = df.index.year
        df["month"] = df.index.month
        df["day"] = df.index.day
        df["hour"] = df.index.hour
        df["day_of_week"] = df.index.dayofweek

        return df

    def add_lag_features(
        self,
        df: pd.DataFrame,
        value_col: str = "price_value",
        lags: list[int] = [1, 2, 24]
    ) -> pd.DataFrame:

        df = df.copy()

        for lag in lags:
            df[f"{value_col}_lag_{lag}"] = df[value_col].shift(lag)

        return df

    def add_target(
        self,
        df: pd.DataFrame,
        value_col: str = "price_value",
        horizon: int = 1
    ) -> pd.DataFrame:

        df = df.copy()
        df["target"] = df[value_col].shift(-horizon)

        return df


class ModelDatasetBuilder:
    def __init__(self, db_path: str | Path):
        self.db = DatabaseManager(db_path)
        self.loader = DataLoader(self.db)
        self.preprocessor = DataPreprocessor()
        self.features = FeatureEngineer()

    def _get_zone_ids(
        self,
        zones: str | list[str] | int | list[int] | None
    ) -> list[int] | None:
        """
        Converts zone names like 'NO1' or ['NO1', 'NO2'] into zone_id values.
        If zone IDs are already provided, returns them directly.
        """
        if zones is None:
            return None

        if not isinstance(zones, list):
            zones = [zones]

        if isinstance(zones[0], str):
            bidding_zones = self.loader.load_bidding_zones()

            zone_map = (
                bidding_zones
                .set_index("zone_code")["zone_id"]
                .to_dict()
            )

            missing_zones = [zone for zone in zones if zone not in zone_map]

            if missing_zones:
                raise ValueError(f"Zones not found in database: {missing_zones}")

            return [zone_map[zone] for zone in zones]

        return zones

    def build_price_dataset(
        self,
        zones: str | list[str] | int | list[int] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        value_col: str = "price_value",
        add_time_features: bool = False,
        lags: list[int] | None = None,
        target_horizon: int | None = None,
        dropna: bool = False
    ) -> pd.DataFrame:
        """
        General price dataset builder.

        Can be used for:
        - Traditional models: ARIMA, ARIMAX, SARIMA
        - Machine Learning models: Random Forest, XGBoost, etc.
        - Event-based models
        - Future GNN models

        By default, it only returns a clean base dataset.
        Extra ML features are added only if requested.
        """

        df = self.loader.load_prices()

        zone_ids = self._get_zone_ids(zones)

        if zone_ids is not None:
            df = self.preprocessor.filter_zones(
                df,
                zone_col="zone_id",
                zones=zone_ids
            )

        df = self.preprocessor.create_datetime_index(df)

        df = self.preprocessor.filter_dates(
            df,
            start_date=start_date,
            end_date=end_date
        )

        df = df.sort_index()

        if add_time_features:
            df = self.features.add_time_features(df)

        if lags is not None:
            df = self.features.add_lag_features(
                df,
                value_col=value_col,
                lags=lags
            )

        if target_horizon is not None:
            df = self.features.add_target(
                df,
                value_col=value_col,
                horizon=target_horizon
            )

        if dropna:
            df = self.preprocessor.clean_missing_values(df)

        return df

    def close(self):
        self.db.close()