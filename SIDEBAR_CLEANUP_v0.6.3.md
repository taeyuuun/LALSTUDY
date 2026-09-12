# LALSTUDY v0.6.3 Sidebar Cleanup

Responsibilities are now explicit:

- `ai_provider.py`: OpenAI keys/readiness/app usage state only
- `openai_usage_sync.py`: official usage retrieval only
- `openai_sidebar.py`: the only OpenAI sidebar UI
- `knowledge_widget.py`: Knowledge Archive UI only
- `sidebar_ui.py`: widget visibility/order/expanded state only
- `home_editor.py`: admin settings only

Default sidebar:
1. Language
2. Knowledge Archive
3. OpenAI Usage

OpenAI UI:
- green `OpenAI READY`
- total tokens
- requests + cost
- refresh button
- no sync timestamp
- no usage UI version marker
- no debug/setup text in minimal mode
- no divider around usage content

Knowledge Archive:
- placeholder: `e.g. apoptotic stress`
- helper: `이해가 필요한 용어를 검색해보세요.`

No SQL / secret / dependency changes.
