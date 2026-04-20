import { describe, expect, it } from "vitest";
import * as schema from "@medevents/shared/db/schema";

describe("db schema", () => {
  it("exports the events table", () => {
    expect(schema).toHaveProperty("events");
  });

  it("exports the sources table", () => {
    expect(schema).toHaveProperty("sources");
  });

  it("exports the audit_log table", () => {
    expect(schema).toHaveProperty("audit_log");
  });
});
