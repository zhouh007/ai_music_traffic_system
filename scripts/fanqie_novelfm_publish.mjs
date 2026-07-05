import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import url from "node:url";

const __filename = url.fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const publishEntryUrl = "https://www.novelfm.com/creator/music/publishWorks";
const uploadPageUrl = "https://www.novelfm.com/creator/music/finished/ugc/uploadProduct";

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
    throw new Error("Playwright is not available. Run `npm install` in F:\\code\\ai_music_traffic_system.");
  }
}

async function waitForUrl(page, matcher, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (matcher(page.url())) return true;
    await page.waitForTimeout(300);
  }
  return false;
}

async function clickFirstVisible(page, selectors, timeoutMs = 8000) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    try {
      if ((await locator.count()) === 0) continue;
      await locator.waitFor({ state: "visible", timeout: timeoutMs }).catch(() => {});
      await locator.scrollIntoViewIfNeeded().catch(() => {});
      await locator.click({ force: true, timeout: timeoutMs });
      return true;
    } catch (_error) {
      continue;
    }
  }
  return false;
}

async function uploadThroughTriggeredInput(page, triggerLocator, filePath, acceptHint = "") {
  const existingCount = await page.locator("input[type='file']").count();
  const fileChooserPromise = page.waitForEvent("filechooser", { timeout: 3000 }).catch(() => null);
  await triggerLocator.click({ force: true, timeout: 10000 });

  const chooser = await fileChooserPromise;
  if (chooser) {
    await chooser.setFiles(filePath);
    return true;
  }

  const deadline = Date.now() + 6000;
  while (Date.now() < deadline) {
    const fileInputs = page.locator("input[type='file']");
    const total = await fileInputs.count();
    if (total > existingCount) {
      for (let index = total - 1; index >= existingCount; index -= 1) {
        const locator = fileInputs.nth(index);
        const accept = (await locator.getAttribute("accept")) || "";
        if (!acceptHint || accept.includes(acceptHint)) {
          await locator.setInputFiles(filePath);
          return true;
        }
      }
    }
    await page.waitForTimeout(150);
  }

  return false;
}

async function uploadByFormLabel(page, labelText, filePath, fallbackSelector = "") {
  const row = page.locator(".arco-form-item").filter({ hasText: labelText }).first();
  if ((await row.count()) === 0) return false;

  const candidates = [
    row.locator(".common-file-upload-wrapper").first(),
    row.locator(".image-upload-input").first(),
    row.locator(".upload-input-container-Xm4c1M").first(),
    row.locator(".image-upload-input-btn").first(),
    row.locator(".grid-center").first(),
    fallbackSelector ? page.locator(fallbackSelector).first() : null,
  ].filter(Boolean);

  for (const locator of candidates) {
    try {
      if ((await locator.count()) === 0) continue;
      await locator.waitFor({ state: "visible", timeout: 5000 }).catch(() => {});
      await locator.scrollIntoViewIfNeeded().catch(() => {});
      const acceptHint =
        labelText.includes("封面") ? "image/" : labelText.includes("歌词") ? "text/plain" : labelText.includes("完整歌曲") ? "audio/" : "";
      if (await uploadThroughTriggeredInput(page, locator, filePath, acceptHint)) {
        return true;
      }
    } catch (_error) {
      continue;
    }
  }

  return false;
}

async function fillTextByPlaceholder(page, placeholder, value) {
  if (!value) return false;
  const locator = page.locator(`input[placeholder='${placeholder}'], textarea[placeholder='${placeholder}']`).first();
  if ((await locator.count()) === 0) return false;
  await locator.waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
  await locator.fill(value);
  return true;
}

async function fillNthTagInput(page, index, value) {
  if (!value) return false;
  const locator = page.locator("input.arco-input-tag-input").nth(index);
  if ((await locator.count()) === 0) return false;
  await locator.waitFor({ state: "visible", timeout: 10000 }).catch(() => {});
  await locator.fill(value);
  await locator.press("Enter").catch(() => {});
  return true;
}

async function chooseAiYes(page) {
  const aiRow = page.locator(".arco-form-item").filter({ hasText: "AI" }).first();
  if ((await aiRow.count()) === 0) return false;
  const yesLabel = aiRow.locator("label.arco-radio").filter({ hasText: "是" }).first();
  const yesInput = yesLabel.locator("input[type='radio']").first();
  if ((await yesLabel.count()) === 0) return false;
  await yesLabel.scrollIntoViewIfNeeded().catch(() => {});
  await yesLabel.click({ force: true, timeout: 10000 }).catch(() => {});
  await yesInput.click({ force: true, timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(500);
  const cls = (await yesLabel.getAttribute("class")) || "";
  return cls.includes("arco-radio-checked");
}

async function ensureUploadForm(page) {
  if (page.url().startsWith(uploadPageUrl)) return true;
  await page.goto(publishEntryUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);
  if (await waitForUrl(page, (value) => value.startsWith(uploadPageUrl), 3000)) return true;
  const clicked = await clickFirstVisible(page, [
    "button.arco-btn.arco-btn-dashed",
    ".publish-works button",
    "button:has-text('发布作品')",
  ]);
  if (!clicked) return false;
  return waitForUrl(page, (value) => value.startsWith(uploadPageUrl), 15000);
}

async function collectValidationSnapshot(page) {
  const snapshot = await page.evaluate(() => {
    const bodyText = document.body.innerText || "";
    const errors = [...document.querySelectorAll(".arco-form-message, .arco-form-item-status-error, .arco-form-item-explain, .arco-trigger-popup, .arco-message, .arco-notification")]
      .map((el) => (el.textContent || "").trim())
      .filter(Boolean);
    return {
      url: location.href,
      bodySnippet: bodyText.slice(0, 2000),
      errors,
    };
  });
  return snapshot;
}

async function keepProcessAlive() {
  await new Promise(() => {});
}

async function run() {
  const args = parseArgs(process.argv);
  if (!args["job-file"]) {
    throw new Error("Missing required argument: --job-file");
  }

  const job = readJson(args["job-file"]);
  const payload = readJson(path.join(job.package_dir, "publish_payload.json"));
  const meta = readJson(payload.meta_path);
  const pauseMs = Number(args["manual-login-ms"] || 15000);
  const keepOpen = Boolean(args["keep-open"]);
  const { chromium } = await importPlaywright();
  const userDataDir = path.join(projectRoot, "data", "publish", "browser_profiles", "fanqie_music_novelfm");
  fs.mkdirSync(userDataDir, { recursive: true });

  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    slowMo: 150,
  });
  const page = context.pages()[0] || await context.newPage();

  await page.goto(publishEntryUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(pauseMs);

  const ready = await ensureUploadForm(page);
  if (!ready) {
    throw new Error("Could not open the Novelfm upload form.");
  }

  await page.waitForTimeout(2000);
  await clickFirstVisible(page, [".add-song-section"]);
  await page.waitForTimeout(1000);

  const summary = {
    title: payload.title,
    uploadFormReady: true,
    audioUploaded: false,
    lyricsUploaded: false,
    coverUploaded: false,
    titleFilled: false,
    lyricistFilled: false,
    composerFilled: false,
    producerFilled: false,
    singerFilled: false,
    aiMarked: false,
    nextClicked: false,
    validation: null,
    humanReviewRequired: true,
    pageUrl: page.url(),
  };

  summary.audioUploaded = await uploadByFormLabel(page, "完整歌曲", payload.audio_path);
  await page.waitForTimeout(2500);
  summary.lyricsUploaded = await uploadByFormLabel(page, "歌词", payload.lyrics_path);
  await page.waitForTimeout(1500);
  summary.titleFilled = await fillTextByPlaceholder(page, "请输入作品名称", payload.title);
  summary.lyricistFilled = await fillNthTagInput(page, 0, "AI Music Traffic");
  summary.composerFilled = await fillNthTagInput(page, 1, "AI Music Traffic");
  summary.producerFilled = await fillNthTagInput(page, 2, "AI Music Traffic");
  summary.singerFilled = await fillNthTagInput(page, 3, "AI Music Traffic");
  summary.coverUploaded = await uploadByFormLabel(page, "歌曲封面", payload.cover_path);
  await page.waitForTimeout(1500);
  summary.aiMarked = await chooseAiYes(page);

  if (args["next-step"]) {
    summary.nextClicked = await clickFirstVisible(page, [".next-button", "button:has-text('下一步')"]);
    await page.waitForTimeout(2000);
  }
  summary.pageUrl = page.url();
  summary.validation = await collectValidationSnapshot(page);

  const outputPath = path.join(job.package_dir, "novelfm_automation_last_run.json");
  fs.writeFileSync(outputPath, JSON.stringify(summary, null, 2), "utf-8");
  console.log(JSON.stringify(summary, null, 2));

  if (keepOpen) {
    console.log("[novelfm-upload] browser left open for manual review");
    await keepProcessAlive();
  }

  await context.close();
}

run().catch((error) => {
  console.error(`[novelfm-upload] ${error.message}`);
  process.exit(1);
});
