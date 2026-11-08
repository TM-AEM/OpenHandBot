# Notification System (OHB2-08) — Architecture, Data, Reliability, API, Frontend, Ops

Status: reference documentation for the notification subsystem as implemented through
the OHB2 release branch (`release/ohb2-20261101`, superseding the earlier `7b6ec25`
main baseline). It covers OHB2-08-01 through OHB2-08-08 including the R5-01
pagination-retry correction.

Scope note: this document is descriptive. It records what the code does today.
Items marked **[recommendation]** are operational advice, not guarantees the code
provides. Where the implementation has a known limitation, it is stated explicitly
and is never upgraded to a stronger guarantee than the code supports.

Related docs:
- `docs/MINI_APP.md` §13b — Mini App inbox surface (Arabic, UI-facing).
- `docs/OPERATIONS_RUNBOOK.md` — general bot operations and DB inspection commands.
- `README.md` §الإشعارات — user-facing summary of the two notification types.

---

## 1. Overview

OpenHandBot has two independent producers of user notifications:

- **Watcher** (`bot/watcher.py`) — owns notifications for conversations the owner
  explicitly *watches* (`terminal`, `timeout`, `missing`, `stale_report`).
- **Notifier** (`bot/notifier.py`) — the general/proactive producer for *all other*
  conversations (`proactive`), plus recovery of terminal-transition events.

Both run in the same process, share **one** `Database` connection, and persist into
the same SQLite file. There is no second database owner and no separate worker
process.

Notifications are persisted into a durable **inbox** (`notification_inbox`) using an
**event-first / write-ahead** model: the event row is written *before* any Telegram
send attempt, so a failed send or a process crash does not lose the event. Telegram
delivery is tracked separately on the same row via `delivery_status`.

**Delivery is at-least-once with bounded retries, not exactly-once.** See §4.5.

---

## 2. Architecture

### 2.1 Components

```
                 ┌──────────────────────────── Telegram Bot API ───────────────────────────┐
                 │                     (sendMessage via bot/sender.send_long)              │
                 └───────▲───────────────────────────────▲─────────────────────────────┘
                         │ send_long                     │ send_long
        ┌────────────────┴───────────┐      ┌────────────┴─────────────────┐
        │ Watcher (bot/watcher.py)   │      │ Notifier (bot/notifier.py)   │
        │ interval = WATCHER_INTERVAL│      │ interval = WATCHER_INTERVAL  │
        │ kinds: terminal/timeout/   │      │ kinds: proactive/terminal    │
        │        missing/stale_report│      │ (recovery)                   │
        └───────┬──────────▲─────────┘      └───────────┬──────────▲───────┘
                │ writes   │ reads                      │ writes   │ reads
                ▼          │                            ▼          │
        ┌───────────────────┴────────────────────────────────────────────┐
        │            Shared SQLite Database (bot/db.py, single owner)      │
        │  watched · notification_state · notifier_pending ·               │
        │  notifier_retry_not_before · notification_inbox · settings       │
        └───────────────────────────────▲─────────────────────────────────┘
                                        │ reads / narrow writes
        ┌───────────────────────────────┴─────────────────────────────────┐
        │  Mini App backend (bot/web/app.py + services.py), ASGI           │
        │  same process, reads DB directly; never starts a worker          │
        └───────────────────────────────▲─────────────────────────────────┘
                                        │ HTTP (session cookie)
        ┌───────────────────────────────┴─────────────────────────────────┐
        │  Frontend (bot/web/static/app.js + inbox.js) — Telegram WebApp   │
        └──────────────────────────────────────────────────────────────────┘
```

### 2.2 Notification event lifecycle

```
 status transition detected (watcher active watch, or notifier poll)
        │
        ▼
 note_transition(...)  ──► assigns durable transition_seq (identity "epoch")
        │                  (bot/db.py; shared by watcher and notifier)
        ▼
 event-first write: add_inbox_event(...)  delivery_status='pending'
        │            (BEFORE any Telegram send)
        ▼
 send_long(dest, message, bot)
        │
        ├─ success ─► mark_inbox_delivered(id)      delivery_status='delivered'
        │              (+ durable pending marker, then atomic reconcile — §4)
        ├─ RetryAfter ─► set_inbox_retry_deadline(id, deadline)  (no attempt consumed)
        ├─ TelegramError ─► record_inbox_attempt(id, error=...)
        │                    delivery_attempts++  ; mark_failed when budget exhausted
        └─ crash/unexpected ─► claim released; event stays 'pending' for recovery
        │
        ▼
 read path (Mini App): GET /notifications  (read_at independent of delivery_status)
```

Key property: the inbox row survives independent of Telegram. If delivery never
succeeds, the event remains visible in the inbox (`pending` or, after the attempt
budget is exhausted, `failed`) — it is never silently dropped.

### 2.3 Watcher vs Notifier responsibilities

| Concern | Watcher | Notifier |
| --- | --- | --- |
| Watched conversations (`terminal`/`timeout`/`missing`/`stale_report`) | **owns** delivery | records snapshot only; **does not send** for watched conversations |
| All other conversations (`proactive`) | — | **owns** delivery |
| Terminal-transition recovery | recovers its own watch kinds | recovers `proactive` + stuck watched terminal events (§4.3) |
| Ownership marker | `watched` row present | `is_watched(cid)` is False |

The Notifier deliberately skips conversations currently watched
(`if not enabled or self._db.is_watched(cid): return`) to prevent duplicate delivery.
For those, it still records the observed status as "accounted for" so that a later
unwatch or re-enable does not release a stale notification.

`record_notification_sent(...)` is the single explicit coordination point: whoever
successfully delivers a transition records it, so the other producer will not send
the same transition again.

### 2.4 Shared database ownership

- One `Database` instance is created once and passed to the Watcher, the Notifier,
  and the Mini App service. See `bot/app.py` (`_post_init`) wiring.
- The Mini App (`bot/web/services.py`) never opens its own connection and never
  starts a worker; it wakes the existing worker via `application.bot_data` when
  needed (`_wake`).
- All concurrency-sensitive writes use `BEGIN IMMEDIATE` transactions (claim lease,
  `note_transition`, reconcile) so the single shared connection plus separate
  connections (Mini App) cannot interleave a read-modify-write.

### 2.5 Inbox persistence and delivery state

- Rows are inserted with `delivery_status='pending'` by `add_inbox_event` (the
  event-first path used by both producers).
- `add_inbox_item` is a backward-compatible helper that inserts
  `delivery_status='delivered'` directly (legacy callers).
- `read_at` (read/unread) is **independent** of `delivery_status`. A user can read
  an inbox item before Telegram delivery completes, or after a delivery failure.

### 2.6 Telegram delivery integration

- All sends go through `bot/sender.send_long(dest, text, bot)`.
- Destination resolution: the row's stored `chat_id` if present and allowed,
  otherwise the default owner chat. `allowed_chats` (from
  `config.allowed_telegram_ids`) restricts destinations; a disallowed stored chat
  falls back to the default owner chat.
- `RetryAfter` (HTTP 429) is treated as a **scheduling** signal, not a failure
  (§4.2). `TelegramError` is treated as a delivery failure that consumes the attempt
  budget.

### 2.7 Frontend notification lifecycle

- The Mini App fetches `GET /notifications?page=N` for the inbox tab.
- Items are rendered with an unread style, a kind label, and a delivery pill
  (`بيتسلّم…` for `pending`, `فشل التسليم` for `failed`; `delivered` shows no pill).
- A filter bar switches between **all** / **unread** (`unread=1`) / **archived**
  (`archived=1`); switching resets to page 0. Filtering never changes read state — only
  the explicit read action (`…/read`) or read-all does. If the filter changes while a
  list request is in flight, the stale result (success **or** failure) is discarded and
  the list reloads for the current filter (no cross-filter race).
- Each row has an **archive/unarchive** button (reversible). Rows the server marks
  `deletable` also get a two-step **delete** action (explicit confirmation before any
  request; the server re-checks eligibility and can still answer `409`).
- Clicking an unread item POSTs `…/read` and opens the conversation detail.
- A tab badge shows `unread_count` from `bootstrap` and from each list response.
- A visibility-aware poll refreshes the list while the tab is visible (§6.3).

---

## 3. Database

All notification tables are created by `Database._init_schema` and extended by
`Database._migrate` in `bot/db.py`. Migrations are additive (`ALTER TABLE ADD COLUMN`
and `CREATE ... IF NOT EXISTS`); no destructive column change is performed.

### 3.1 Tables and columns

**`notification_state`** — per-conversation notification snapshot (both producers).

| Column | Meaning |
| --- | --- |
| `conversation_id` | PK |
| `status` | last observed status |
| `notified_status` | last status actually delivered/accounted for |
| `retry_count` | consecutive failed notify attempts (bounded by `MAX_NOTIFY_RETRIES`) |
| `updated_at` | ISO timestamp |
| `transition_seq` | durable **transition epoch** (see §3.3) |
| `discovered_status` | terminal status the current epoch belongs to |

**`notifier_pending`** — durable write-ahead delivery marker for the Notifier.

| Column | Meaning |
| --- | --- |
| `conversation_id` | PK |
| `state` | the state that was actually sent (accepted by Telegram) |
| `updated_at` | ISO timestamp |
| `event_id` | linked `notification_inbox.id` |
| `transition_seq` | linked transition epoch |

**`notifier_retry_not_before`** — durable per-conversation RetryAfter deadline.

| Column | Meaning |
| --- | --- |
| `conversation_id` | PK |
| `not_before` | UTC ISO deadline; the conversation is skipped until this passes |

**`notification_inbox`** — durable event log (the user-visible inbox).

| Column | Meaning |
| --- | --- |
| `id` | PK, monotonic (stable ordering: `ORDER BY id DESC`) |
| `conversation_id` | source conversation |
| `title`, `kind`, `message` | display fields (`kind` ∈ §3.4) |
| `created_at` | ISO timestamp |
| `read_at` | NULL = unread; set when read |
| `event_key` | logical event identity (idempotency), see §3.3 |
| `delivery_status` | `pending` / `delivered` / `failed` |
| `delivery_attempts` | failed-attempt counter |
| `last_attempt_at`, `delivered_at`, `last_error`, `next_retry_at` | delivery bookkeeping |
| `chat_id` | delivery destination captured at creation |
| `transition_status` | observed status at creation (**descriptive** only) |
| `transition_seq` | transition epoch (**identity**), see §3.3 |
| `claim_token`, `claim_at` | atomic claim lease for an in-flight delivery (§4.4) |
| `archived_at` | NULL = active inbox; set = archived (reversible, §3.7) |

**`watched`** (pre-existing) carries `pending_delivery_state`, `watch_seq`,
`retry_count` used by the Watcher's write-ahead marker and lifecycle identity.

**`settings`** (pre-existing) stores `notifications_enabled` (default enabled).

### 3.2 Indexes and uniqueness constraints

Created in `_migrate` (idempotent; created **after** the columns are guaranteed to
exist so older databases upgrade cleanly):

- `idx_inbox_unread` on `notification_inbox(read_at)`.
- `idx_inbox_conversation` on `notification_inbox(conversation_id, id)`.
- `idx_inbox_event_key` **UNIQUE partial** on `(event_key) WHERE event_key IS NOT NULL`
  — prevents recording the same logical event twice (retry/restart/reconcile).
- `idx_inbox_transition_seq_unique` **UNIQUE partial** on
  `(conversation_id, transition_seq) WHERE transition_seq IS NOT NULL AND
  delivery_status='pending'` — prevents the two producers from creating competing
  **pending** rows for the *same* transition epoch. `failed` rows are excluded, so a
  later genuine transition of the same status is not blocked.
- `idx_inbox_delivery_pending` **partial** on `(delivery_status, id)
  WHERE delivery_status='pending'` — cheap pending-recovery scan.

`archived_at` has no dedicated index: the active inbox lists `archived_at IS NULL`
rows ordered by the monotonic PK (`id DESC`), and the archived view is small, so the
PK scan with a residual filter is sufficient (see §3.7).

OHB2-08-04 outbox indexes (unrelated to the inbox but part of the same batch):
`idx_outbox_status_updated (status, updated_at)` and
`idx_outbox_conv_chat_status (conversation_id, chat_id, status)`.

Indexes dropped during migration (index-only, no data touched):
`idx_inbox_transition_unique` (superseded identity), `idx_inbox_created` (redundant
with the PK).

### 3.3 Event identity and transition sequence

Two identities exist and must not be conflated:

- **`event_key`** — the idempotency key of an inbox row.
  - Watcher transition events: `conversation_id | kind | watch_seq | transition_seq`.
  - Watcher non-transition events (timeout/missing/stale_report):
    `conversation_id | kind | watch_seq | last_state`.
  - Notifier proactive events: `conversation_id | proactive | transition_seq`.
- **`transition_seq`** — the durable **epoch** assigned by
  `note_transition(conversation_id, status, terminal, now)`:
  - A *new* terminal transition (different terminal status than the last discovered
    one) increments the counter **once** and then stays fixed across all retries of
    that transition.
  - Re-polling the same transition yields the same number (idempotent).
  - Observing a **non-terminal** status closes the epoch (`discovered_status=NULL`),
    so `finished → running → finished` yields two distinct numbers (two events).
  - Executed inside `BEGIN IMMEDIATE`, so the Watcher and Notifier observe the
    **same** identity for the same transition.

This is why the identity is *not* the status text: two genuine transitions with the
same terminal status must produce two separate events.

### 3.4 States

`kind` ∈ `terminal` (watched conversation finished) · `timeout` (24h watch timeout) ·
`missing` (watched conversation disappeared) · `stale_report` (no fresh report after
the prompt) · `proactive` (general Notifier notification).

`delivery_status` ∈ `pending` (not yet delivered) · `delivered` (Telegram accepted) ·
`failed` (attempt budget exhausted, or explicitly marked).

`read_at`: NULL = unread; set = read (independent of delivery).

### 3.5 Retention rules (`_prune_inbox`, run inside the insert transaction)

- **Protected rows are never pruned**: rows with `delivery_status='pending'` **or**
  `read_at IS NULL` **or** `archived_at IS NOT NULL` are always kept.
- Only **read, non-archived** rows are eligible for pruning, oldest first (`id ASC`).
- Soft caps: `INBOX_MAX_PER_CONVERSATION` = 50 per conversation and
  `INBOX_MAX_TOTAL` = 500 overall. If protected rows alone exceed a cap, the table
  is allowed to exceed it — a protected row is never deleted to satisfy a cap.
- Message text is truncated to `INBOX_MAX_MESSAGE_CHARS` = 1000 at insert.

### 3.6 Unread notification preservation

Because unread rows are protected, a notification the user has not seen is never
deleted by retention, regardless of delivery state. Reading an item (`read_at` set)
makes it eligible for pruning once it is also non-pending.

### 3.7 Archiving and safe deletion (OHB2-PHASE1C)

Archiving is a **separate, reversible axis** (`archived_at`). It changes only
visibility: an archived row is hidden from the active inbox and shown in the archived
view, and it **never** touches `delivery_status`, `read_at`, `claim_*`,
`transition_seq` or any operation record (`outbox`, `notifier_pending`, `watched`).
Unarchiving clears `archived_at` and restores the row to the active inbox with the
same identity, so nothing is lost. The unread badge (`unread_count`) and pagination
count the **active** inbox only (`archived_at IS NULL`), so archiving an unread item
does not keep it in the badge. Archive is **idempotent** (a repeated archive keeps the
original `archived_at`). Archiving is a deliberate user action to keep a notification,
so retention (§3.5) **never prunes archived rows**; after unarchiving, a read row
becomes prunable again like any other read row.

Deleting an inbox row permanently is **eligibility-gated on the server** (never on the
client) and **fail-closed**. `notification_inbox.kind` is the deciding axis: only the
**status/outcome report kinds** that have no linked executable operation are eligible
(`INBOX_DELETABLE_KINDS = {terminal, timeout, missing, stale_report}`). `proactive`
(Notifier live-state notification) and **any unknown/unclassified kind** are protected.
A row is deletable only when **all** of these hold:

- its `kind` is in `INBOX_DELETABLE_KINDS` (unknown kinds are protected — fail-closed),
  **and**
- `delivery_status = 'delivered'` (no pending/failed delivery evidence), **and**
- `read_at IS NOT NULL` (the user has seen it), **and**
- it is not referenced as the reconciliation marker of a durable `notifier_pending`
  row (`notifier_pending.event_id`; that row is a crash-recovery witness), **and**
- its conversation has no durable `notifier_pending` marker, **and**
- its conversation has no **open** outbox prompt (`pending`/`claimed`/`sending`).

Otherwise the delete is refused with `409` and no change is made (no false success).
The eligibility is re-checked **inside** the `BEGIN IMMEDIATE` delete transaction, so a
concurrent change (e.g. a new open outbox prompt for the same conversation) cannot be
raced past. An unread actionable failure therefore stays protected even after the user
opens the inbox; a permanently-deleted row is reported `missing` (404) on repeat.
Deleting an inbox row never deletes the conversation, its outbox records, its watch,
or its tombstones. The client `deletable` flag (§5) mirrors these rules but the server
remains the final authority.

---

## 4. Reliability

### 4.1 Durable pending markers (OHB2-08-01)

The Notifier writes a **durable** write-ahead marker in `notifier_pending` *after*
Telegram accepts the message but *before* the permanent `notification_state` record.
Unlike the old in-memory hint, this survives a process restart. On the next cycle
`_process` reconciles the marker **before any send**, so a restart does not cause a
blind re-send. The Watcher has the equivalent per-row marker
`watched.pending_delivery_state`.

### 4.2 RetryAfter persistence and scheduling (OHB2-08-02)

`RetryAfter` (429) is **not** a failure: it does not consume the attempt budget and
does not mark the conversation accounted for. Instead a durable per-conversation
deadline is written to `notifier_retry_not_before` (UTC ISO). Until the deadline
passes, only that conversation is skipped — a 429 for one conversation does not stall
the rest of the cycle. An expired or malformed deadline is cleared and retried
(fail-safe: retry early rather than lose a notification). `_retry_after_seconds`
accepts both `int` and `timedelta` values.

### 4.3 Worker recovery and reconciliation

At the start of each cycle, both producers run a recovery sweep over **due pending**
inbox rows (`list_due_pending_inbox`, respecting `next_retry_at` and the claim lease):

- Watcher recovers its watch kinds, excluding currently-watched conversations
  (`exclude_watched=True`).
- Notifier recovers `proactive` and `terminal` events, skipping conversations that
  currently hold a `notifier_pending` marker (owned by the normal path) and
  conversations visible in the current poll (`exclude_cids`), except:
  - `_watched_event_stuck` — the **current canonical** terminal event of a **stuck**
    watched conversation (active watch path will not retry because `last_state` is
    already terminal). The Notifier takes it over so it cannot hang forever.
  - Superseded (older-epoch) terminal events of a stuck watch are also taken over when
    they are the highest pending epoch (`find_latest_pending_transition`).
- When the attempt budget is exhausted without a `RetryAfter`
  (`delivery_attempts >= INBOX_DELIVERY_MAX_ATTEMPTS`), the event is marked `failed`
  explicitly (kept visible) rather than left pending forever.

On a successful send the recovery path marks the row `delivered` and, if the event
represents the **current** epoch, records the transition as notified (isolated: a
failure here does not undo the successful delivery).

### 4.4 Cross-worker coordination

- **Atomic claim lease** (`claim_pending_inbox`): `UPDATE ... WHERE id=? AND
  delivery_status='pending' AND (claim_token IS NULL OR claim_at<=cutoff)` in a
  `BEGIN IMMEDIATE` transaction. Decision and write are one statement, so it is safe
  across separate SQLite connections (no check-then-act). Only one worker wins.
- `INBOX_CLAIM_LEASE` = 5 minutes. A stale lease (from a crashed process) is reclaimed
  automatically, so an event cannot remain claimed forever.
- The claim is released by `record_inbox_attempt`, `mark_inbox_delivered`,
  `mark_inbox_failed`, and `set_inbox_retry_deadline`.
- The unified partial unique index on `(conversation_id, transition_seq)` is the
  database-level guard against two producers creating competing pending rows for the
  same transition.

### 4.5 Delivery ambiguity window — at-least-once, not exactly-once

Telegram's `sendMessage` returns **no idempotency key**. There is an irreducible
window between "Telegram accepted the message" and "we durably recorded delivery":

```
   Telegram accepts ────────────────► durable record written
                     ▲
                     │  crash here ⇒ on restart the message may be sent again
                     └── ambiguity window (narrowed by write-ahead markers, not removed)
```

The write-ahead markers (`notifier_pending`, `watched.pending_delivery_state`) and the
atomic reconcile **narrow** this window but cannot eliminate it. The design deliberately
prefers safe recovery and explicit uncertainty over silently losing a notification.

**Do not claim exactly-once Telegram delivery.** The system provides at-least-once
delivery with bounded retries (`MAX_NOTIFY_RETRIES` / `MAX_WATCH_NOTIFY_RETRIES` = 5,
`INBOX_DELIVERY_MAX_ATTEMPTS` = 5) and durable visibility of every discovered event.

---

## 5. API contract

All routes are under `API_PREFIX` (`/api/v1`). Error responses share the shape
`{"error": "<code>", "message": "<arabic text>"}` with an appropriate HTTP status.
Authentication is a session cookie; `state_changing` routes additionally require a
valid `Origin` header.

| Method & path | Auth | Body / query | Success response |
| --- | --- | --- | --- |
| `GET /notifications` | session | `page` (int, default 0), `unread` (`1`/`true`), `archived` (`1`/`true`) | inbox page (below) |
| `POST /notifications/{item_id}/read` | session + Origin | none | `{"ok": true, "unread_count": n}` |
| `POST /notifications/read-all` | session + Origin | none | `{"ok": true, "marked": n, "unread_count": n}` |
| `POST /notifications/{item_id}/archive` | session + Origin | none | `{"ok": true, "archived": true, "unread_count": n}` |
| `POST /notifications/{item_id}/unarchive` | session + Origin | none | `{"ok": true, "archived": false, "unread_count": n}` |
| `DELETE /notifications/{item_id}` | session + Origin | none | `{"ok": true, "deleted": true, "unread_count": n}` |
| `POST /app/notifications` | session + Origin | `{"enabled": bool}` | `{"ok": true, "notifications_enabled": bool}` |

`GET /notifications` response:

```json
{
  "page": 0,
  "has_more": true,
  "unread_count": 3,
  "items": [
    {
      "id": 42,
      "conversation_id": "abc",
      "title": "…",
      "kind": "terminal",
      "message": "…",
      "created_at": "2026-10-13T10:00:00+00:00",
      "read": false,
      "archived": false,
      "deletable": false,
      "delivery_status": "delivered",
      "delivery_attempts": 0,
      "delivered_at": "2026-10-13T10:00:01+00:00"
    }
  ]
}
```

`archived` reflects `archived_at IS NOT NULL`; `deletable` is the server's current
delete-eligibility verdict (§3.7) and is the only signal the UI may use to show the
delete control. The client never derives deletability on its own when the server sends
`deletable`; its fallback (no `deletable` field) mirrors the server allowlist
(`terminal`/`timeout`/`missing`/`stale_report` + delivered + read) and is **fail-closed**
for unknown kinds.

Pagination and error behavior (as implemented):

- Page size is fixed at `INBOX_PAGE_SIZE` = 10; offset = `page * 10`; ordering is
  `id DESC` (stable, since `id` is monotonic).
- `page` is clamped to `>= 0`. If a requested page is empty because it exceeds the
  range, the service falls back to page 0 and reports `page: 0` (mirrors the watches
  list behavior). This is why the frontend must synchronize its page from the server
  response (§6.5).
- `has_more` = `total > offset + len(items)`, where `total` respects `unread_only`
  and `archived`.
- `unread_count` is always the unread-only count of the **active** inbox (archived
  rows excluded).
- Malformed `page` → `400 {"error":"bad_request"}`.
- Missing/invalid session → `401`; disallowed user → `403`; missing/foreign Origin on
  a state-changing route → `403 {"error":"bad_origin"}`.
- Reading a non-existent item → `404 {"error": "الإشعار مش موجود."}`; invalid id →
  `400`. Archive/unarchive of a missing item → `404`; invalid id → `400`.
- Deleting a missing item → `404`; invalid id → `400`; a **protected** item (unknown
  or `proactive` kind, pending, failed, unread, a reconciliation reference, a
  conversation with a durable `notifier_pending` marker, or a conversation with an
  open outbox prompt) → `409 {"error":"الإشعار ده محمي من
  الحذف النهائي."}` with no change.
- If the database is unavailable, `GET /notifications` returns an empty page
  (`page 0, has_more false, items []`) rather than failing; read/read-all/archive/
  unarchive/delete return `503`.
- The inbox DTO does **not** expose `event_key`, `claim_token`, or `transition_seq`
  (internal fields).

`bootstrap` (`GET /app/bootstrap`) includes `inbox.unread_count` for the tab badge and
`settings.notifications_enabled`.

---

## 6. Frontend behavior

Two files, both loaded with `defer` and versioned (`?v=5`):
`bot/web/static/inbox.js` (pure, DOM-free helpers) and `bot/web/static/app.js`
(DOM wiring). Tests run the real files under `tests/frontend/dom_stub.js`.

### 6.1 Deduplication

`state.inboxIds` tracks rendered ids. Offset pagination can overlap when new items
shift the window; a repeated id is skipped so the same notification is never rendered
twice. The map is reset when page 0 is loaded.

### 6.2 In-flight request guard

`state.inboxLoading` is set **synchronously** before the request and cleared in both
the success and failure paths. Every `loadInbox` caller (tab open, refresh button,
"المزيد", poll, visibility refresh) goes through this guard, so there is never more
than one notifications request in flight — repeated clicks and a visibility refresh
cannot create overlapping requests.

### 6.3 Visibility-aware refresh and throttling (OHB2-08-07)

- `refreshInterval(visible)` returns `REFRESH_VISIBLE_MS` = 30000 when visible, and
  `0` when hidden. A hidden page runs **no** poll (saves network/battery).
- `setInboxPolling(visible)` clears any existing interval and starts a new one when
  visible, so repeated visibility changes never create duplicate timers.
- On becoming visible, `refreshInboxIfVisible()` triggers an immediate refresh, but
  only if the inbox tab is actually open and the throttle allows it.
- `shouldThrottleRefresh(last, now, minGap)` returns true when
  `now - last < minGap` (`MIN_REFRESH_GAP_MS` = 5000). Missing/invalid/`<= 0` last
  timestamps allow the refresh; a non-finite or negative gap falls back to 5000.
  Clock skew that makes `now - last` negative therefore allows (never locks out).
- If the Page Visibility API is unavailable, the code fails open: it treats the page
  as visible (no crash). With no `visibilitychange` events it simply keeps polling.

### 6.4 Silent refresh failure behavior

Background refreshes call `loadInbox(page, silent=true)`. In silent mode:
- no loading row is shown and the existing list is not cleared;
- an HTTP failure or a network rejection is ignored (the current list is preserved);
- the unread badge/list are only updated from a successful response.

### 6.5 Pagination and server-returned page synchronization (OHB2-08-08)

- "المزيد" requests `nextPage(state.inboxPage, true)` and is blocked when
  `state.inboxHasMore` is false or a request is in flight.
- The success path sets `state.inboxPage = data.page` (only when it is a valid
  `number >= 0`) and `state.inboxHasMore = !!data.has_more`.
- If the server falls back to page 0 (out-of-range request), the client adopts the
  returned page, so it will not request a non-existent page and cannot loop.

### 6.6 R5-01 last-successfully-loaded-page invariant

> **Invariant:** `state.inboxPage` is the **last successfully loaded page**, and it is
> written **only** on the `loadInbox` success path, from the server-returned
> `data.page`.

Consequences (all verified against the source):
- "المزيد" never advances `inboxPage` itself; it only computes the next target. So a
  failed page request (HTTP error or network rejection) leaves the baseline
  unchanged and the next click re-requests the **same** page instead of skipping it.
- Page-zero entry points (tab open, refresh button, `markAllRead`) no longer
  pre-assign `inboxPage = 0`; the baseline becomes 0 only when a page-0 load
  succeeds.
- `state.inboxHasMore` and `state.inboxPage` are written only on success, so a failed
  request cannot corrupt them.

### 6.7 Failed HTTP/network request retry behavior

- **Failed "المزيد" (page N > 0)**: rows and ids are preserved, `inboxHasMore`
  stays, and the next click retries page N.
- **Failed page-0 refresh / tab open**: existing rows and the previous baseline are
  preserved; the next pagination request is computed from the last successful page.
- **Failed silent refresh**: ignored entirely (no flash, no clear).

---

## 7. Operations and troubleshooting

All checks below are **read-only** unless stated. Use the DB path from your config
(`DB_PATH`). Commands use the `sqlite3` CLI; substitute the real path.

### 7.1 Diagnose pending notifications

```sql
-- Pending inbox events (undelivered), oldest first
SELECT id, conversation_id, kind, delivery_status, delivery_attempts,
       next_retry_at, last_error, claim_token, claim_at
FROM notification_inbox
WHERE delivery_status = 'pending'
ORDER BY id ASC;

-- Failed deliveries (attempt budget exhausted)
SELECT id, conversation_id, kind, delivery_attempts, last_error
FROM notification_inbox WHERE delivery_status = 'failed' ORDER BY id DESC;

-- Unread count (what the badge shows)
SELECT COUNT(*) FROM notification_inbox WHERE read_at IS NULL;
```

Interpretation:
- `pending` with `next_retry_at` in the future ⇒ scheduled retry (often a
  `RetryAfter`); expected, not an error.
- `pending` with `claim_token` set and recent `claim_at` ⇒ a delivery is in flight.
- `pending` with a stale `claim_at` (> 5 min) ⇒ a crashed attempt; the lease is
  reclaimable and the next recovery sweep will pick it up.
- `pending` with `delivery_attempts >= 5` and no `next_retry_at` ⇒ about to be marked
  `failed` by the recovery sweep.

### 7.2 RetryAfter behavior

```sql
SELECT conversation_id, not_before FROM notifier_retry_not_before ORDER BY not_before;
```

A conversation listed here is skipped until `not_before` passes. This is normal 429
handling; no action needed. A stale/expired row is cleared automatically on the next
cycle. **[recommendation]** If many rows persist far in the future, check the bot's
Telegram rate limits and whether more than one bot instance is sending.

### 7.3 Failed inbox events

`delivery_status='failed'` means the event was discovered and stored, and delivery
was attempted `INBOX_DELIVERY_MAX_ATTEMPTS` (5) times without success. The event
remains visible in the inbox so the user still sees it. There is **no automatic
re-send** after `failed`; recovery only re-attempts `pending` rows.

### 7.4 Unwatch reconciliation

- `reconcile_pending_delivery` / `remove_watched` / `remove_watched_completing` /
  `remove_watched_if_seq` complete any pending delivery **atomically** with the
  deletion (single `BEGIN IMMEDIATE`), so an unwatch cannot silently drop a delivery
  that Telegram already accepted.
- The Watcher's `on_unwatch` hook (installed on the DB at construction) pins the
  in-memory hint into the durable `watched.pending_delivery_state` before deletion,
  so the Mini App fallback (`db.remove_watched` when the Watcher is unavailable) also
  finds the marker.
- `remove_watched_if_seq` is a compare-and-swap on `watch_seq`: a stale snapshot's
  delete is a no-op if a new watch lifecycle started, so a new watch is never removed
  by an old cycle.
- A new watch lifecycle (`add_watched(new_lifecycle=True)`) reconciles any pending
  marker first, so it does not re-send a notification already delivered in the
  previous lifecycle.

### 7.5 Common API / frontend errors

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| `401 unauthenticated` | missing/expired session cookie | re-auth via Telegram WebApp initData |
| `403 forbidden` | user not in `allowed_telegram_ids` | `config.allowed_telegram_ids` |
| `403 bad_origin` | state-changing call without a valid Origin | reverse-proxy / host configuration |
| `400 bad_request` | malformed `page` or invalid item id | request payload |
| `404` on read | item id does not exist | inbox retention may have pruned it (only if read) |
| Empty inbox but notifications expected | DB unavailable (empty page returned) | DB path/permissions |
| List shows a delivery pill `بيتسلّم…` | event still `pending` | §7.1 |

### 7.6 Relevant logs and safe operational checks

Log messages are emitted by the `bot.watcher` and `bot.notifier` loggers (Arabic
text, exception **type names only** — never exception text, to avoid leaking
secrets). Useful greps:

- `"خطأ في دورة المراقب"` / `"خطأ في دورة المُبلّغ"` — a cycle raised; check traceback.
- `"تعذّر جلب أحداث الصندوق المعلّقة"` — recovery query failed.
- `"تليجرام طلب انتظار ... (429)"` — RetryAfter scheduling.
- `"فشل إشعار المحادثة ... المحاولة n/5"` — delivery failure counting toward budget.
- `"استسلمنا من إشعار المحادثة ..."` — budget exhausted.
- `"تعذّر تسجيل علامة تسليم إشعار ..."` — the write-ahead marker failed; possible
  re-send after restart (ambiguity window).

Safe (read-only) checks: `PRAGMA quick_check;` / `PRAGMA integrity_check;` (see
`Database.quick_check` / `integrity_check`), and `SELECT COUNT(*)` queries above.
Startup runs `run_startup_maintenance` (quick_check + optimize + checkpoint), which
is safe and non-destructive.

**[recommendation]** Do not manually `UPDATE`/`DELETE` inbox rows to "fix" delivery
state unless you fully understand the invariants (especially the partial unique index
and the claim lease); manual edits can create states the recovery sweep does not
expect.

---

## 8. Verification

Documentation checks and the regression gate (run from the repository root):

```bash
# Frontend (Node built-in test runner; no npm/deps)
node --test tests/frontend/*.test.js

# Python unit/integration tests
pytest -q

# Lint (imports/undefined names)
pyflakes bot/ main.py tests/

# Whitespace/conflict check
git diff --check
```

Coverage snapshot at the earlier `7b6ec25` baseline (historical; superseded by the
release branch `release/ohb2-20261101`). Current release-branch gate: pytest
**1222 pass**, frontend **122 pass / 0 fail**, pyflakes clean, `git diff --check`
clean (verified 2026-11-02):

| Suite | Count | Notes |
| --- | --- | --- |
| `tests/frontend/inbox.test.js` | 18 | pure `inbox.js` helpers |
| `tests/frontend/inbox_watch.test.js` | 55 | A–E lifecycle + F (pagination) + G (visibility) + H (R5-01 retry) |
| `tests/frontend/ops.test.js` | 12 | operation-id lifecycle (shared) |
| **frontend total** | **85 pass / 0 fail** | deterministic |
| **pytest total** | **884 pass** | includes notification/inbox suites below |

Notification-relevant Python suites:
`tests/test_notifier.py`, `tests/test_watcher.py`, `tests/test_u01_watcher.py`,
`tests/test_miniapp_inbox.py`, `tests/test_miniapp_inbox_manage.py`,
`tests/test_miniapp_api.py`,
`tests/test_miniapp_features.py`, `tests/test_notifications_controls.py`,
`tests/test_notifications_pref.py`, `tests/test_batch3r_fix.py`,
`tests/test_batch3r_fix2.py`, `tests/test_batch3r_fix2_f1.py`,
`tests/test_batch3r_fix2_n1n2.py`, `tests/test_batch3r_retention.py`,
plus inbox/index coverage in `tests/test_db.py`.

Frontend test sections in `inbox_watch.test.js`:
- A1–A5b initial load; B1–B6 pagination basics; C1–C7 read/read-all; D1–D10
  watch/unwatch; E1–E6 refresh/toast; F1–F4 server-page sync;
  G1–G6 visibility/silent refresh; H1–H10 R5-01 retry-after-failure.

OHB2-PHASE1C suites: `tests/test_miniapp_inbox_manage.py` (45 tests: unread filter,
archive/unarchive isolation, safe-delete eligibility including unknown/`proactive` kind,
open-outbox and `notifier_pending` protection, session/expiry/rate-limit/origin guards,
no false success) and `tests/frontend/inbox_manage.test.js` (F1–F10 filter + filter race,
A1–A4 archive, D1–D8 delete + conservative `canDelete` fallback).

The H1–H3 tests are non-vacuous: reverting the R5-01 `inbox-next` handler makes them
fail (verified by a `/tmp`-only mutation; no repository file was modified).

---

## 9. Limitations and unresolved edge cases

- **No exactly-once Telegram delivery.** The ambiguity window in §4.5 is irreducible
  without a Telegram idempotency key. Expect possible duplicate sends after a crash
  inside the window; this is a deliberate trade-off favoring safe recovery.
- **Single-process assumption.** Coordination relies on one shared process/DB. There
  is no cross-process protection beyond SQLite transactions; running multiple bot
  instances against the same DB is not a supported configuration.
- **`failed` events are not auto-resent.** After the attempt budget is exhausted the
  event stays visible but is not retried automatically.
- **Offset pagination** can overlap when new items arrive between page fetches; the
  frontend deduplicates by id, but a page boundary can still shift. A cursor-based
  scheme would remove the overlap entirely (not implemented).
- **Deletion is eligibility-gated**, not a general "empty the inbox": unknown or
  `proactive` kinds, pending, failed, unread, reconciliation-referenced rows, and rows
  whose conversation has a durable `notifier_pending` marker or an open outbox prompt
  cannot be deleted (they are refused with `409`). Automatic retention still prunes
  read, non-archived, non-pending rows at the caps
  (§3.5); there is no cleanup worker (pruning happens inside the insert transaction).
- **Archived rows are hidden from the active inbox and the unread badge.** The archived
  view is a single flat list (no per-conversation grouping, no bulk unarchive). Archived
  rows are exempt from retention pruning (archiving is a deliberate keep action).
- **Notifier recovery heuristics** (`_watched_event_stuck`, superseded-epoch takeover)
  are subtle; changes there require care to avoid duplicate or lost deliveries.
