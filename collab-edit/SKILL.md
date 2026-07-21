---
name: collab-edit
description: Optimizes the shared editing loop between a human and an AI to prevent race conditions and overwrites. Use this skill when performing complex file edits where both the user and the AI are modifying the same file, ensuring changes are synced and visible to both parties before final commit.
---

# Collaborative File Editing

## Overview
This skill provides a structured workflow for "Human-in-the-loop" file editing. It prevents the common "overwrite" problem where an AI rewrites a file based on an outdated version while the user is making edits in their editor.

## Collaborative Workflow

To maintain synchronization and avoid data loss, follow this sequence for every edit cycle:

### 1. Synchronization (The "Sync" Phase)
Before making any changes, the AI must ensure it has the absolute latest version of the file.
- **Action**: Read the file immediately before proposing an edit.
- **Check**: If the user mentioned they made changes, perform a fresh `cat` or `read` of the file to capture those changes in context.

### 2. Proposing Changes (The "Review" Phase)
Avoid overwriting the entire file for small changes.
- **Action**: Use targeted edits. If the file is large, propose specific line-number changes or use "Search and Replace" blocks.
- **Communication**: Explicitly state: *"I am updating lines X through Y. Please check if this conflicts with your recent edits."*

### 3. Concurrent Edit Guardrails
When both parties are active:
- **Locking**: Suggest a "soft lock." Example: *"I'm about to rewrite the `UserService` class. Please hold off on editing that section for a moment."*
- **Verification**: After writing, ask the user to verify the change in their editor before proceeding to the next step.

### 4. The "Crumbs" Method (For Large Files)
If editing a massive file, use a temporary "diff" or "patch" approach:
- Write the proposed changes to a `.tmp` file or a `diff` output.
- Let the user review the diff.
- Apply the change only after user confirmation.

## Best Practices for the AI
- **Never assume** the version of the file in the conversation history is current.
- **Always prioritize** the version on disk over the version in the prompt.
- **Use atomic writes** via scripts if the environment supports it to prevent partial file corruption.

## Resources

### references/
- `sync-patterns.md`: Detailed examples of how to communicate sync states and handle merge conflicts manually.

