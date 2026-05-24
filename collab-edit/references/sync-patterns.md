# Sync Patterns for Collaborative Editing

When a human and AI edit the same file, "Race Conditions" occur. Use these patterns to mitigate them.

## 1. The "Fresh Read" Pattern
**When to use:** Whenever the user says "I just fixed that" or "I changed the variable name."
**AI Action:**
- Immediately call `cat <filepath>` or the equivalent read tool.
- Compare the new content with the previous version in context.
- Acknowledge the change: *"I see you've updated the `Auth` logic to use JWT. I will now integrate the rest of my changes into this new version."*

## 2. The "Targeted Edit" Pattern
**When to use:** Modifying specific functions or blocks in a file > 100 lines.
**AI Action:**
- Do not rewrite the whole file.
- Provide a clear diff:
  - `REMOVE: lines 12-15`
  - `ADD: [new code]`
- This allows the user to see exactly what is changing and spot conflicts quickly.

## 3. The "Soft Lock" Pattern
**When to use:** Performing a major refactor of a specific section.
**AI Action:**
- State clearly: *"I'm refactoring the `PaymentGateway` class now. To avoid overwrites, please don't touch that specific class for the next 30 seconds."*

## 4. Conflict Resolution
**When to use:** When the AI writes a file, but the user's latest version has different changes.
**AI Action:**
- Do not simply overwrite.
- Propose a merge: *"I see both of us changed the `handleRequest` method. Your version adds error handling, mine adds logging. I will merge both."*
