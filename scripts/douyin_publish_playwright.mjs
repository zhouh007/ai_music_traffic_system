import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import url from "node:url";

const __filename = url.fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
      continue;
    }
    args[key] = next;
    i += 1;
  }
  return args;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

async function importPlaywright() {
  try {
    return await import("playwright");
  } catch (_error) {
    throw new Error("Playwright is not available in this project. Run `npm install` first.");
  }
}

async function waitForUploadInput(page, timeoutMs = 30000) {
  const selectors = [
    'input[type="file"][accept*="video"]',
    'input[type="file"]',
  ];
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const selector of selectors) {
      const locator = page.locator(selector).first();
      if ((await locator.count()) > 0) {
        return locator;
      }
    }
    await page.waitForTimeout(500);
  }
  return null;
}

async function setCaption(page, text) {
  const selectors = [
    'textarea[placeholder*="作品"]',
    'textarea[placeholder*="标题"]',
    'textarea',
    '[contenteditable="true"][data-placeholder*="作品"]',
    '[contenteditable="true"][data-placeholder*="标题"]',
    '[contenteditable="true"]',
  ];
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if ((await locator.count()) === 0) continue;
    try {
      await locator.waitFor({ state: "visible", timeout: 5000 }).catch(() => {});
      await locator.click({ force: true, timeout: 5000 }).catch(() => {});
      const tagName = await locator.evaluate((el) => el.tagName.toLowerCase()).catch(() => "");
      if (tagName === "textarea" || tagName === "input") {
        await locator.fill(text);
      } else {
        await page.keyboard.press(process.platform === "darwin" ? "Meta+A" : "Control+A").catch(() => {});
        await page.keyboard.press("Backspace").catch(() => {});
        await page.keyboard.type(text, { delay: 20 });
      }
      return true;
    } catch (_error) {
      continue;
    }
  }
  return false;
}

async function maybeClick(page, textCandidates) {
  for (const text of textCandidates) {
    try {
      const locator = page.getByText(text, { exact: false }).first();
      if ((await locator.count()) > 0) {
        await locator.click({ force: true, timeout: 3000 }).catch(() => {});
        return true;
      }
    } catch (_error) {
      continue;
    }
  }
  return false;
}

async function run() {
  const args = parseArgs(process.argv);
  if (!args["job-file"]) {
    throw new Error("Missing required argument: --job-file");
  }

  const job = readJson(args["job-file"]);
  const payload = readJson(path.join(job.package_dir, "publish_payload.json"));
  const { chromium } = await importPlaywright();
  const userDataDir = path.join(projectRoot, "data", "publish", "browser_profiles", "douyin");
  fs.mkdirSync(userDataDir, { recursive: true });

  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    slowMo: 120,
  });
  const page = context.pages()[0] || await context.newPage();
  const pauseMs = Number(args["manual-login-ms"] || 90000);

  console.log(`[douyin-upload] opening ${job.publish_url}`);
  await page.goto(job.publish_url, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);
  console.log(`[douyin-upload] waiting ${pauseMs}ms for manual login / page readiness`);
  await page.waitForTimeout(pauseMs);

  const summary = {
    platform: "douyin",
    videoUploaded: false,
    captionFilled: false,
    browserLeftOpen: true,
    targetUrl: page.url(),
    nextManualChecks: [
      "Confirm Douyin login is complete.",
      "Review uploaded video cover and playback.",
      "Adjust caption if needed, then click final publish manually.",
    ],
  };

  const uploadInput = await waitForUploadInput(page, 30000);
  if (!uploadInput) {
    throw new Error("Could not find Douyin video upload input after login wait.");
  }

  await uploadInput.setInputFiles(payload.video_path);
  summary.videoUploaded = true;
  console.log("[douyin-upload] video file selected");

  await page.waitForTimeout(15000);
  await maybeClick(page, ["继续上传", "继续", "下一步"]);
  await page.waitForTimeout(5000);

  const captionText = payload.caption || payload.title || "";
  summary.captionFilled = await setCaption(page, captionText);
  console.log(`[douyin-upload] caption filled: ${summary.captionFilled}`);

  const outputPath = path.join(job.package_dir, "automation_last_run_douyin.json");
  fs.writeFileSync(outputPath, JSON.stringify(summary, null, 2), "utf-8");
  console.log(JSON.stringify(summary, null, 2));

  if (args["keep-open"]) {
    console.log("[douyin-upload] browser left open for manual final publish");
    process.stdin.resume();
    await new Promise(() => {});
  }

  await context.close();
}

run().catch((error) => {
  console.error(`[douyin-upload] ${error.message}`);
  process.exitCode = 1;
});
