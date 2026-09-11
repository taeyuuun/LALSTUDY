# LALSTUDY Knowledge Archive — Supabase Setup

This is a one-time setup.

## 1. Create a Supabase project

Create a free project in Supabase.

## 2. Create the Archive tables

Open:

`Supabase Dashboard → SQL Editor → New query`

Paste the entire contents of:

`supabase_schema.sql`

and click **Run**.

You should then see:

- `knowledge_concepts`
- `knowledge_aliases`

in the Table Editor.

## 3. Copy the server credentials

In Supabase:

`Settings → API Keys`

Use the new **Secret key** (`sb_secret_...`) for Streamlit server-side access.

Do **not** use this secret key in browser JavaScript or commit it to GitHub.

You also need the project URL.

## 4. Add Streamlit Cloud Secrets

Open the deployed LALSTUDY app:

`Manage app → Settings → Secrets`

Add:

```toml
GEMINI_API_KEY = "..."
MINERU_TOKEN = "..."

SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_..."
```

Save. Streamlit will restart.

## 5. Verify

Open `Learn a Paper`.

The sidebar should display something like:

`🧠 Knowledge Archive · 0 concepts`

Enter:

```text
zinc homeostasis
p53 conformational change
lysosomal degradation
```

Click:

`Archive 검색 + 필요한 것만 설명`

First run:

- Archive HIT = 0
- Archive MISS = 3
- Gemini generated = 3
- one Gemini batch request
- the three cards are inserted into Supabase

Run the same concepts again (or open the app as another user):

- Archive HIT = 3
- Archive MISS = 0
- Gemini generated = 0
- zero Gemini API calls

## Security

The tables have RLS enabled and no public anon/authenticated policies.

Only LALSTUDY's server-side Supabase secret is intended to access them.
