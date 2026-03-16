"""
data_loader.py
Loads all accident CSVs once at startup into pandas DataFrames.
Auto-detects files by matching filename fragments defined in DATASET_REGISTRY.
"""

import os
import glob
import pandas as pd
from typing import Optional, List, Dict, Any

# ── Registry: dataset key → fragment that must appear in the CSV filename ──────
DATASET_REGISTRY = {
    "road_features_2019":      "Road_Features_2019",
    "road_features_2020":      "Road_Features_2020",
    "vehicles_2020":           "Impacting_Vehicles_2020",
    "junctions_2019":          "Junctions_2019",
    "junctions_2020":          "Junctions_2020",
    "traffic_control_2019":    "Traffic_Control_2019",
    "traffic_control_2020":    "Traffic_Control_2020",
    "traffic_violations_2019": "Traffic_Violations_2019",
    "traffic_violations_2020": "Traffic_Violations_2020",
    "weather_2019":            "Weather_2019",
    "weather_2020":            "Weather_2020",
    "weather_2021":            "Weather_2021",
    "road_defects_2006_2016":  "Road_Defects",
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "csv")


class DataLoader:
    def __init__(self):
        self._frames: Dict[str, pd.DataFrame] = {}
        self._meta: Dict[str, Dict] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def load_all(self):
        csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
        print(f"[DataLoader] Found {len(csv_files)} CSV(s) in {DATA_DIR}")
        for key, fragment in DATASET_REGISTRY.items():
            matched = [f for f in csv_files
                       if fragment.lower() in os.path.basename(f).lower()]
            if matched:
                self._load(key, matched[0])
            else:
                print(f"[DataLoader] WARNING: no CSV matched for key='{key}' "
                      f"(looking for '{fragment}')")

    def get(self, key: str) -> Optional[pd.DataFrame]:
        return self._frames.get(key)

    def available_datasets(self) -> List[Dict]:
        return list(self._meta.values())

    def get_cities(self, dataset_key: Optional[str] = None) -> List[str]:
        if dataset_key:
            df = self.get(dataset_key)
            if df is None or "city" not in df.columns:
                return []
            return sorted(df["city"].dropna().unique().tolist())
        cities: set = set()
        for df in self._frames.values():
            if "city" in df.columns:
                cities.update(df["city"].dropna().unique().tolist())
        return sorted(list(cities))

    def get_years(self) -> List[int]:
        years = set()
        for key in self._frames:
            for y in ["2019", "2020", "2021", "2006", "2016"]:
                if y in key:
                    years.add(int(y))
        return sorted(list(years))

    def query(
        self,
        key: str,
        city: Optional[str] = None,
        sort_by: Optional[str] = None,
        ascending: bool = True,
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        df = self.get(key)
        if df is None:
            raise KeyError(f"Dataset '{key}' is not loaded.")
        if city and "city" in df.columns:
            df = df[df["city"].str.lower() == city.lower()]
        if sort_by and sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=ascending)
        if top_n:
            df = df.head(top_n)
        return df.to_dict(orient="records")

    def summarize(
        self,
        key: str,
        group_col: str = "city",
        value_col: Optional[str] = None,
    ) -> Dict[str, Any]:
        df = self.get(key)
        if df is None:
            raise KeyError(f"Dataset '{key}' is not loaded.")
        if group_col not in df.columns:
            raise ValueError(f"Column '{group_col}' not found in dataset '{key}'.")
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if value_col:
            if value_col not in df.columns:
                raise ValueError(f"Column '{value_col}' not found.")
            agg = df.groupby(group_col)[value_col].sum().sort_values(ascending=False)
            return {"grouped_by": group_col, "value": value_col,
                    "data": agg.to_dict()}
        agg = df.groupby(group_col)[num_cols].sum()
        return {"grouped_by": group_col, "columns": num_cols,
                "data": agg.to_dict(orient="index")}

    # ── Private helpers ───────────────────────────────────────────────────────

    def _load(self, key: str, path: str):
        try:
            df = pd.read_csv(path, encoding="utf-8",
                             na_values=["", "NA", "N/A", "-"])
            # Normalise column names
            df.columns = [c.strip().lower().replace(" ", "_")
                          for c in df.columns]
            # Rename city-like columns
            for col in df.columns:
                if "city" in col:
                    df.rename(columns={col: "city"}, inplace=True)
                    break
            df.dropna(how="all", inplace=True)
            num_cols = df.select_dtypes(include="number").columns
            df[num_cols] = df[num_cols].fillna(0)
            self._frames[key] = df
            self._meta[key] = {
                "key": key,
                "rows": len(df),
                "columns": list(df.columns),
                "file": os.path.basename(path),
            }
            print(f"[DataLoader] Loaded '{key}': {len(df)} rows, "
                  f"{len(df.columns)} columns")
        except Exception as exc:
            print(f"[DataLoader] ERROR loading '{key}' from {path}: {exc}")


# Singleton – imported by routers and main
loader = DataLoader()
