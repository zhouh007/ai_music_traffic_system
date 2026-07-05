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

function loadSelectorConfig(platform) {
  const selectorPath = path.join(projectRoot, "data", "publish", "selectors", `${platform}.json`);
  if (!fs.existsSync(selectorPath)) {
    throw new Error(`Selector config not found: ${selectorPath}`);
  }
  return readJson(selectorPath);
}

function firstExisting(values) {
  for (const value of values || []) {
    if (value && String(value).trim()) {
      return String(value).trim();
    }
  }
  return "";
}

async function importPlaywright() {
  try {
    return await import("playwright");
  } catch (error) {
    throw new Error(
      "Playwright is not available in this project. Run `npm install playwright` in F:\\code\\ai_music_traffic_system first.",
    );
  }
}

async function fillFirst(page, selectors, value) {
  if (!value) return false;
  for (const selector of selectors || []) {
    const locator = page.locator(selector).first();
    if ((await locator.count()) > 0) {
      await locator.waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
      await locator.fill(value);
      return true;
    }
  }
  return false;
}

async function clickFirst(page, selectors) {
  for (const selector of selectors || []) {
    try {
      const locator = page.locator(selector).first();
      if ((await locator.count()) > 0) {
        await locator.waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
        await locator.scrollIntoViewIfNeeded().catch(() => {});
        await locator.click({ force: true, timeout: 10000 });
        return true;
      }
    } catch (_error) {
      continue;
    }
  }
  return false;
}

async function setInputFilesFirst(page, selectors, filePath) {
  for (const selector of selectors || []) {
    try {
      const locator = page.locator(selector).first();
      if ((await locator.count()) > 0) {
        await locator.waitFor({ state: "attached", timeout: 10000 }).catch(() => {});
        await locator.setInputFiles(filePath);
        return true;
      }
    } catch (_error) {
      continue;
    }
  }
  return false;
}

async function waitForAny(page, selectors, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    for (const selector of selectors || []) {
      const locator = page.locator(selector).first();
      if ((await locator.count()) > 0) {
        return true;
      }
    }
    await page.waitForTimeout(300);
  }
  return false;
}

async function clickFullTrackEntry(page, selectors) {
  const buttonSelectors = selectors.full_track_buttons || [];
  if (await clickFirst(page, buttonSelectors)) {
    return true;
  }
  const textCandidates = ["发布全曲", "全曲作品"];
  for (const text of textCandidates) {
    try {
      const locator = page.getByText(text, { exact: false }).first();
      if ((await locator.count()) > 0) {
        await locator.waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
        await locator.scrollIntoViewIfNeeded().catch(() => {});
        await locator.click({ force: true, timeout: 10000 });
        return true;
      }
    } catch (_error) {
      continue;
    }
  }
  const fallback = page.locator("button.submit").first();
  if ((await fallback.count()) > 0) {
    await fallback.waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
    await fallback.scrollIntoViewIfNeeded().catch(() => {});
    await fallback.click({ force: true, timeout: 10000 });
    return true;
  }
  return false;
}

async function run() {
  const args = parseArgs(process.argv);
  if (!args["job-file"]) {
    throw new Error("Missing required argument: --job-file");
  }

  const job = readJson(args["job-file"]);
  const selectors = loadSelectorConfig(job.platform);
  const headed = args.headless ? false : true;
  const pauseMs = Number(args["manual-login-ms"] || 60000);
  const dryRun = Boolean(args["dry-run"]);
  const { chromium } = await importPlaywright();
  const userDataDir = path.join(projectRoot, "data", "publish", "browser_profiles", job.platform);
  fs.mkdirSync(userDataDir, { recursive: true });
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: !headed,
    slowMo: 150,
  });
  const page = context.pages()[0] || await context.newPage();

  const payloadPath = path.join(job.package_dir, "publish_payload.json");
  const payload = readJson(payloadPath);
  const targetUrl = selectors.publish_entry_url || job.publish_url;
  console.log(`[music-upload] opening ${targetUrl}`);
  await page.goto(targetUrl, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);

  if (selectors.login_wait_hint) {
    console.log(`[music-upload] login hint: ${selectors.login_wait_hint}`);
  }
  if (pauseMs > 0) {
    console.log(`[music-upload] waiting ${pauseMs}ms for manual login / page readiness`);
    await page.waitForTimeout(pauseMs);
  }

  if (dryRun) {
    console.log("[music-upload] dry run only, browser steps skipped after page open");
    await context.close();
    return;
  }

  const summary = {
    platform: job.platform,
    mode: args.submit ? "explicit_submit_test" : "safe_semi_auto",
    fullTrackReady: false,
    audioUploaded: false,
    coverUploaded: false,
    titleFilled: false,
    captionFilled: false,
    lyricsFilled: false,
    draftClicked: false,
    submitClicked: false,
    humanReviewRequired: true,
  };

  if (Array.isArray(selectors.full_track_buttons) && selectors.full_track_buttons.length > 0) {
    const entered = await clickFullTrackEntry(page, selectors);
    console.log(`[music-upload] full track entry clicked: ${entered}`);
    summary.fullTrackReady = entered && await waitForAny(page, selectors.full_track_ready_checks || [], 15000);
    console.log(`[music-upload] full track form ready: ${summary.fullTrackReady}`);
    await page.waitForTimeout(4000);
  }

  if (summary.fullTrackReady) {
    summary.audioUploaded = await setInputFilesFirst(page, selectors.audio_inputs, payload.audio_path);
    console.log(`[music-upload] audio uploaded: ${summary.audioUploaded}`);
    await page.waitForTimeout(3000);
  }

  if (summary.audioUploaded) {
    await waitForAny(page, selectors.title_ready_checks || [], 15000);
    summary.coverUploaded = await setInputFilesFirst(page, selectors.cover_inputs, payload.cover_path);
    summary.titleFilled = await fillFirst(page, selectors.title_inputs, payload.title);
    summary.captionFilled = await fillFirst(page, selectors.caption_inputs, payload.caption);
    summary.lyricsFilled = await fillFirst(
      page,
      selectors.lyrics_inputs,
      payload.lyrics_path ? fs.readFileSync(payload.lyrics_path, "utf-8") : "",
    );
    summary.draftClicked = await clickFirst(page, selectors.draft_buttons);
  }

  if (args.submit) {
    summary.submitClicked = await clickFirst(page, selectors.submit_buttons);
  }

  if (!args.submit) {
    console.log("[music-upload] semi-auto mode: final submit intentionally skipped for manual review");
  }

  const outputPath = path.join(job.package_dir, "automation_last_run.json");
  fs.writeFileSync(outputPath, JSON.stringify(summary, null, 2), "utf-8");
  console.log(JSON.stringify(summary, null, 2));

  if (args["keep-open"]) {
    console.log("[music-upload] keep-open enabled, browser left running");
    return;
  }
  await context.close();
}

run().catch((error) => {
  console.error(`[music-upload] ${error.message}`);
  process.exit(1);
});
