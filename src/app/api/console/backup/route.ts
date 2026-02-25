import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import fs from "fs";
import path from "path";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { internalServerError } from "@/lib/server/api-response";

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
        console.log(`[Newsixity] Deleted old manual backup: ${backup.name}`);
      });
      console.log(`[Newsixity] Cleaned up ${toDelete.length} old manual backup(s), kept ${MAX_BACKUPS} most recent`);
    }
  } catch (error) {
    console.error("[Newsixity] Manual backup cleanup failed:", error);
  }
}

export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "console-backup",
    limit: 3,
    windowMs: 60 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const db = getDb();

    // Create backups directory if it doesn't exist
    const backupsDir = path.join(process.cwd(), "data", "backups");
    if (!fs.existsSync(backupsDir)) {
      fs.mkdirSync(backupsDir, { recursive: true });
    }

    // Generate backup filename with timestamp
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, -5);
    const backupPath = path.join(backupsDir, `newsixity-${timestamp}.db`);

    // Use SQLite VACUUM INTO to create a clean backup
    db.exec(`VACUUM INTO '${backupPath}'`);

    // Get backup file size
    const stats = fs.statSync(backupPath);
    const sizeKB = (stats.size / 1024).toFixed(2);

    // Clean up old manual backups (keep only 10 most recent)
    cleanupOldBackups(backupsDir, "newsixity-");

    // Count remaining manual backups
    const backups = fs.readdirSync(backupsDir)
      .filter(f => f.startsWith("newsixity-") && !f.startsWith("newsixity-auto-") && f.endsWith(".db"));

    const totalBackups = backups.length;

    return NextResponse.json({
      success: true,
      path: backupPath,
      size: `${sizeKB} KB`,
      timestamp,
      totalBackups,
    });
  } catch (e) {
    return internalServerError("Console backup POST error", e);
  }
}
