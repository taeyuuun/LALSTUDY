# LALSTUDY v0.4.0-beta — OpenAI-only migration

## 1. Overwrite the project code

Extract this ZIP and copy its contents over:

`C:\immune_methods_mvp\LALSTUDY_v0.1.0-beta`

The ZIP does not contain your real `.streamlit/secrets.toml`, `figure_cache/`, research DB, or local JSON corpus files.

## 2. Install/update dependencies

```powershell
cd C:\immune_methods_mvp\LALSTUDY_v0.1.0-beta
python -m pip install -U -r requirements.txt
```

Optional local cleanup of the no-longer-used Gemini SDK:

```powershell
python -m pip uninstall -y google-genai
```

## 3. Secrets

Keep/add:

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_ADMIN_KEY = "sk-admin-..."  # optional; required for official usage/cost sync
OPENAI_COMPLIMENTARY_DAILY_TOKENS = "2500000"

MINERU_TOKEN = "..."
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_..."
```

`GEMINI_API_KEY` is no longer used and can be deleted from local and Streamlit Cloud secrets.

## 4. Local test

```powershell
python -m streamlit run app.py --server.address=127.0.0.1
```

Open `http://127.0.0.1:8501`.

Expected sidebar:

```text
🤖 OpenAI Usage
🟢 OpenAI READY
Free used / Free left / Requests
Official billed cost today

🧠 Knowledge Archive
```

Learn a Paper test:

```text
PDF upload
→ Analyze paper
→ Core Analysis + Figure crop/legend
→ each Figure: Analyze this Figure
→ optional Plus Analysis
```

## 5. GitHub / Streamlit Cloud

```powershell
git add .
git commit -m "Migrate LALSTUDY to OpenAI-only AI engine"
git push
```

Then update Streamlit Cloud Secrets to include `OPENAI_API_KEY` and, for official usage sync, `OPENAI_ADMIN_KEY`.
