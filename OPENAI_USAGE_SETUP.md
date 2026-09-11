# OpenAI Official Usage Sync

LALSTUDY uses two separate OpenAI keys:

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_ADMIN_KEY = "sk-admin-..."
OPENAI_COMPLIMENTARY_DAILY_TOKENS = "2500000"
```

- `OPENAI_API_KEY`: normal project API key used for model calls.
- `OPENAI_ADMIN_KEY`: organization Admin API key used only on the Streamlit server to query official Organization Usage and Costs endpoints.
- Never expose or commit either key.

The sidebar refreshes official OpenAI usage at most once per 60 seconds unless the user presses the explicit refresh button.

If the Usage API exposes the `data sharing incentive` service tier, LALSTUDY labels the complimentary-token remaining value as exact. If that tier is not present in the API response, LALSTUDY shows an official eligible-model usage fallback and marks the remaining value as an estimate.

Gemini still uses app-side usage tracking in this version.
