"""
Smart retrieval: given a user query and a dataframe, return a relevant subset.

Strategy:
1. Ask the LLM to generate a pandas filter expression based on the query + column info
2. Apply the filter
3. If the filter returns too many rows, apply keyword search on top
4. If filter fails or returns nothing, fall back to keyword search
5. If all else fails, return a representative sample
"""

import re
import pandas as pd
from src.config import LLMConfig
from src.llm_client import chat

MAX_ROWS_FOR_CONTEXT = 150  # Rows to pass to the analysis LLM
FILTER_PROMPT_TEMPLATE = """You are a data analyst assistant. Given a pandas DataFrame with the following columns and sample data, generate a Python pandas filter expression to retrieve rows relevant to the user's question.

COLUMNS AND TYPES:
{column_info}

SAMPLE VALUES (first 3 rows):
{sample_rows}

USER QUESTION:
{question}

Respond with ONLY a valid pandas filter expression (the part that goes inside df[...]).
Examples:
  df['asset'] == 'P-101'
  df['status'].str.lower().str.contains('open', na=False)
  (df['asset'] == 'K-201') & (df['status'].str.lower() == 'open')
  df['date'] >= '2024-01-01'

If the question is broad (e.g. "summarise all findings") or cannot be filtered, respond with: ALL
Do not include any explanation. Only the expression or ALL."""


def _build_column_info(df: pd.DataFrame) -> str:
    lines = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        sample = df[col].dropna().unique()[:5].tolist()
        lines.append(f"  {col!r} ({dtype}): e.g. {sample}")
    return "\n".join(lines)


def _apply_filter_expression(df: pd.DataFrame, expr: str) -> pd.DataFrame | None:
    """Safely evaluate a filter expression. Returns None if it fails."""
    try:
        # Sanitise: only allow eval in restricted context
        result = df[eval(expr, {"df": df, "pd": pd, "__builtins__": {}})]
        if isinstance(result, pd.DataFrame):
            return result
    except Exception:
        pass
    return None


def _keyword_search(df: pd.DataFrame, query: str, text_cols: list[str]) -> pd.DataFrame:
    """Simple keyword search across text columns."""
    if not text_cols:
        return df.sample(min(MAX_ROWS_FOR_CONTEXT, len(df)))

    keywords = [w.lower() for w in query.split() if len(w) > 3]
    if not keywords:
        return df.sample(min(MAX_ROWS_FOR_CONTEXT, len(df)))

    mask = pd.Series([False] * len(df), index=df.index)
    for col in text_cols:
        if col in df.columns:
            col_lower = df[col].astype(str).str.lower()
            for kw in keywords:
                mask = mask | col_lower.str.contains(kw, na=False)

    results = df[mask]
    if len(results) == 0:
        # Nothing matched — return sample
        return df.sample(min(MAX_ROWS_FOR_CONTEXT, len(df)))
    return results


def retrieve(
    df: pd.DataFrame,
    query: str,
    col_map: dict,
    config: LLMConfig,
) -> tuple[pd.DataFrame, str]:
    """
    Returns (relevant_subset_df, retrieval_method_description)
    """
    # Identify text columns for keyword fallback
    text_cols = [v for v in [col_map.get("finding_col"), col_map.get("asset_col")] if v]

    # Step 1: Ask LLM for a filter expression
    column_info = _build_column_info(df)
    sample_rows = df.head(3).to_csv(index=False)

    filter_prompt = FILTER_PROMPT_TEMPLATE.format(
        column_info=column_info,
        sample_rows=sample_rows,
        question=query,
    )

    try:
        filter_expr = chat(
            messages=[{"role": "user", "content": filter_prompt}],
            config=config,
            temperature=0.0,
            max_tokens=200,
        ).strip()
    except Exception as e:
        # LLM call failed — fall back to keyword search
        subset = _keyword_search(df, query, text_cols)
        return subset.head(MAX_ROWS_FOR_CONTEXT), f"keyword search (LLM unavailable: {e})"

    # Step 2: Apply filter
    if filter_expr.upper() == "ALL" or not filter_expr:
        # Broad query — use keyword search or sample
        subset = _keyword_search(df, query, text_cols)
        method = "keyword search (broad query)"
    else:
        filtered = _apply_filter_expression(df, filter_expr)
        if filtered is not None and len(filtered) > 0:
            subset = filtered
            method = f"pandas filter: `{filter_expr}` → {len(filtered)} rows"
        else:
            # Filter returned nothing or failed — fall back to keyword
            subset = _keyword_search(df, query, text_cols)
            method = f"keyword search (filter failed or empty: `{filter_expr}`)"

    # Step 3: Trim to context limit
    if len(subset) > MAX_ROWS_FOR_CONTEXT:
        subset = subset.head(MAX_ROWS_FOR_CONTEXT)
        method += f" [trimmed to {MAX_ROWS_FOR_CONTEXT}]"

    return subset, method
