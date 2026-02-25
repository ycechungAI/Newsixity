import Database from "better-sqlite3";
import path from "path";
import fs from "fs";
import { initializeSchema } from "./schema";

function resolveDbPath(): string {
  const override = process.env.NEWSIXITY_DB_PATH?.trim();
  if (!override) {
    return path.join(process.cwd(), "data", "newsixity.db");
  }

  return path.isAbsolute(override)
    ? override
    : path.join(process.cwd(), override);
}

function createDb(): Database.Database {
  const dbPath = resolveDbPath();
  const dir = path.dirname(dbPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const db = new Database(dbPath);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  initializeSchema(db);
  return db;
}

const globalForDb = globalThis as unknown as {
  __newsixityDb: Database.Database | undefined;
};

export function getDb(): Database.Database {
  if (!globalForDb.__newsixityDb) {
    globalForDb.__newsixityDb = createDb();
  }
  return globalForDb.__newsixityDb;
}

export function closeDbConnection(): void {
  if (!globalForDb.__newsixityDb) return;
  globalForDb.__newsixityDb.close();
  globalForDb.__newsixityDb = undefined;
}
