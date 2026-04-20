import "server-only";
import { hash, verify } from "@node-rs/argon2";

// Algorithm.Argon2id = 2 (const enum; inlined manually due to isolatedModules)
const ARGON2_OPTIONS = {
  algorithm: 2 as const, // Argon2id
  memoryCost: 19_456,
  timeCost: 2,
  parallelism: 1,
} as const;

export async function hashPassword(plain: string): Promise<string> {
  if (plain.length < 12) {
    throw new Error("password must be at least 12 characters");
  }
  return hash(plain, ARGON2_OPTIONS);
}

export async function verifyPassword(
  hashed: string,
  plain: string,
): Promise<boolean> {
  try {
    return await verify(hashed, plain);
  } catch {
    return false;
  }
}
