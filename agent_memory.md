# agent_memory.md
# Machine-readable codebase context. Not for humans.

## Purpose
Streamlit app for natural-language analysis of a production efficiency (PE) findings/annotations database.
Domain: oil/gas or industrial process operations. Users are process engineers.
Core loop: upload CSV → chat → LLM analyses relevant subset → response.

## Key Domain Concepts
- **PE (Production Efficiency)**: how close actual production is to maximum production potential (MPP).
- **Finding/Annotation**: a free-text observation logged by an engineer about an asset's behaviour or trend.
- **Asset**: a physical piece of equipment (pump, compressor, heat exchanger, vessel). Referenced by tag (e.g. P-101, K-201).
- **Functional Location (FLOC)**: hierarchical location string (e.g. AREA-B/COMP-201).
- **Status**: typically Open/Closed/Resolved — whether the finding has been actioned.
- Dataset scale: ~10,000 rows expected. Cannot fit in context window. Retrieval is mandatory.

## File Map
```
app.py                  Streamlit entrypoint. All UI logic lives here.
src/config.py           LLMConfig dataclass. Reads .env or accepts UI overrides.
src/data_loader.py      CSV loading (utf-8/latin-1), column detection heuristics, df→text serialisation.
src/llm_client.py       Thin LiteLLM wrapper. chat() and check_connection(). Passes api_key/api_base through.
src/retriever.py        Two-stage retrieval: LLM generates pandas filter → apply → keyword fallback → sample fallback.
sample_data/example.csv 15-row synthetic dataset. Columns: date, asset, functional_location, finding, status, engineer, severity.
.env.example            LLM config template.
requirements.txt        streamlit, pandas, litellm, python-dotenv, openpyxl.
```

## Architecture: Data Flow Per Query
```
user_query
  → retriever.retrieve(df, query, col_map, llm_config)
      → LLM call 1: generate pandas filter expression (temp=0.0, max_tokens=200)
      → eval filter on df → filtered_df
      → fallback: keyword search on finding_col + asset_col if filter fails/empty
      → trim to MAX_ROWS_FOR_CONTEXT (150)
  → dataframe_to_text(subset)  # CSV string, max 200 rows
  → LLM call 2: system prompt (dataset summary) + last 3 conversation turns + user query + context rows
  → response rendered in st.chat_message
```

## LLM Integration: LiteLLM
- Model string format: `{provider}/{model}` e.g. `openai/gpt-4o`, `anthropic/claude-3-5-sonnet-20241022`, `ollama/llama3.2`
- kwargs: `model`, `messages`, `temperature`, `max_tokens`, optionally `api_key`, `api_base`
- Fully agnostic — caller sets provider, model, key, base URL. No hardcoded provider logic.
- Two calls per query (retrieval filter + analysis). Known bottleneck; not yet optimised.

## State: st.session_state Keys
```
df              pd.DataFrame    Loaded CSV
col_map         dict            Keys: finding_col, asset_col, date_col, status_col, location_col. Values: column name strings or None.
summary         str             Plain-text dataset summary (row count, top assets, date range, status breakdown)
last_file       str             Filename of last uploaded file (used to detect re-upload)
messages        list[dict]      Chat history. Each: {role, content, retrieval_info?}
```

## col_map Keys (critical for retrieval)
```
finding_col     Free-form text field — the actual finding/annotation. Primary text search target.
asset_col       Asset tag or name. High-cardinality string. Used in filter expressions.
date_col        Date of finding. Parsed with pd.to_datetime(errors='coerce').
status_col      Open/Closed/etc. Used for status breakdown and filter expressions.
location_col    Functional location string. Secondary identifier.
```

## Known Gaps / TODO
1. **Broad queries**: no aggregation strategy. "Summarise all findings" → keyword search → 150 rows → response misses 99% of data. Fix: pre-aggregate (groupby asset, value_counts, theme clustering) before LLM call.
2. **Column detection**: heuristic string matching. Will fail on unusual column names. Real schema unknown until user uploads data.
3. **Filter eval security**: uses `eval()` with restricted builtins `{"df": df, "pd": pd, "__builtins__": {}}`. Adequate for trusted single-user local deployment. Not suitable for multi-tenant.
4. **No streaming**: LLM responses appear all at once. Streamlit supports `st.write_stream`; not yet implemented.
5. **No session persistence**: chat history lives in `st.session_state` only. Reloading page resets everything.
6. **Two LLM calls per query**: retrieval filter + analysis. Could be collapsed into one with structured output.
7. **Token in git remote URL**: `https://AxiomaBot:<TOKEN>@github.com/AxiomaBot/pe-findings-analyzer.git` — not in keychain. Must be re-embedded on new clone.
8. **Actual CSV schema unknown**: app built against synthetic 7-column schema. Real data may have 20+ columns with different naming conventions.

## Constraints
- Single-user local deployment (Streamlit localhost)
- Data confidentiality: findings contain sensitive operational data, must not leave corporate network
- LLM must be configurable to point at internal endpoints (Azure OpenAI, on-prem, etc.)
- No embeddings/vector DB — intentional, to avoid dependency on external embedding services
- No auth layer — assumed to run on trusted local machine or internal network

## Repo
https://github.com/AxiomaBot/pe-findings-analyzer
Branch: main
Committed by: Axioma (axioma@local)
