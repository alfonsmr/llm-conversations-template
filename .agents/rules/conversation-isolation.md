---
trigger: always_on
description: Per-conversation subfolder isolation and on-demand GitHub sync rules for this workspace.
---

# Per-Conversation Subfolder Isolation Rules

This workspace hosts multiple independent conversations on different topics. Every conversation MUST stay isolated within its own subfolder inside `<workspace-root>/conversations/`.

## 1. Subfolder Creation & Naming
- Each conversation has a unique `Conversation ID` (provided in `<user_information>`).
- Maintain a mapping between `Conversation ID` and its subfolder name in `.conversations.json` at the workspace root (format: `{"<conversation-id>": "<subfolder-name>"}`).
- When a conversation begins:
  1. Check `.conversations.json` in the workspace root to see if the current `Conversation ID` already has an assigned subfolder.
  2. If not, use the suggested subfolder name from the `PreInvocation` hook message (if provided), or derive a concise, descriptive `kebab-case` subfolder name that matches the conversation topic/name (e.g., `thessaloniki-trip`, `tax-planning`), create `<workspace-root>/conversations/<subfolder-name>`, and record `<subfolder-name>` in `.conversations.json`.

## 2. Strict Read/Write Isolation
- **Read Scope**: ONLY read, search (`grep_search`, `find_by_name`), or inspect files inside the current conversation's assigned subfolder `<workspace-root>/conversations/<subfolder-name>/` (plus `.conversations.json` at the workspace root for setup). Do NOT read files in the workspace root or in other conversation subfolders unless the user explicitly instructs you to access a specific path outside your subfolder.
- **Write & Command Scope**: Create, edit, and save all files inside `<workspace-root>/conversations/<subfolder-name>/`, and run shell commands with `<workspace-root>/conversations/<subfolder-name>` as the working directory (`Cwd`) whenever possible.
- If the user uploads or drops a new file into the workspace root during the conversation and references it, move it into the current conversation's subfolder (`conversations/<subfolder-name>/`) before working with it.

## 3. Renaming the Subfolder
- When a conversation is renamed in the Antigravity UI sidebar, the `PreInvocation` hook (`.agents/hooks.json`) automatically detects the updated title in `conversation_summaries.db`, renames `<workspace-root>/conversations/<old-name>` to `<workspace-root>/conversations/<new-name>`, updates `.conversations.json`, and notifies you via a `FOLDER_EVENT` ephemeral message on the next turn.
- If the user also asks in chat to rename the folder, rename `<workspace-root>/conversations/<old-name>` to `<workspace-root>/conversations/<new-name>` and update `.conversations.json`.

## 4. Deleting a Subfolder
- Orphaned subfolders from deleted conversations are automatically cleaned up by the `PreInvocation` hook (`.agents/hooks.json`), which checks whether each conversation in `.conversations.json` still exists in the Antigravity brain directory and notifies you via a `FOLDER_EVENT` ephemeral message.
- You may also delete a subfolder directly if the user explicitly asks to remove it.

## 5. Always Announce Folder Create, Rename, and Delete Events in Chat
- Whenever a conversation subfolder is **created**, **renamed**, or **deleted**—whether performed directly by you or reported via `FOLDER_EVENT` from the `PreInvocation` hook—you **MUST** clearly announce it at the very top of your response to the user using a visible status line:
  - **Created**: `📁 **Folder created:** \`conversations/<subfolder-name>/\``
  - **Renamed**: `📁 **Folder renamed:** \`conversations/<old-name>/\` → \`conversations/<new-name>/\``
  - **Deleted**: `🗑️ **Folder deleted:** \`conversations/<subfolder-name>/\` *(conversation deleted)*`

## 6. On-Demand GitHub Sync & Occasional Reminders
- **Never Sync Automatically**: Do NOT commit or push changes to Git/GitHub unless the user explicitly asks you to (e.g., *"sync"*, *"push changes"*, *"commit to GitHub"*).
- **How to Sync When Asked**: When the user asks to sync or push changes, run git commands from `<workspace-root>` to stage all changes (`git add -A`), commit with a concise summary message (`git commit -m "..."`), and push to the remote repository (`git push`).
- **Occasional Sync Suggestion**: Once in a while—only when uncommitted file changes exist and a natural milestone is reached (for example, after creating or significantly updating several files, and at most once every 5–6 turns)—add a brief, low-key one-line note at the end of your response asking if the user would like to sync/push changes to GitHub. Do NOT suggest syncing on consecutive turns or during purely conversational turns with no file edits.
