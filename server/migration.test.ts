import { describe, expect, it } from "vitest";

describe("Manus migration runtime", () => {
  it("uses the configured persistent database through the health endpoint", async () => {
    const baseUrl = process.env.TEST_BASE_URL || "http://127.0.0.1:3000";
    const response = await fetch(`${baseUrl}/api/health`);
    expect(response.ok).toBe(true);

    const body = await response.json() as {
      status?: string;
      db?: string;
      persistent?: boolean;
    };
    expect(body.status).toBe("ok");
    expect(body.persistent).toBe(true);
    expect(["mongodb", "neon-postgres"]).toContain(body.db);
  });
});
