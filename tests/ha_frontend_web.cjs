// Browser acceptance for the production component, real HA WS, synthetic panel.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
if (process.env.PLANT_SETTINGS_DISTRO_PLAYWRIGHT === '1') {
  const files = require(path.join(path.dirname(require.resolve('playwright-core')), 'lib/utils/fileUtils.js'));
  files.removeFolders = dirs => Promise.all(dirs.map(dir => fs.promises.rm(dir, {recursive:true, force:true}).then(() => undefined, e => e)));
}
const origin = process.env.HA_BROWSER_ORIGIN;
assert.match(origin, /^http:\/\/127\.0\.0\.1:\d+$/);
const output = path.resolve('build/ha-frontend');
fs.mkdirSync(output, {recursive:true});

(async () => {
  const executablePath = process.env.HA_BROWSER_MANAGED_PLAYWRIGHT === '1' ? undefined : '/usr/bin/chromium';
  const browser = await chromium.launch({executablePath, headless:true, args:['--no-sandbox']});
  try {
    const context = await browser.newContext({viewport:{width:1280, height:900}, acceptDownloads:true});
    const page = await context.newPage(), errors = [], external = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.route('**/*', route => {
      if (new URL(route.request().url()).origin === origin) return route.continue();
      external.push(route.request().url()); return route.abort();
    });
    await page.addInitScript(token => { window.testCredentials = token; }, process.env.HA_BROWSER_TOKEN);
    async function until(predicate) {
      const deadline = Date.now() + 12000;
      while (Date.now() < deadline) {
        if (await page.evaluate(predicate)) return;
        await page.waitForTimeout(30);
      }
      throw new Error('Browser state timed out: ' + predicate);
    }
    async function idle() { await until(() => window.harness?.element._loaded && !harness.element._busy); }
    async function select() { await page.locator('#panel').selectOption(process.env.HA_BROWSER_ENTRY); await idle(); }
    async function refresh() { await page.locator('#refresh').click(); await idle(); }
    async function importSource(source) { await page.locator(`[data-import="${source}"]`).click(); await idle(); }
    await page.goto(origin + '/home_panel_browser_fixture/index.html', {waitUntil:'domcontentloaded'});
    await idle();
    assert.deepEqual(await page.evaluate(() => harness.calls.map(c => c.type)), ['home_panel/config/panels']);
    assert.equal(await page.locator('#panel').inputValue(), '', 'Never select a panel automatically');
    assert.equal(await page.locator('#refresh').isDisabled(), true);
    await page.locator('#menu').click();
    assert.equal(await page.evaluate(() => harness.menuEvents), 1);
    assert.equal(await page.locator('#panel option').count(), 3);
    assert.equal(await page.evaluate(() => window.injected), undefined, 'Names are text, never HTML');
    await select();
    assert.equal(await page.locator('#limit').textContent(), '16384');
    for (const source of ['candidate', 'backup', 'active']) {
      await importSource(source);
      assert.equal(await page.evaluate(() => harness.element._original.source), source);
      assert.match(await page.locator('#originalReport').textContent(), /Valid model/);
    }
    const original = await page.locator('#document').textContent();
    assert.ok(original.startsWith(' \r\n') && original.endsWith('\r\n'));
    await page.locator('#tab-check').click();
    assert.equal(await page.locator('#input').inputValue(), '', 'Import never overwrites local input');
    await page.locator('#input').fill(original);
    await page.locator('#validate').click(); await idle();
    assert.match(await page.locator('#validation').textContent(), /^Valid model/);
    await page.locator('#input').fill('broken');
    assert.match(await page.locator('#validation').textContent(), /Previous validation/);
    await page.locator('#validate').click(); await idle();
    assert.match(await page.locator('#validation').textContent(), /^Invalid model/);
    assert.equal(await page.locator('#document').textContent(), original);
    await page.locator('#tab-original').click();
    const downloadEvent = page.waitForEvent('download');
    await page.locator('#download').click();
    const download = await downloadEvent;
    assert.equal(download.suggestedFilename(), 'panel-active-r31.json');
    await download.saveAs(path.join(output, 'download.json'));
    assert.equal(fs.readFileSync(path.join(output, 'download.json'), 'utf8'), original);
    await require('./ha_frontend_draft.cjs')(page, output, original);
    await page.evaluate(async () => { await harness.hass.callWS({type:'home_panel/config/entities', entry_id:harness.element._entry, limit:50, include_inactive:true}); });
    fs.writeFileSync(path.join(output, 'preview.json'), JSON.stringify(await page.evaluate(() => harness.results), null, 2));
    // Dirty input survives a canceled selection; no status/POST is sent for it.
    const count = await page.evaluate(() => harness.calls.length);
    await page.locator('#panel').selectOption(process.env.HA_BROWSER_UNLOADED);
    await page.locator('#discard-dialog').waitFor();
    await page.locator('#discard-dialog button[value="cancel"]').click();
    await until(() => harness.element.shadowRoot.getElementById('panel').value === harness.element._entry);
    assert.equal(await page.locator('#panel').inputValue(), process.env.HA_BROWSER_ENTRY);
    assert.equal(await page.locator('#input').inputValue(), 'broken');
    assert.equal(await page.evaluate(() => harness.calls.length), count);
    await page.locator('#panel').selectOption(process.env.HA_BROWSER_UNLOADED);
    await page.locator('#discard-dialog button[value="discard"]').click();
    await until(() => harness.element._selected?.state === 'not_loaded');
    assert.equal(await page.locator('#refresh').isDisabled(), true);
    assert.equal(await page.locator('#input').inputValue(), '');
    await select();
    await page.locator('#tab-check').click();
    // Limits count UTF-8 bytes, not JS characters. Bad files do not replace input.
    await page.locator('#input').fill('\u042f'.repeat(8193));
    assert.equal(await page.locator('#validate').isDisabled(), true);
    assert.match(await page.locator('#inputBytes').textContent(), /16386 \/ 16384/);
    await page.locator('#file').setInputFiles({name:'bad.json', mimeType:'application/json', buffer:Buffer.from([0xff])});
    await until(() => harness.element._notice === 'badFile');
    assert.equal((await page.locator('#input').inputValue()).length, 8193);
    await page.locator('#file').setInputFiles({name:'large.json', mimeType:'application/json', buffer:Buffer.alloc(65537, 32)});
    await until(() => harness.element._notice === 'tooLarge');
    await page.locator('#file').setInputFiles({name:'valid.json', mimeType:'application/json', buffer:Buffer.from(original)});
    await until(() => harness.element._notice === 'fileLoaded');
    assert.equal(await page.locator('#validate').isDisabled(), false);
    // A slow local read must not overwrite newer typing.
    await page.evaluate(() => {
      harness.element._readFile({size:2, arrayBuffer:() => new Promise(resolve => { harness.releaseFile = resolve; })});
    });
    await page.locator('#input').fill('broken');
    await page.evaluate(() => harness.releaseFile(new TextEncoder().encode('{}').buffer));
    await page.waitForTimeout(50);
    assert.equal(await page.locator('#input').inputValue(), 'broken');
    await page.evaluate(() => harness.faults.push({error:'outcome_unknown'}));
    await page.locator('#validate').click(); await idle();
    assert.equal(await page.locator('#validate').isDisabled(), true);
    assert.match(await page.locator('#message').textContent(), /Result unknown/);
    assert.ok(!(await page.locator('#message').textContent()).includes('PRIVATE'));
    const afterLost = await page.evaluate(() => harness.calls.length);
    await page.waitForTimeout(100);
    assert.equal(await page.evaluate(() => harness.calls.length), afterLost, 'No automatic replay');
    await refresh();
    assert.equal(await page.locator('#validate').isDisabled(), false);
    await page.evaluate(() => harness.faults.push({error:'incompatible_response'}));
    await refresh();
    assert.match(await page.locator('#message').textContent(), /Firmware metadata/);
    assert.equal(await page.locator('#validate').isDisabled(), true);
    await refresh();
    await page.locator('#validate').click(); await idle();
    assert.match(await page.locator('#validation').textContent(), /^Invalid model/);
    await page.evaluate(() => harness.close());
    assert.equal(await page.locator('#validate').isDisabled(), true);
    await page.evaluate(() => harness.connect()); await idle();
    assert.equal(await page.locator('#validate').isDisabled(), true, 'Reconnect never makes stale status fresh');
    await refresh();
    assert.equal(await page.locator('#validate').isDisabled(), false);
    assert.match(await page.locator('#validation').textContent(), /Previous validation/);
    // Device busy / missing SD are distinct, and neither enables import.
    await page.evaluate(() => harness.faults.push({mutate:r => { r.status.busy = true; }}));
    await refresh();
    assert.equal(await page.locator('#validate').isDisabled(), true);
    await refresh();
    await page.evaluate(() => harness.faults.push({mutate:r => { r.status.sd_ready = false; }}));
    await refresh();
    assert.equal(await page.locator('[data-import="active"]').isDisabled(), true);
    assert.equal(await page.locator('#sd').textContent(), 'Unavailable');
    await refresh();
    await importSource('active');
    await page.evaluate(() => harness.faults.push({mutate:r => { r.status.files.active.sha256 = '0'.repeat(64); }}));
    await refresh();
    assert.equal(await page.locator('#sourceChanged').isVisible(), true);
    await refresh();
    for (const language of ['en', 'ru']) {
      await page.evaluate(language => { harness.hass.locale.language = language; harness.update(); }, language);
      for (const dark of [false, true]) {
        await page.evaluate(dark => harness.theme(dark), dark);
        for (const width of [1280, 390, 320]) {
          await page.setViewportSize({width, height:width > 700 ? 900 : 844});
          await page.evaluate(() => { harness.element.scrollTop = 0; });
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
          const overflow = await page.evaluate(() => {
            const root = harness.element.shadowRoot;
            return [...root.querySelectorAll('main, .selection, .facts, .files, .tabs, .file-row, button')]
              .filter(e => e.getClientRects().length && e.scrollWidth > e.clientWidth + 1).map(e => e.id || e.className);
          });
          assert.deepEqual(overflow, [], `${language} ${dark} ${width} horizontal overflow`);
          await page.screenshot({path:path.join(output, `panel-${language}-${dark ? 'dark' : 'light'}-${width}.png`), fullPage:true});
          await page.locator('#tab-check').click();
          assert.equal(await page.locator('#input').isVisible(), true);
          await page.locator('#input').scrollIntoViewIfNeeded();
          await page.screenshot({path:path.join(output, `check-${language}-${dark ? 'dark' : 'light'}-${width}.png`), fullPage:true});
          await page.locator('#tab-original').click();
        }
      }
    }
    // HA may reserve room for a sidebar in a wide browser: use container width.
    await page.setViewportSize({width:1280, height:900});
    for (const width of [850, 460, 320]) {
      await page.evaluate(width => { harness.element.style.width = width + 'px'; }, width);
      assert.equal(await page.evaluate(() => harness.element.scrollWidth > harness.element.clientWidth), false, `HA content width ${width}`);
      assert.deepEqual(await page.evaluate(() => [...harness.element.shadowRoot.querySelectorAll('.file-row, .selection, .tabs')]
        .filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.className)), []);
    }
    await page.evaluate(() => { harness.element.style.width = ''; });
    await page.locator('#tab-original').focus();
    await page.locator('#tab-original').press('ArrowRight');
    assert.equal(await page.locator('#tab-editor').getAttribute('aria-selected'), 'true');
    await page.locator('#tab-editor').press('ArrowRight');
    assert.equal(await page.locator('#tab-check').getAttribute('aria-selected'), 'true');
    await page.locator('#tab-check').press('Home');
    assert.equal(await page.locator('#tab-original').getAttribute('aria-selected'), 'true');
    // Dropped privileges clear buffers and discard an already completed, delayed reply.
    await page.evaluate(() => harness.faults.push({hold:true}));
    await page.locator('[data-import="active"]').click();
    await until(() => typeof harness.release === 'function');
    await page.evaluate(() => { harness.hass.user.is_admin = false; harness.update(); harness.release(); });
    await page.waitForTimeout(50);
    assert.equal(await page.locator('main').isVisible(), false);
    assert.equal(await page.locator('#document').textContent(), '');
    assert.equal(await page.locator('#input').inputValue(), '');
    assert.equal(await page.evaluate(() => harness.element._original), null);
    assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
    await page.evaluate(() => { harness.hass.user.is_admin = true; harness.update(); }); await idle();
    assert.equal(await page.locator('#panel').inputValue(), '');
    await page.evaluate(() => harness.faults.push({mutate:r => { r.panels = []; }}));
    await page.locator('#reload').click(); await idle();
    assert.equal(await page.locator('#panel option').count(), 1);
    assert.deepEqual(errors, [], 'No browser exceptions');
    assert.deepEqual(external, [], 'No CDN, third-party or direct device requests');
    assert.ok((await page.evaluate(() => harness.calls)).every(c => /^home_panel\/config\/(panels|status|import|validate|draft_get|draft_save|draft_delete|draft_history_get|model_check|model_changes|entities)$/.test(c.type)));
    await page.evaluate(() => harness.close());
    console.log('HA browser acceptance passed: real auth/WS, 24 screenshots, import/UTF-8/download, failures, lifecycle and admin guards.');
    await context.close();
    await require('./ha_frontend_navigation.cjs')(browser, origin, process.env.HA_BROWSER_TOKEN, process.env.HA_BROWSER_ENTRY);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
