import { describe, expect, it } from "vitest";

describe("database health", () => {
  it("uses the configured persistent database", async () => {
    const baseUrl = process.env.TEST_BASE_URL ?? "http://127.0.0.1:8080";
    const response = await fetch(`${baseUrl}/api/health`);
    expect(response.ok).toBe(true);

    const payload = (await response.json()) as {
      status?: string;
      db?: string;
      persistent?: boolean;
    };

    expect(payload.persistent).toBe(true);
    expect(payload.db).not.toBe("mongomock");
  }, 15_000);
});
