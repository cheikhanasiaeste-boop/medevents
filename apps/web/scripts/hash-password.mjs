#!/usr/bin/env node
import argon2 from "argon2";
import readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";

const rl = readline.createInterface({ input, output, terminal: true });

const password = await rl.question(
  "Admin password (will be hashed; min 12 chars): ",
);
rl.close();

if (password.length < 12) {
  console.error("ERROR: password must be at least 12 characters");
  process.exit(1);
}

const hash = await argon2.hash(password, {
  type: argon2.argon2id,
  memoryCost: 19_456,
  timeCost: 2,
  parallelism: 1,
});

console.log("\nADMIN_PASSWORD_HASH=" + hash);
console.log("\nCopy the line above into your .env file.");
