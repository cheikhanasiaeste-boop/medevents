import { describe, expect, it } from "vitest";
import { hashPassword, verifyPassword } from "@/lib/auth/password";

describe("password hashing", () => {
  it("verifies a correct password", async () => {
    const hash = await hashPassword("hunter2-correct-horse");
    await expect(verifyPassword(hash, "hunter2-correct-horse")).resolves.toBe(
      true,
    );
  });

  it("rejects an incorrect password", async () => {
    const hash = await hashPassword("hunter2-correct-horse");
    await expect(verifyPassword(hash, "wrong-password")).resolves.toBe(false);
  });

  it("emits an argon2id-prefixed hash", async () => {
    const hash = await hashPassword("anything-long");
    expect(hash).toMatch(/^\$argon2id\$/);
  });
});
