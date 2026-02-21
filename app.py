"""
PE Findings Analyzer — Streamlit App
Chat with your production efficiency findings/annotations database.
"""

import streamlit as st
import pandas as pd

from src.config import load_config_from_env, config_from_ui
from src.data_loader import load_csv, detect_columns, get_dataset_summary, dataframe_to_text
from src.llm_client import chat, check_connection
from src.retriever import retrieve

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="PE Findings Analyzer",
    page_icon="⚙️",
    layout="wide",
)

# ─── Sidebar: LLM Configuration ──────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Configuration")

    st.subheader("LLM Backend")

    env_config = load_config_from_env()

    provider = st.text_input("Provider", value=env_config.provider,
                             help="openai | anthropic | azure | ollama | etc.")
    model = st.text_input("Model", value=env_config.model,
                          help="e.g. gpt-4o, claude-3-5-sonnet-20241022, llama3.2")
    api_key = st.text_input("API Key", value=env_config.api_key or "",
                            type="password", help="Leave blank for local models")
    api_base = st.text_input("API Base URL (optional)", value=env_config.api_base or "",
                             help="Custom endpoint, e.g. http://localhost:11434 for Ollama")

    llm_config = config_from_ui(provider, model, api_key, api_base)

    if st.button("Test connection"):
        with st.spinner("Testing..."):
            ok, msg = check_connection(llm_config)
        if ok:
            st.success(f"✅ Connected — model replied: {msg}")
        else:
            st.error(f"❌ Failed: {msg}")

    st.divider()

    st.subheader("Dataset")
    uploaded_file = st.file_uploader("Upload findings CSV", type=["csv"])

    if "df" in st.session_state:
        df = st.session_state["df"]
        st.metric("Rows", f"{len(df):,}")
        st.metric("Columns", len(df.columns))


# ─── Main area ────────────────────────────────────────────────────────────────

st.title("⚙️ PE Findings Analyzer")
st.caption("Chat with your production efficiency findings database")

# ─── Load data ───────────────────────────────────────────────────────────────

if uploaded_file is not None:
    if "df" not in st.session_state or st.session_state.get("last_file") != uploaded_file.name:
        with st.spinner("Loading data..."):
            df = load_csv(uploaded_file)
            col_map = detect_columns(df)
            summary = get_dataset_summary(df, col_map)
            st.session_state["df"] = df
            st.session_state["col_map"] = col_map
            st.session_state["summary"] = summary
            st.session_state["last_file"] = uploaded_file.name
            st.session_state["messages"] = []
        st.success(f"Loaded {len(df):,} rows")

# ─── Column mapping (if data loaded) ─────────────────────────────────────────

if "df" in st.session_state:
    df = st.session_state["df"]
    col_map = st.session_state["col_map"]

    with st.expander("Column mapping (auto-detected — click to review/override)", expanded=False):
        cols = ["(none)"] + list(df.columns)
        col1, col2, col3 = st.columns(3)

        with col1:
            finding_col = st.selectbox(
                "Finding/annotation text",
                cols,
                index=cols.index(col_map["finding_col"]) if col_map["finding_col"] in cols else 0,
            )
            asset_col = st.selectbox(
                "Asset identifier",
                cols,
                index=cols.index(col_map["asset_col"]) if col_map["asset_col"] in cols else 0,
            )
        with col2:
            date_col = st.selectbox(
                "Date",
                cols,
                index=cols.index(col_map["date_col"]) if col_map["date_col"] in cols else 0,
            )
            status_col = st.selectbox(
                "Status",
                cols,
                index=cols.index(col_map["status_col"]) if col_map["status_col"] in cols else 0,
            )
        with col3:
            location_col = st.selectbox(
                "Functional location",
                cols,
                index=cols.index(col_map["location_col"]) if col_map["location_col"] in cols else 0,
            )

        # Update col_map from UI selections
        col_map = {
            "finding_col": finding_col if finding_col != "(none)" else None,
            "asset_col": asset_col if asset_col != "(none)" else None,
            "date_col": date_col if date_col != "(none)" else None,
            "status_col": status_col if status_col != "(none)" else None,
            "location_col": location_col if location_col != "(none)" else None,
        }
        st.session_state["col_map"] = col_map
        st.session_state["summary"] = get_dataset_summary(df, col_map)

    # Quick dataset overview
    with st.expander("Dataset overview", expanded=False):
        st.text(st.session_state["summary"])
        st.dataframe(df.head(10), use_container_width=True)

# ─── Chat interface ───────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Render chat history
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("retrieval_info"):
            st.caption(f"🔍 Retrieval: {msg['retrieval_info']}")

# Input
if "df" not in st.session_state:
    st.info("👆 Upload a CSV file in the sidebar to get started.")
else:
    query = st.chat_input("Ask something about your findings...")

    if query:
        # Display user message
        with st.chat_message("user"):
            st.markdown(query)
        st.session_state["messages"].append({"role": "user", "content": query})

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                df = st.session_state["df"]
                col_map = st.session_state["col_map"]
                summary = st.session_state["summary"]

                # Step 1: Retrieve relevant rows
                subset, retrieval_info = retrieve(df, query, col_map, llm_config)
                context_text = dataframe_to_text(subset)

                # Step 2: Build analysis prompt
                system_prompt = f"""You are an expert production efficiency analyst assistant.
You help engineers analyse production findings and annotations to identify improvement opportunities.

The user has uploaded a findings database. Here is a summary of the full dataset:
{summary}

Your job is to answer the user's question based on the relevant findings provided below.
Be specific, cite asset names and findings where relevant. Think like an engineer.
If the data is insufficient to answer, say so clearly and suggest what additional data would help."""

                user_prompt = f"""Question: {query}

Relevant findings (filtered subset of {len(df):,} total rows):
{context_text}"""

                messages = [
                    {"role": "system", "content": system_prompt},
                    # Include recent conversation history for context
                    *[
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state["messages"][:-1]  # Exclude current query (already added)
                        if m["role"] in ("user", "assistant")
                    ][-6:],  # Last 3 exchanges
                    {"role": "user", "content": user_prompt},
                ]

                try:
                    response = chat(messages, llm_config, temperature=0.3, max_tokens=2048)
                except Exception as e:
                    response = f"❌ Error calling LLM: {e}\n\nCheck your configuration in the sidebar."

            st.markdown(response)
            st.caption(f"🔍 Retrieval: {retrieval_info}")

        st.session_state["messages"].append({
            "role": "assistant",
            "content": response,
            "retrieval_info": retrieval_info,
        })

# Clear chat button
if st.session_state.get("messages"):
    if st.button("🗑️ Clear chat", key="clear_chat"):
        st.session_state["messages"] = []
        st.rerun()
