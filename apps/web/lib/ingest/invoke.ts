import "server-only";
import { spawn } from "node:child_process";
import path from "node:path";

const REPO_ROOT = path.resolve(process.cwd(), "..", "..");

export type InvokeResult = {
  exitCode: number;
  stdout: string;
  stderr: string;
  durationMs: number;
};

/**
 * Spawn `medevents-ingest run --source <code>` against the configured DB.
 * Sync model: blocks until the child exits or 60s timeout.
 * If this becomes flaky in production, REMOVE the calling button rather than
 * adding job infrastructure (see W1 spec §8 sync-run guardrail).
 */
export async function runIngestForSource(
  sourceCode: string,
): Promise<InvokeResult> {
  const start = Date.now();

  return new Promise<InvokeResult>((resolve, reject) => {
    const child = spawn(
      "uv",
      [
        "--directory",
        "services/ingest",
        "run",
        "medevents-ingest",
        "run",
        "--source",
        sourceCode,
      ],
      {
        cwd: REPO_ROOT,
        env: { ...process.env, DATABASE_URL: process.env.DATABASE_URL },
      },
    );

    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error("ingest run timed out after 60s"));
    }, 60_000);

    child.stdout.on("data", (b: Buffer) => (stdout += b.toString()));
    child.stderr.on("data", (b: Buffer) => (stderr += b.toString()));
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve({
        exitCode: code ?? -1,
        stdout,
        stderr,
        durationMs: Date.now() - start,
      });
    });
  });
}
