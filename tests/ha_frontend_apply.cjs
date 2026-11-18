// Production frontend + real HA WebSocket, synthetic configuration lifecycle only.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
if (process.env.HA_BROWSER_MANAGED_PLAYWRIGHT !== '1') {
  const files = require(path.join(path.dirname(require.resolve('playwright-core')), 'lib/utils/fileUtils.js'));
  files.removeFolders = dirs => Promise.all(dirs.map(dir => fs.promises.rm(dir, {recursive:true, force:true}).then(() => undefined, e => e)));
}
const origin = process.env.HA_BROWSER_ORIGIN;
assert.match(origin, /^http:\/\/127\.0\.0\.1:\d+$/);
const output = path.resolve('build/ha-apply');
fs.mkdirSync(output, {recursive:true});
(async () => {
  const executablePath = process.env.HA_BROWSER_MANAGED_PLAYWRIGHT === '1' ? undefined : '/usr/bin/chromium';
  const browser = await chromium.launch({executablePath, headless:true, args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1280, height:900}}), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    await page.addInitScript(token => { window.testCredentials = token; }, process.env.HA_BROWSER_TOKEN);
    async function idle() { await page.waitForFunction(() => window.harness?.element._loaded && !harness.element._busy); }
    const applies = () => page.evaluate(() => harness.calls.filter(c => c.type.endsWith('/apply')).length);
    await page.goto(origin + '/home_panel_browser_fixture/index.html'); await idle();
    await page.locator('#panel').selectOption(process.env.HA_BROWSER_ENTRY); await idle();
    assert.equal(await page.locator('#apply-candidate').isDisabled(), true);
    await page.locator('[data-import="active"]').click(); await idle();
    await page.locator('#edit-original').click();
    await page.locator('#draft-room-name').fill('Детская');
    await page.locator('#draft-update-room').click();
    await page.locator('#draft-check').click(); await idle();
    page.once('dialog', dialog => dialog.accept());
    await page.locator('#draft-send').click(); await idle();
    assert.equal(await applies(), 0, 'Send is not Apply');
    assert.equal(await page.locator('#apply-candidate').isEnabled(), true);
    assert.match(await page.locator('#activation-status').textContent(), /Candidate ready/);
    if (process.env.HA_APPLY_OUTCOME === 'maintenance') {
      await page.locator('[data-import="candidate"]').click(); await idle();
      const discard = page.locator('#discard-candidate');
      const recover = page.locator('#recover-candidate');
      for (const width of [320, 1280]) {
        await page.setViewportSize({width, height:900});
        assert.equal(await discard.evaluate(el => el.scrollWidth <= el.clientWidth + 1), true);
      }
      page.once('dialog', dialog => dialog.dismiss());
      await discard.click(); await idle();
      assert.equal(await page.evaluate(() => harness.calls.some(c => c.type.endsWith('/discard'))), false);
      page.once('dialog', dialog => dialog.accept());
      await discard.click(); await idle();
      assert.match(await page.locator('#message').textContent(), /Candidate removed/);
      assert.equal(await page.locator('#apply-candidate').isDisabled(), true);
      await page.locator('[data-import="backup"]').click(); await idle();
      await page.setViewportSize({width:320, height:900});
      await page.evaluate(() => { harness.hass.locale.language = 'ru'; harness.theme(true); harness.update(); });
      await recover.scrollIntoViewIfNeeded();
      assert.equal(await page.locator('#originalInfo').evaluate(el => el.offsetHeight <= 32), true);
      assert.equal(await recover.evaluate(el => el.scrollWidth <= el.clientWidth + 1), true);
      await page.screenshot({path:path.join(output, 'recover-ru-dark-320.png'), fullPage:true});
      page.once('dialog', dialog => dialog.accept());
      await recover.click(); await idle();
      assert.match(await page.locator('#message').textContent(), /Резервная копия сохранена как кандидат/);
      assert.match(await page.locator('#activation-status').textContent(), /r33/);
      assert.equal(await page.locator('#apply-candidate').isEnabled(), true);
      assert.equal(await applies(), 0, 'Recovery only stages a candidate');
      assert.equal(await page.evaluate(() => harness.element.$('draft-editor').document.rooms[0].name), 'Детская');
      assert.deepEqual(errors, []);
      return;
    }
    const beforeCancel = await page.evaluate(() => harness.calls.length);
    page.once('dialog', dialog => dialog.dismiss());
    await page.locator('#apply-candidate').click(); await idle();
    assert.equal(await page.evaluate(() => harness.calls.length), beforeCancel);
    if (process.env.HA_APPLY_OUTCOME === 'lost') await page.evaluate(() => harness.faults.push({lost:true}));
    page.once('dialog', dialog => { assert.match(dialog.message(), /r32/); return dialog.accept(); });
    await page.locator('#apply-candidate').click(); await idle();
    assert.equal(await applies(), 1);
    assert.equal(await page.locator('#apply-candidate').isDisabled(), true);
    assert.match(await page.locator('#activation-status').textContent(), process.env.HA_APPLY_OUTCOME === 'lost' ? /unknown/ : /Restart scheduled/);
    for (let i = 0; i < 3; i++) { await page.locator('#refresh').click(); await idle(); }
    const expected = process.env.HA_APPLY_OUTCOME === 'rollback' ? /Trial rolled back/ : /Running configuration confirmed/;
    assert.match(await page.locator('#activation-status').textContent(), expected);
    assert.equal(await applies(), 1, 'Inspection never replays Apply');
    assert.equal(await page.locator('#apply-candidate').isDisabled(), true);
    for (const language of ['en', 'ru']) for (const dark of [false, true]) for (const width of [320, 1280]) {
      await page.evaluate(({language, dark}) => { harness.hass.locale.language = language; harness.theme(dark); harness.update(); }, {language, dark});
      await page.setViewportSize({width, height:900});
      await page.locator('#activation-tools').scrollIntoViewIfNeeded();
      assert.deepEqual(await page.evaluate(() => [...harness.element.shadowRoot.querySelectorAll('#activation-tools, #activation-tools button, #activation-status')]
        .filter(n => n.getClientRects().length && n.scrollWidth > n.clientWidth + 1).map(n => n.id)), [], 'Apply controls fit');
      if (process.env.HA_APPLY_OUTCOME === 'confirmed') await page.screenshot({path:path.join(output, `apply-${language}-${dark ? 'dark' : 'light'}-${width}.png`), fullPage:true});
    }
    const count = await applies();
    await page.waitForTimeout(150);
    assert.equal(await applies(), count);
    await page.evaluate(() => harness.close());
    assert.equal(await page.locator('#apply-candidate').isDisabled(), true);
    assert.match(await page.locator('#activation-status').textContent(), /неизвестен/);
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
