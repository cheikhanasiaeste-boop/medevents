import "dotenv/config";
import { defineConfig } from "drizzle-kit";

export default defineConfig({
  dialect: "postgresql",
  out: "../../packages/shared/db",
  schema: "../../packages/shared/db/schema.ts",
  dbCredentials: {
    url:
      process.env.DATABASE_URL ??
      "postgresql://medevents:medevents@localhost:5432/medevents", // pragma: allowlist secret
  },
  introspect: { casing: "preserve" },
  verbose: true,
});
