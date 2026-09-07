import { describe, expect, it } from "vitest";

describe("Telegram credentials", () => {
  it("accepts the configured bot token", async () => {
    const token = process.env.TELEGRAM_BOT_TOKEN?.trim();
    expect(token).toBeTruthy();

    const response = await fetch(`https://api.telegram.org/bot${token}/getMe`);
    expect(response.ok).toBe(true);

    const body = await response.json() as { ok?: boolean; result?: { is_bot?: boolean } };
    expect(body.ok).toBe(true);
    expect(body.result?.is_bot).toBe(true);
  }, 30_000);

  it("accepts the configured chat id", async () => {
    const token = process.env.TELEGRAM_BOT_TOKEN?.trim();
    const chatId = process.env.TELEGRAM_CHAT_ID?.trim();
    expect(token).toBeTruthy();
    expect(chatId).toBeTruthy();

    const response = await fetch(
      `https://api.telegram.org/bot${token}/getChat?chat_id=${encodeURIComponent(chatId ?? "")}`,
    );
    expect(response.ok).toBe(true);

    const body = await response.json() as { ok?: boolean };
    expect(body.ok).toBe(true);
  }, 30_000);
});
