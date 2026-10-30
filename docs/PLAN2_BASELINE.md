# PLAN2 Baseline — OpenHandBot 2 (OHB2-00)

Phase 0 is read-only: **no production code was changed** to produce this document.

## 1. Repository state (verified, not assumed)

| Item | Value |
|---|---|
| Repository | `TM-AEM/OpenHandBot` |
| Default branch | `main` |
| HEAD SHA at Phase 0 | `feed851c87ea339887fb102590c8e5bdc021c590` |
| `origin/main` | `feed851c87ea339887fb102590c8e5bdc021c590` (in sync) |
| Plan commit | `feed851` "Add files via upload" adds `docs/plan-openhandBot-2.md` (485 lines) |
| Working tree | clean (no staged/unstaged/untracked) |
| Local Python | 3.13.15 (`/usr/local/bin/python3.13`); `uv` available for 3.11 |

## 2. Test baseline (recorded, actually executed)

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | **583 passed**, exit 0 |
| `.venv/bin/python -m pyflakes bot/ main.py tests/` | clean, exit 0 |
| `git diff --check` | clean, exit 0 |
| CI (`.github/workflows`) | matrix Python 3.11 + 3.13; last run on `063e9a6` = success |

## 3. Registered slash commands (from `bot/app.py`, actual source)

`CommandHandler` registrations: `/start`, `/cancel`, `/notifications`, `/outbox`,
`/outbox_status`, `/outbox_discard`, `/outbox_mark_sent` (7 commands).

- **No `set_my_commands` call exists** anywhere in `bot/` — so Telegram's command menu
  is currently empty. Adding handlers does not populate the menu (plan §2 confirms this).
- **No menu-button call exists** (`set_chat_menu_button` / `MenuButton*` absent).

## 4. Feature matrix (Telegram side, from handler registration + `bot/features.py`)

`DEFERRED_FEATURES_HIDDEN = True`; `HIDDEN_FEATURES = {files, export, cost, followups}`.

| Feature | Handler(s) | Telegram state | Mini App state | Notes |
|---|---|---|---|---|
| Start / main menu | `start`, `show_menu` | visible | planned | add Mini App button here |
| Conversations list | `list_conversations` | visible | planned | `^list:` |
| Open conversation | `open_conversation` | visible | planned | `^open:` |
| Reply / prompt | `reply_prompt`, `_send_prompt`, `handle_text` | visible | planned | durable via outbox |
| New chat / repos | `start_new_chat`, `repos_page`, `pick_repo` | visible | planned | `^newchat`, `^repos:`, `^pickrepo:` |
| Notifications pref | `notifications_command/menu/toggle` | visible | planned | decision A preserved |
| Status | `show_status` | visible | planned | `^status:` |
| Copy / full reply | `copy_reply`, `full_reply` | visible | planned | `^copy:`, `^full:` |
| Outbox ops | `outbox_list/status/discard/mark_sent` | visible | planned | `confirm` required on writes |
| **Followups** | `list_watches`, `watch_conversation`, `unwatch_conversation` | **hidden** | planned | `is_hidden("followups")` |
| **Cost** | `show_cost` | **hidden** | planned | `is_hidden("cost")` |
| **Export** | `export_conversation` | **hidden** | planned | `is_hidden("export")` |
| **Files** | `list_files`, `show_file` | **hidden** | planned | `is_hidden("files")` |

All four hidden features have complete handler + service code and data; only entry points
are suppressed. Auto-follow after prompt (`bot/watcher.py`) remains active regardless.

## 5. Services and state owners (single-owner, must not be duplicated)

- `bot/openhands_client.py` — `OpenHandsClient` (httpx.AsyncClient, Bearer auth).
- `bot/db.py` — `Database` (one SQLite file; schema + migrations).
- `bot/outbox.py` — `OutboxWorker`, `CreationWorker`.
- `bot/watcher.py` — `Watcher` (watched conversations; `watch_seq` CAS).
- `bot/notifier.py` — `Notifier` (global proactive notifications).
- `bot/app.py` — `build_application`, `_post_init`, `_post_shutdown`.
- `main.py` — `run_polling(drop_pending_updates=True)` (long polling; no inbound port).

## 6. Hosting feasibility (decision gate — NOT yet resolved)

Current documented host is **Katabump free** (`docs/DEPLOY_KATABUMP.md`):
- 308 MB RAM, 716 MB storage, 25% CPU; **free server renews every 4 days**.
- **Long polling only — "مفيش منفذ وارد مطلوب" (no inbound port required).**
- No public HTTPS ingress is documented for this deployment.

**Conclusion:** the existing host provides **no proven public HTTPS ingress**, which the
Mini App backend (Phase 3/4) requires. Per plan §4.1 and §8, this is a **decision gate**:
choosing a public-HTTPS backend topology (reverse proxy on the same host, a no-card
tunnel, or another host) is an owner decision and must not be silently assumed.

## 7. Unresolved risks / blockers

1. **Public HTTPS ingress** — no proven route yet (see §6). Blocks OHB2-04+ (HTTP API +
   Mini App). This is the primary gate.
2. Mini App cannot share the menu button with the command list; plan keeps commands and
   launches the app via an inline `web_app` button + `/app` (no conflict).
3. Python 3.11 locally requires `uv python install 3.11` (available); CI already covers it.

## 8. Decision record — backend hosting topology

**Status: OPEN.** Not decided. The plan requires proving a public HTTPS URL within the
free/no-card budget before implementing the web backend. Awaiting owner decision.

## 9. Phase 0 exit

- Production code changed: **none**.
- Existing tests/CI baseline recorded: **yes** (§2).
- Proven route to public HTTPS Mini App URL: **no** → documented blocker + gate (§6–§8).
