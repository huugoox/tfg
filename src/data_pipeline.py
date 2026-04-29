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

    def load_prices(self) -> pd.DataFrame:
        return self.db.query("SELECT * FROM Prices")

    def load_volumes(self) -> pd.DataFrame:
        return self.db.query("SELECT * FROM Volumes")

    def load_flows(self) -> pd.DataFrame:
        return self.db.query("SELECT * FROM Flows")

    def load_capacities(self) -> pd.DataFrame:
        return self.db.query("SELECT * FROM Capacities")

    def load_bidding_zones(self) -> pd.DataFrame:
        return self.db.query("SELECT * FROM BiddingZones")


class Preprocessor:
    def clean_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.dropna().copy()

    def create_time_features(
        self,
        df: pd.DataFrame,
        datetime_col: str
    ) -> pd.DataFrame:
        df = df.copy()
        df[datetime_col] = pd.to_datetime(df[datetime_col])

        df["year"] = df[datetime_col].dt.year
        df["month"] = df[datetime_col].dt.month
        df["day"] = df[datetime_col].dt.day
        df["hour"] = df[datetime_col].dt.hour
        df["day_of_week"] = df[datetime_col].dt.dayofweek

        return df

    def filter_year(
        self,
        df: pd.DataFrame,
        datetime_col: str,
        year: int
    ) -> pd.DataFrame:
        df = df.copy()
        df[datetime_col] = pd.to_datetime(df[datetime_col])
        return df[df[datetime_col].dt.year == year].copy()

    def filter_zones(
        self,
        df: pd.DataFrame,
        zone_col: str,
        zones: list[str]
    ) -> pd.DataFrame:
        return df[df[zone_col].isin(zones)].copy()