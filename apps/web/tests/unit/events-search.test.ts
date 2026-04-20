import { describe, expect, it } from "vitest";
import { parseEventsFilter } from "@/lib/search/events";

describe("parseEventsFilter", () => {
  it("returns defaults on empty input", () => {
    const f = parseEventsFilter({});
    expect(f.page).toBe(1);
    expect(f.per_page).toBe(20);
    expect(f.q).toBeUndefined();
  });

  it("trims and accepts q within bounds", () => {
    const f = parseEventsFilter({ q: "  ortho  " });
    expect(f.q).toBe("ortho");
  });

  it("coerces page and per_page from strings", () => {
    const f = parseEventsFilter({ page: "3", per_page: "50" });
    expect(f.page).toBe(3);
    expect(f.per_page).toBe(50);
  });

  it("rejects invalid lifecycle", () => {
    expect(() => parseEventsFilter({ lifecycle: "bogus" })).toThrow();
  });

  it("rejects per_page > 100", () => {
    expect(() => parseEventsFilter({ per_page: "200" })).toThrow();
  });

  it("rejects non-uuid source_id", () => {
    expect(() => parseEventsFilter({ source_id: "not-a-uuid" })).toThrow();
  });
});
