import { getDb } from "@/lib/db";
import fs from "fs";
import path from "path";

const globalForBackup = globalThis as unknown as {
  __newsixityBackupScheduler: NodeJS.Timeout | undefined;
  __newsixityBackupStarted: boolean | undefined;
};

const MAX_BACKUPS = 10;

/**
 * Clean up old backups, keeping only the most recent MAX_BACKUPS
 */
function cleanupOldBackups(backupsDir: string, prefix: string): void {
  try {
    const backups = fs.readdirSync(backupsDir)
      .filter(f => f.startsWith(prefix) && f.endsWith(".db"))
      .map(f => ({
        name: f,
        path: path.join(backupsDir, f),
        mtime: fs.statSync(path.join(backupsDir, f)).mtime.getTime()
      }))
      .sort((a, b) => b.mtime - a.mtime); // Sort by newest first

    // Delete backups beyond the limit
    if (backups.length > MAX_BACKUPS) {
      const toDelete = backups.slice(MAX_BACKUPS);
      toDelete.forEach(backup => {
        fs.unlinkSync(backup.path);
        console.log(`[Newsixity] Deleted old backup: ${backup.name}`);
      });
      console.log(`[Newsixity] Cleaned up ${toDelete.length} old backup(s), kept ${MAX_BACKUPS} most recent`);
    }
  } catch (error) {
    console.error("[Newsixity] Backup cleanup failed:", error);
  }
}

async function createDailyBackup(): Promise<void> {
  try {
    const db = getDb();

    // Create backups directory if it doesn't exist
    const backupsDir = path.join(process.cwd(), "data", "backups");
    if (!fs.existsSync(backupsDir)) {
      fs.mkdirSync(backupsDir, { recursive: true });
    }

    // Generate backup filename with timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, -5);
    const backupPath = path.join(backupsDir, `newsixity-auto-${timestamp}.db`);

    // Use SQLite VACUUM INTO to create a clean backup
    db.exec(`VACUUM INTO '${backupPath}'`);

    // Get backup file size
    const stats = fs.statSync(backupPath);
    const sizeKB = (stats.size / 1024).toFixed(2);

    console.log(`[Newsixity] Auto backup created: ${backupPath} (${sizeKB} KB)`);

    // Clean up old automatic backups (keep only 10 most recent)
    cleanupOldBackups(backupsDir, "newsixity-auto-");

    // Count remaining automatic backups
    const backups = fs.readdirSync(backupsDir)
      .filter(f => f.startsWith("newsixity-auto-") && f.endsWith(".db"));

    const totalBackups = backups.length;
    console.log(`[Newsixity] Total automatic backups: ${totalBackups}`);
  } catch (error) {
    console.error("[Newsixity] Auto backup failed:", error);
  }
}

/**
 * Start automatic daily backups at 3 AM
 */
export function startBackupScheduler(): void {
  if (globalForBackup.__newsixityBackupStarted) return;
  globalForBackup.__newsixityBackupStarted = true;

  console.log("[Newsixity] Starting daily backup scheduler (3 AM)");

  // Calculate time until next 3 AM
  const now = new Date();
  const next3AM = new Date();
  next3AM.setHours(3, 0, 0, 0);

  // If it's already past 3 AM today, schedule for tomorrow
  if (now > next3AM) {
    next3AM.setDate(next3AM.getDate() + 1);
  }

  const msUntil3AM = next3AM.getTime() - now.getTime();

  // Schedule first backup at 3 AM
  setTimeout(() => {
    createDailyBackup();

    // Then repeat every 24 hours
    globalForBackup.__newsixityBackupScheduler = setInterval(
      createDailyBackup,
      24 * 60 * 60 * 1000
    );
  }, msUntil3AM);

  // Create an immediate backup on startup
  createDailyBackup().catch(() => {});
}

export function stopBackupScheduler(): void {
  if (globalForBackup.__newsixityBackupScheduler) {
    clearInterval(globalForBackup.__newsixityBackupScheduler);
    globalForBackup.__newsixityBackupScheduler = undefined;
    globalForBackup.__newsixityBackupStarted = false;
    console.log("[Newsixity] Backup scheduler stopped");
  }
}
