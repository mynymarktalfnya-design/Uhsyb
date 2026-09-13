import { describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";

const sourceDir = "/home/ubuntu/work_publish/ljdyd-mbny-mrkt-lmHdth-nskh-mn-bryd-Hsyn-blsm/market-backend";
const pythonBin = "/home/ubuntu/work_publish/ljdyd-mbny-mrkt-lmHdth-nskh-mn-bryd-Hsyn-blsm/.venv/bin/python";

describe("Neon database secret", () => {
  it("connects and responds to a lightweight database ping", () => {
    const result = spawnSync(
      pythonBin,
      ["-c", "from database import db; assert db.command('ping')['ok'] == 1"],
      {
        cwd: sourceDir,
        env: { ...process.env, NEON_DATABASE_URL: process.env.NEON_DATABASE_URL },
        encoding: "utf8",
        timeout: 20_000,
      },
    );

    expect(result.status, result.stderr || result.stdout).toBe(0);
  });
});
