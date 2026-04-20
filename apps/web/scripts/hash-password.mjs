#!/usr/bin/env node
// Algorithm.Argon2id = 2 (numeric value of the @node-rs/argon2 const enum)
import { hash } from "@node-rs/argon2";
import process from "node:process";

async function readSecret(prompt) {
  process.stdout.write(prompt);
  if (!process.stdin.isTTY) {
    throw new Error("hash-password.mjs requires an interactive TTY");
  }
  process.stdin.setRawMode(true);
  process.stdin.resume();
  process.stdin.setEncoding("utf8");

  return new Promise((resolve, reject) => {
    let buf = "";
    const onData = (chunk) => {
      for (const ch of chunk) {
        // Enter (LF, CR) → submit
        if (ch === "\n" || ch === "\r") {
          process.stdin.setRawMode(false);
          process.stdin.pause();
          process.stdin.removeListener("data", onData);
          process.stdout.write("\n");
          resolve(buf);
          return;
        }
        // Ctrl-C → cancel
        if (ch === "\u0003") {
          process.stdin.setRawMode(false);
          process.stdin.pause();
          process.stdin.removeListener("data", onData);
          process.stdout.write("\n");
          reject(new Error("Cancelled"));
          return;
        }
        // Backspace / DEL → erase last char
        if (ch === "\u007f" || ch === "\b") {
          if (buf.length > 0) {
            buf = buf.slice(0, -1);
            process.stdout.write("\b \b");
          }
          continue;
        }
        // Ctrl-D EOF → submit
        if (ch === "\u0004") {
          process.stdin.setRawMode(false);
          process.stdin.pause();
          process.stdin.removeListener("data", onData);
          process.stdout.write("\n");
          resolve(buf);
          return;
        }
        // Printable → buffer + mask
        buf += ch;
        process.stdout.write("*");
      }
    };
    process.stdin.on("data", onData);
  });
}

const password = await readSecret(
  "Admin password (will be hashed; min 12 chars): ",
);

if (password.length < 12) {
  console.error("ERROR: password must be at least 12 characters");
  process.exit(1);
}

const adminHash = await hash(password, {
  algorithm: 2, // Argon2id
  memoryCost: 19_456,
  timeCost: 2,
  parallelism: 1,
});

console.log("\nADMIN_PASSWORD_HASH=" + adminHash);
console.log("\nCopy the line above into your .env file.");
