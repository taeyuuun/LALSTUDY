# Restore old OpenAI sidebar

This patch restores the older OpenAI Usage UI with the green `OpenAI READY`
status box.

Files:
- `openai_sidebar.py` — restored from v0.6.1 Open Beta
- `sidebar_ui.py` — compatibility shim so the current shared sidebar still works

Knowledge Archive remains above OpenAI by default because the current
`sidebar_ui.py` ordering logic is preserved.

No SQL, secrets, or dependency changes are required.
