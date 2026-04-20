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

  it("treats empty-string form fields as absent (blank filter submit doesn't 500)", () => {
    // HTML forms with unfilled inputs submit empty strings, not absent params.
    // Without coercion, z.string().min(1) and z.enum([...]) both reject "".
    const f = parseEventsFilter({
      q: "",
      lifecycle: "",
      is_published: "",
      source_id: "",
      page: "",
      per_page: "",
    });
    expect(f.q).toBeUndefined();
    expect(f.lifecycle).toBeUndefined();
    expect(f.is_published).toBeUndefined();
    expect(f.source_id).toBeUndefined();
    expect(f.page).toBe(1);
    expect(f.per_page).toBe(20);
  });
});
