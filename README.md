# Multi-Conversation Antigravity Workspace

**Isolated per-conversation folders inside a single project.**

Use a single project for all your day-to-day LLM conversations without cross-contaminating files or context:
- **1 Conversation = 1 Subfolder**: Every new chat automatically works inside `conversations/<chat-title>/`.
- **Zero Context Bleed**: The agent is scoped strictly to the active conversation's subfolder.
- **UI-Synced Lifecycle**: Rename or delete a chat in the Antigravity sidebar and its subfolder is automatically renamed or moved to `.trash/` on disk.

---

## How It Works

### 1. Per-Conversation Subfolder Isolation
- Each Antigravity conversation has a unique `Conversation ID`.
- When a conversation starts, a `kebab-case` subfolder matching the conversation's topic or UI title is created inside `conversations/` (e.g., `conversations/thessaloniki-trip/`, `conversations/tax-planning/`).
- The mapping between `Conversation ID` and its assigned subfolder name is tracked locally in `.conversations.json` (which is git-ignored).
- **Strict Scope**: Within any given conversation, the agent only reads, searches, edits, and runs commands inside that conversation's assigned `conversations/<subfolder-name>/` directory. The project root stays clean with `README.md` as the only root file.

### 2. Automatic Syncing via `PreInvocation` Hook
A `PreInvocation` hook ([`.agents/hooks.json`](.agents/hooks.json) → [`.agents/scripts/cleanup-conversations.py`](.agents/scripts/cleanup-conversations.py)) runs automatically before each agent turn to keep workspace folders in sync with the Antigravity UI:

- **Creating Subfolders**: For a new conversation, the hook reads the current conversation title from Antigravity's local SQLite database (`conversation_summaries.db`) and suggests a matching `conversations/<kebab-case-name>` folder to the agent.
- **Renaming Subfolders**: If you rename a conversation in the Antigravity sidebar, the hook automatically detects the title change on the next turn, renames `conversations/<old-name>/` → `conversations/<new-name>/` on disk, updates `.conversations.json`, and instructs the agent to announce the rename in chat.
- **Moving Deleted Conversations to Trash**: If you delete a conversation in the Antigravity UI, its directory in `~/.gemini/antigravity/brain/<conversation-id>` is removed. On the next turn of any conversation, the hook detects that the brain directory no longer exists, safely moves the orphaned `conversations/<subfolder-name>/` directory into `.trash/<subfolder-name>/` (git-ignored), cleans up `.conversations.json`, and instructs the agent to announce the move/deletion in chat. Folders in `.trash/` are retained for **30 days** before being permanently purged by the hook.

### 3. Chat Announcements
Whenever a conversation subfolder is created, renamed, or deleted, the agent announces the change at the top of its response:
- 📁 **Folder created:** `conversations/<subfolder-name>/`
- 📁 **Folder renamed:** `conversations/<old-name>/` → `conversations/<new-name>/`
- 🗑️ **Folder deleted:** `conversations/<subfolder-name>/` *(conversation deleted)*

### 4. On-Demand GitHub Sync
- Changes are **never** committed or pushed automatically.
- Whenever you want to back up or publish your workspace changes, simply ask the agent in chat (e.g., *"sync"*, *"push changes"*, or *"commit to GitHub"*).

---

## Using This as a Template

1. Create a new **private** repository on GitHub from this template (or clone it and point `origin` to your own private repository).
2. Open the repository folder in Antigravity and start a conversation—your first topic folder will be created automatically under `conversations/`.
3. *(Optional)* If you are working inside a **public** template repository and want to prevent any test conversations from ever being committed, keep `conversations/` in `.gitignore`. In your **private** conversations repository, remove `conversations/` from `.gitignore` so your conversations are backed up when you ask the agent to sync.

---

## Repository Structure

```text
llm-conversations/
├── .agents/
│   ├── hooks.json                          # Configures the PreInvocation hook
│   ├── rules/
│   │   └── conversation-isolation.md       # Workspace isolation & Git sync rules for the agent
│   └── scripts/
│       └── cleanup-conversations.py        # Syncs folder renames & moves deleted folders to .trash/
├── .conversations.json                     # Local Conversation ID -> subfolder map (git-ignored)
├── .trash/                                 # Deleted conversation folders, auto-purged after 30 days (git-ignored)
├── .gitignore
├── README.md                               # Project documentation (only file in root)
└── conversations/
    └── <conversation-subfolder>/           # Isolated directory per conversation
```
