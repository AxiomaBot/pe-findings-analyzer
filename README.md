# PE Findings Analyzer

A Streamlit app for analysing production efficiency (PE) findings/annotations using an LLM of your choice.

Upload your findings database (CSV), configure any LLM backend, and chat with your data in plain language.

---

## What it does

- Loads a CSV of production findings/annotations
- Auto-detects columns and summarises the dataset
- Lets you ask natural language questions about your data
- Smart retrieval: filters relevant rows before sending to LLM (handles large datasets)
- Fully model-agnostic — works with OpenAI, Anthropic, Azure, local Ollama, or any OpenAI-compatible endpoint

---

## Architecture

```
CSV upload
    ↓
Column detection + data summary
    ↓
User query (chat)
    ↓
[Retriever] — LLM generates pandas filter → subset of relevant rows
    ↓
[Analyser] — LLM answers query using filtered rows as context
    ↓
Response rendered in chat UI
```

10,000 rows can't be stuffed into a context window. The retriever solves this by:
1. Sending the query + column schema to the LLM
2. LLM returns a pandas filter expression (e.g. `asset == 'P-101'`)
3. Filter applied → relevant subset passed to the analysis LLM
4. Falls back to keyword search if filter fails

---

## Setup

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Configure (copy and edit)
cp .env.example .env

# 3. Run
streamlit run app.py
```

---

## Configuration

Set in `.env` or via the sidebar in the app:

| Variable | Description | Example |
|---|---|---|
| `LLM_PROVIDER` | Provider prefix for LiteLLM | `openai`, `anthropic`, `azure`, `ollama` |
| `LLM_MODEL` | Model name | `gpt-4o`, `claude-3-5-sonnet-20241022` |
| `LLM_API_KEY` | API key | `sk-...` |
| `LLM_API_BASE` | Custom base URL (optional) | `http://localhost:11434` for Ollama |

### Provider examples

```env
# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-...

# Anthropic
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
LLM_API_KEY=sk-ant-...

# Azure OpenAI
LLM_PROVIDER=azure
LLM_MODEL=gpt-4o
LLM_API_KEY=...
LLM_API_BASE=https://your-resource.openai.azure.com/

# Ollama (local, no key needed)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
LLM_API_BASE=http://localhost:11434

# Any OpenAI-compatible endpoint
LLM_PROVIDER=openai
LLM_MODEL=your-model
LLM_API_KEY=your-key
LLM_API_BASE=https://your-custom-endpoint.com/v1
```

---

## CSV format

The app is flexible — it detects columns automatically. It works best when your CSV has:

- A **finding/annotation text column** (free-form text describing the observation)
- **Asset identifier** column (e.g. asset name, tag, functional location)
- **Date** column
- Any additional metadata (severity, status, engineer, unit, system, etc.)

On first upload, you'll be asked to map which column is which.

---

## Example questions

- *"Which assets have the most open findings?"*
- *"Summarise all findings for compressor K-201"*
- *"What are the recurring themes across pump findings this year?"*
- *"Which findings were raised last month and are still unresolved?"*
- *"What are the top 5 PE improvement opportunities based on finding frequency?"*

---

## Project status

- [x] Project scaffold + architecture
- [x] CSV loader with column detection
- [x] Model-agnostic LLM client (LiteLLM)
- [x] Smart retriever (filter generation + keyword fallback)
- [x] Streamlit chat UI
- [ ] Column mapping UI (auto-detect with manual override)
- [ ] Export chat to report
- [ ] Multi-file / incremental upload
- [ ] Saved queries / templates
