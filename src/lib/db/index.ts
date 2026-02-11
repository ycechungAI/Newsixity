import Database from "better-sqlite3";
import path from "path";
import fs from "fs";
import { initializeSchema } from "./schema";

const DB_PATH = path.join(process.cwd(), "data", "newsixity.db");

function createDb(): Database.Database {
  const dir = path.dirname(DB_PATH);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const db = new Database(DB_PATH);
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
