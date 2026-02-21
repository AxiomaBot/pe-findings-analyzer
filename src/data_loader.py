"""
CSV loading, validation, and column detection.
"""

import pandas as pd
from typing import Optional
import io


def load_csv(file) -> pd.DataFrame:
    """Load a CSV from a Streamlit UploadedFile or file path."""
    if hasattr(file, "read"):
        content = file.read()
        # Try UTF-8 first, fall back to latin-1 (common in European corporate systems)
        try:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(content), encoding="latin-1")
    else:
        try:
            df = pd.read_csv(file, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file, encoding="latin-1")

    # Clean column names: strip whitespace
    df.columns = df.columns.str.strip()
    return df


def detect_columns(df: pd.DataFrame) -> dict:
    """
    Heuristic detection of key column roles.
    Returns a dict with best guesses for:
      - finding_col: the free-form text/annotation column
      - asset_col: asset identifier
      - date_col: date of finding
      - status_col: open/closed/resolved etc.
      - location_col: functional location
    """
    cols_lower = {c.lower(): c for c in df.columns}

    def find(candidates):
        for c in candidates:
            if c in cols_lower:
                return cols_lower[c]
        # Partial match fallback
        for c in candidates:
            for col_l, col in cols_lower.items():
                if c in col_l:
                    return col
        return None

    finding_col = find([
        "finding", "annotation", "observation", "comment", "description",
        "text", "note", "remarks", "detail"
    ])
    asset_col = find([
        "asset", "tag", "equipment", "unit", "machine", "device"
    ])
    location_col = find([
        "functional location", "floc", "functional_location", "location", "area", "plant"
    ])
    date_col = find([
        "date", "timestamp", "created", "recorded", "reported", "raised"
    ])
    status_col = find([
        "status", "state", "resolution", "resolved", "open", "closed"
    ])

    return {
        "finding_col": finding_col,
        "asset_col": asset_col,
        "location_col": location_col,
        "date_col": date_col,
        "status_col": status_col,
    }


def get_dataset_summary(df: pd.DataFrame, col_map: dict) -> str:
    """Generate a plain-text summary of the dataset for use in LLM prompts."""
    lines = [
        f"Dataset: {len(df):,} rows, {len(df.columns)} columns.",
        f"Columns: {', '.join(df.columns.tolist())}",
    ]

    if col_map.get("asset_col") and col_map["asset_col"] in df.columns:
        n_assets = df[col_map["asset_col"]].nunique()
        top_assets = df[col_map["asset_col"]].value_counts().head(5).to_dict()
        lines.append(f"Unique assets: {n_assets}")
        lines.append(f"Top assets by finding count: {top_assets}")

    if col_map.get("date_col") and col_map["date_col"] in df.columns:
        try:
            dates = pd.to_datetime(df[col_map["date_col"]], errors="coerce").dropna()
            if len(dates):
                lines.append(f"Date range: {dates.min().date()} to {dates.max().date()}")
        except Exception:
            pass

    if col_map.get("status_col") and col_map["status_col"] in df.columns:
        status_counts = df[col_map["status_col"]].value_counts().to_dict()
        lines.append(f"Status breakdown: {status_counts}")

    return "\n".join(lines)


def dataframe_to_text(df: pd.DataFrame, max_rows: int = 200) -> str:
    """Convert a (filtered) dataframe to a plain-text representation for LLM context."""
    if len(df) > max_rows:
        df = df.head(max_rows)
        truncated = True
    else:
        truncated = False

    text = df.to_csv(index=False)
    if truncated:
        text += f"\n[Truncated to {max_rows} rows]"
    return text
