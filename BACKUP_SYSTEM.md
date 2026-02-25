# Database Backup System

## Overview
Automatic and manual database backups to protect your articles from accidental deletion or data loss.

---

## ✅ Features

### 1. Manual Backup (Console Page)
- **Blue "BACKUP" button** in console header
- Creates instant backup on demand
- Shows confirmation with file path and size
- Perfect for before testing or making changes

### 2. Automatic Daily Backups
- **Runs at 3 AM** every day
- **Immediate backup** when app starts
- **Keeps all backups forever** (no auto-deletion)
- Runs in background, doesn't affect performance

### 3. Manual Backup Retention
- **Keeps all manual backups forever** (no auto-deletion)
- Separate from daily backups

---

## 📁 Backup Locations

```
data/
├── newsixity.db                          # Main database
├── newsixity.db-wal                      # Write-ahead log
├── newsixity.db-shm                      # Shared memory
└── backups/                              # Backup directory
    ├── newsixity-2026-02-12T02-30-00.db # Manual backup
    ├── newsixity-2026-02-12T03-00-00.db # Manual backup
    ├── newsixity-auto-2026-02-12T03-00-00.db  # Daily backup (3 AM)
    ├── newsixity-auto-2026-02-13T03-00-00.db  # Daily backup
    └── ... (up to 7 daily + 10 manual)
```

---

## 🔄 How to Use

### Manual Backup (Recommended Before Testing):

1. Go to **Console** page (sidebar link)
2. Click **"BACKUP"** button in header (blue button)
3. Wait for confirmation popup showing path and size
4. Backup is saved to `data/backups/`

### Restore from Backup:

```bash
# 1. Stop the app
# 2. List available backups
ls -lh data/backups/

# 3. Restore from a backup
cp data/newsixity.db data/newsixity.db.old  # Keep current as backup
cp data/backups/newsixity-2026-02-12T03-00-00.db data/newsixity.db

# 4. Restart the app
```

---

## 🛡️ What's Protected

### Automatic Backups Include:
- ✅ All articles (all categories)
- ✅ Saved articles
- ✅ Manual links
- ✅ Article groups
- ✅ Feed configurations
- ✅ User preferences
- ✅ Settings
- ✅ Research cache
- ✅ Stock watchlist

### Backup Method:
- Uses SQLite `VACUUM INTO` for clean, compact backups
- No corruption or partial data
- Full database snapshot

---

## ⏰ Backup Schedule

| Type | When | Retention | Location Pattern |
|------|------|-----------|------------------|
| **Daily** | 3 AM | Forever | `newsixity-auto-YYYY-MM-DDTHH-MM-SS.db` |
| **Manual** | On-demand | Forever | `newsixity-YYYY-MM-DDTHH-MM-SS.db` |
| **Startup** | App start | Counts as daily | `newsixity-auto-YYYY-MM-DDTHH-MM-SS.db` |

---

## 💡 Best Practices

### Before Making Changes:
1. Click "BACKUP" in console
2. Make your changes/tests
3. If something goes wrong, restore from backup

### Regular Maintenance:
- Daily backups run automatically (no action needed)
- Manual backups before major updates
- Keep important backups elsewhere (USB, cloud)

### Emergency Recovery:
```bash
# If app won't start due to database corruption
cd data/backups
ls -lt  # List backups by date (newest first)
cp newsixity-auto-2026-02-12T03-00-00.db ../newsixity.db
# Restart app
```

---

## 🔧 Technical Details

### Implementation Files:
- `src/app/api/console/backup/route.ts` - Manual backup API
- `src/lib/backup/scheduler.ts` - Automatic backup scheduler
- `src/app/console/page.tsx` - Backup button UI
- `src/app/layout.tsx` - Scheduler initialization

### Backup Process:
```
1. Create backups/ directory if missing
2. Generate timestamped filename
3. Run VACUUM INTO (creates clean copy)
4. Check file size
5. Delete old backups (keep last 7 daily / 10 manual)
6. Log result
```

### Storage Requirements:
- Each backup ≈ 1-5 MB (depends on article count)
- Backups accumulate over time (kept forever)
- Example: ~30 MB per month, ~360 MB per year
- Monitor disk space with `du -sh data/backups/`

---

## 🚨 Recovery Scenarios

### Scenario 1: Accidental Deletion
```bash
# Stop app, restore latest backup
cp data/backups/newsixity-auto-2026-02-12T03-00-00.db data/newsixity.db
# Restart app - articles restored
```

### Scenario 2: Test Gone Wrong
```bash
# Used manual backup before testing
cp data/backups/newsixity-2026-02-12T02-30-00.db data/newsixity.db
# Back to pre-test state
```

### Scenario 3: Database Corruption
```bash
# SQLite error on startup
cp data/backups/newsixity-auto-2026-02-11T03-00-00.db data/newsixity.db
# Use day-old backup
```

---

## 📊 Monitoring Backups

### Check Backup Status:
```bash
# List all backups with size and date
ls -lh data/backups/

# Count backups
ls data/backups/ | wc -l

# Show newest backup
ls -t data/backups/ | head -1

# Check backup size
du -sh data/backups/
```

### Verify Backup Integrity:
```bash
# Test if backup is valid SQLite database
sqlite3 data/backups/newsixity-auto-2026-02-12T03-00-00.db "PRAGMA integrity_check;"
# Should output: ok
```

---

## ✅ Summary

**Manual Backup:**
- Blue "BACKUP" button in console
- On-demand protection
- Keeps all backups forever

**Automatic Backup:**
- Daily at 3 AM + on startup
- Keeps all backups forever
- Zero maintenance

**Recovery:**
- Simple file copy
- Full restore in seconds
- All data preserved

Your articles are now protected! 🛡️
