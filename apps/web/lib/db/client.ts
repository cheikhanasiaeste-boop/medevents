import "server-only";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "@medevents/shared/db/schema";

const url = process.env.DATABASE_URL;
if (!url) {
  throw new Error("DATABASE_URL is required");
}

// Single connection pool for the Next.js process. postgres-js handles pooling internally.
const client = postgres(url, {
  max: 10,
  idle_timeout: 20,
  prepare: false, // PgBouncer compatibility (Neon)
});

export const db = drizzle(client, { schema });
export const sql = client;
export { schema };
