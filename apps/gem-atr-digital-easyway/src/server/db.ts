import Database from 'better-sqlite3';
import { initSchema } from './schema';

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (db) return db;

  const filePath = process.env.DATABASE_URL || './gem-atr.db';
  db = new Database(filePath);
  initSchema(db);
  return db;
}
