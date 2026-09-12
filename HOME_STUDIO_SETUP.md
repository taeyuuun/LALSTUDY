# LALSTUDY Home Studio

## What it does

The public landing page can now be edited from the browser.

Open:

`https://YOUR-APP.streamlit.app/?home_editor=1`

The Home Studio provides:

- Korean / English copy editing
- Hero title and subtitle
- CTA button labels
- Feature-card icons / titles / descriptions
- Start-flow text
- Open Beta notice
- Show / hide toggles
- Hero font size
- Subtitle font size
- Section title size
- Card title / body font size
- Hero line height
- Left / center hero alignment
- Page width
- Card corner radius
- Card minimum height
- Live preview
- Save & publish to Supabase

## 1. Run SQL once

In Supabase SQL Editor, run:

`SUPABASE_HOME_EDITOR_MIGRATION.sql`

## 2. Add one secret

Local `.streamlit/secrets.toml` and Streamlit Cloud Secrets:

```toml
HOME_ADMIN_PASSWORD = "choose-a-strong-password"
```

Existing secrets stay unchanged:

```toml
SUPABASE_URL = "https://<project-ref>.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_..."
```

## 3. Open the editor

Add this to the app URL:

`?home_editor=1`

Example:

`https://lalstudy.streamlit.app/?home_editor=1`

The editor is not listed in the public sidebar.

## 4. Persistence

`HOME_CONTENT.toml` is the fallback/default configuration.

When the admin presses `저장 & 게시`, Home Studio writes one JSON document to:

`public.home_page_config`

The public home then loads that published config.

A redeploy does not erase the published home configuration.

## 5. Security

- The admin password is stored only in Streamlit Secrets.
- The Supabase secret key stays server-side.
- `anon` and `authenticated` roles receive no direct table access.
- The Home Studio is hidden from normal navigation.
