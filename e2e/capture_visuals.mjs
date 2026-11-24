import { chromium } from "@playwright/test";
import fs from "fs";
import path from "path";

const screenshotDir = "/Users/samarkumar/.gemini/antigravity/brain/1a22562c-bff0-41fb-b0e0-97a843e7d0dc/screenshots";
if (!fs.existsSync(screenshotDir)) {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

async function run() {
  console.log("Launching Chromium browser...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
  });
  const page = await context.newPage();

  console.log("Navigating to http://127.0.0.1:5173...");
  await page.goto("http://127.0.0.1:5173", { waitUntil: "networkidle" });

  console.log("Capturing 01_homepage.png...");
  await page.screenshot({ path: path.join(screenshotDir, "01_homepage.png"), fullPage: true });

  console.log("Testing Hapur -> Noida Sector 62...");
  const originInput = page.getByPlaceholder("Origin stop or address");
  const destInput = page.getByPlaceholder("Destination stop or address");
  const planButton = page.getByRole("button", { name: "Plan journey" });

  await originInput.fill("Hapur");
  await destInput.fill("Noida Sector 62");
  await planButton.click();

  await page.waitForSelector("text=Hapur → Noida Sector 62", { timeout: 15000 });
  console.log("Capturing 02_hapur_noida_results.png...");
  await page.screenshot({ path: path.join(screenshotDir, "02_hapur_noida_results.png"), fullPage: true });

  console.log("Testing Patna -> Delhi...");
  await originInput.fill("Patna");
  await destInput.fill("Delhi");
  await planButton.click();

  await page.waitForSelector("text=Patna → Delhi", { timeout: 15000 });
  console.log("Capturing 03_patna_delhi_results.png...");
  await page.screenshot({ path: path.join(screenshotDir, "03_patna_delhi_results.png"), fullPage: true });

  console.log("Opening Operations Command Center...");
  const opButton = page.getByRole("button", { name: "Open operations command center" });
  await opButton.click();

  await page.waitForSelector("text=Command Center", { timeout: 10000 });
  console.log("Capturing 04_operations_center.png...");
  await page.screenshot({ path: path.join(screenshotDir, "04_operations_center.png"), fullPage: true });

  console.log("All visual browser tests passed successfully!");
  await browser.close();
}

run().catch((err) => {
  console.error("Browser test failed:", err);
  process.exit(1);
});
