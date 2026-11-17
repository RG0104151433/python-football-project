const fs = require('fs'), path = require('path'), assert = require('assert/strict'), crypto = require('crypto');
const {pathToFileURL} = require('url');
const moduleRoot = process.env.PRESENTATION_NODE_MODULES || 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1112-737-0_26.1112.737.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules';
const {chromium} = require(path.join(moduleRoot, 'playwright'));

(async () => {
  const browser = await chromium.launch({executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true});
  const summary = JSON.parse(fs.readFileSync('outputs/tables/future_predictions/results-check-20261117-am/summary.json', 'utf8'));
  const errors = [], layouts = [];
  try {
    const context = await browser.newContext({offline: true, viewport: {width: 1440, height: 900}});
    const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message));
    await page.goto(pathToFileURL(path.resolve('presentation/index.html')).href);
    await page.waitForFunction(() => !!window.checkedResultsReady);
    const original = await page.evaluate(() => JSON.stringify(reviewAPI.getData().forecasts));
    await page.evaluate(() => reviewAPI.go(9));
    assert.equal(await page.locator('#resultTiles button').count(), 52);
    let totals = await page.locator('#resultTotals').textContent();
    for (const text of ['Correct 30', 'Wrong 13', 'Pending 8', 'Withheld 1', 'Evaluated 43', '69.8%']) assert(totals.includes(text), totals);
    assert.match(await page.locator('#resultTiles [data-id="future:unl-2026:003"]').textContent(), /3–1/);
    assert.match(await page.locator('#resultTiles [data-id="future:unl-2026:040"]').textContent(), /5–0/);
    await page.locator('#resultTiles [data-id="future:unl-2026:003"]').click();
    const dialog = page.locator('dialog[open]'); await dialog.waitFor();
    assert.match(await dialog.textContent(), /Actual score: 3–1/);
    assert.match(await dialog.textContent(), /uefa\.com/);
    await dialog.getByRole('button', {name: 'Close', exact: true}).click();
    await page.locator('#judgeMode').selectOption('three');
    totals = await page.locator('#resultTotals').textContent();
    for (const text of ['Correct 30', 'Wrong 14', 'Pending 8', 'Evaluated 44', '68.2%']) assert(totals.includes(text), totals);
    await page.locator('#judgeMode').selectOption('binary');
    fs.mkdirSync('presentation/_build', {recursive: true});
    for (const [width, height] of [[1440, 900], [1280, 720]]) {
      await page.setViewportSize({width, height});
      const state = await page.locator('main>.slide').nth(9).evaluate(el => ({width: el.clientWidth, height: el.clientHeight, scrollWidth: el.scrollWidth, scrollHeight: el.scrollHeight}));
      layouts.push({viewport: [width, height], ...state});
      assert(state.scrollWidth <= state.width + 2 && state.scrollHeight <= state.height + 2, JSON.stringify(state));
      await page.screenshot({path: `presentation/_build/results_20261117_${width}.png`});
    }
    // A subsequent manual import remains possible; restoring the seed is explicit.
    await page.evaluate(csv => reviewAPI.importCSV(csv), fs.readFileSync('presentation/results_template.csv', 'utf8'));
    assert.match(await page.locator('#resultTotals').textContent(), /Pending 52/);
    await page.locator('#restoreMorningResults').click();
    assert.match(await page.locator('#resultTotals').textContent(), /Evaluated 43/);
    await page.reload(); await page.waitForFunction(() => !!window.checkedResultsReady);
    assert.equal(await page.evaluate(() => JSON.stringify(reviewAPI.getData().forecasts)), original);
    await page.evaluate(() => reviewAPI.go(9));
    assert.match(await page.locator('#resultTotals').textContent(), /Correct 30/);
    assert.equal(errors.length, 0);
    fs.writeFileSync('presentation/checked_results_verification_20261117.json', JSON.stringify({date: '2026-11-17', HTML_sha256: crypto.createHash('sha256').update(fs.readFileSync('presentation/index.html')).digest('hex'), offline: true, initial_auto_load: true, actual_results: {final: 44, pending: 8}, main: summary.main, auxiliary: summary.auxiliary, score_tiles_and_source_dialog: true, manual_import_and_restore: true, refresh_retains_results: true, forecast_payload_unchanged: true, layouts, page_errors: errors}, null, 2) + '\n');
    console.log('Verified real morning results: 30/43 main, 30/44 auxiliary; offline load, display, source dialog, import/restore and forecast immutability.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
