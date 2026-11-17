// Real HA WebSocket and production frontend; synthetic flash only.
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
const output = path.resolve('build/ha-send');
fs.mkdirSync(output, {recursive:true});
(async () => {
  const executablePath = process.env.HA_BROWSER_MANAGED_PLAYWRIGHT === '1' ? undefined : '/usr/bin/chromium';
  const browser = await chromium.launch({executablePath, headless:true, args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1280, height:900}}), errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    await page.addInitScript(token => { window.testCredentials = token; }, process.env.HA_BROWSER_TOKEN);
    async function idle() {
      await page.waitForFunction(() => window.harness?.element._loaded && !harness.element._busy);
    }
    await page.goto(origin + '/home_panel_browser_fixture/index.html'); await idle();
    await page.locator('#panel').selectOption(process.env.HA_BROWSER_ENTRY); await idle();
    await page.locator('[data-import="active"]').click(); await idle();
    await page.locator('#edit-original').click();
    assert.equal(await page.locator('#draft-send').isDisabled(), true);
    await page.locator('#draft-model-check').click(); await idle();
    assert.equal(await page.locator('#draft-send').isDisabled(), true, 'HA-only check cannot enable sending');
    await page.locator('#draft-room-name').fill('Спальня');
    await page.locator('#draft-update-room').click();
    await page.locator('#draft-check').click(); await idle();
    assert.equal(await page.locator('#draft-send').isEnabled(), true);
    await page.locator('#draft-room-name').fill('Детская');
    assert.equal(await page.locator('#draft-send').isDisabled(), true, 'Pending fields block Send');
    await page.locator('#draft-update-room').click();
    assert.equal(await page.locator('#draft-send').isDisabled(), true, 'Edited draft needs another check');
    await page.locator('#draft-check').click(); await idle();
    await page.locator('#draft-save-ha').click(); await idle();
    assert.equal(await page.evaluate(() => harness.calls.filter(c => c.type.endsWith('/send')).length), 0, 'Save in HA never sends');
    assert.equal(await page.locator('#draft-send').isEnabled(), true);
    for (const language of ['en', 'ru']) for (const dark of [false, true]) for (const width of [320, 1280]) {
      await page.evaluate(({language, dark}) => { harness.hass.locale.language = language; harness.theme(dark); harness.update(); }, {language, dark});
      await page.setViewportSize({width, height:900});
      assert.deepEqual(await page.evaluate(() => [...harness.element.$('draft-editor').shadowRoot.querySelectorAll('.draft-toolbar, button')]
        .filter(n => n.getClientRects().length && n.scrollWidth > n.clientWidth + 1).map(n => n.id)), [], 'No toolbar/button overflow');
      if (process.env.HA_SEND_LOST !== '1') await page.screenshot({path:path.join(output, `send-${language}-${dark ? 'dark' : 'light'}-${width}.png`), fullPage:true});
    }
    const before = await page.evaluate(() => harness.calls.length);
    page.once('dialog', dialog => dialog.dismiss());
    await page.locator('#draft-send').click(); await idle();
    assert.equal(await page.evaluate(() => harness.calls.length), before, 'Cancel sends nothing');
    if (process.env.HA_SEND_LOST === '1') await page.evaluate(() => harness.faults.push({lost:true}));
    page.once('dialog', dialog => dialog.accept());
    await page.locator('#draft-send').click(); await idle();
    assert.equal(await page.evaluate(() => harness.calls.filter(c => c.type.endsWith('/send')).length), 1);
    assert.equal(await page.locator('#draft-send').isDisabled(), true, 'No write replay');
    if (process.env.HA_SEND_LOST === '1') {
      assert.match(await page.locator('#message').textContent(), /Нет соединения/);
      await page.locator('#refresh').click(); await idle();
      assert.equal(await page.locator('#draft-send').isDisabled(), true, 'Refresh alone cannot rebind a consumed import');
    } else {
      assert.match(await page.locator('#draft-send-status').textContent(), /Кандидат сохранён, не применён/);
      const results = await page.evaluate(() => harness.results);
      assert.equal(results['home_panel/config/validate/'].candidate_document,
        await page.evaluate(() => harness.calls.findLast(c => c.type.endsWith('/send')).document));
      assert.equal(results['home_panel/config/send/'].candidate.applied, false);
      await page.locator('#draft-room-name').fill('Новые правки');
      assert.equal(await page.locator('#draft-send-status').isHidden(), true, 'Pending fields are not the saved candidate');
      await page.locator('#draft-update-room').click();
      assert.equal(await page.locator('#draft-send-status').isHidden(), true, 'Old receipt does not certify edited draft');
      assert.equal(await page.locator('#draft-send').isDisabled(), true);
    }
    await page.waitForTimeout(150);
    assert.equal(await page.evaluate(() => harness.calls.filter(c => c.type.endsWith('/send')).length), 1);
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
