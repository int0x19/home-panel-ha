// Installed HA frontend/router/sidebar/icons with real HA auth/WS; synthetic device only.
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
  const context = await browser.newContext({viewport:{width:1280,height:900}});
  const page = await context.newPage(), errors = [], posts = [], unknown = [], actions = [];
  page.on('websocket', socket => {
    const commands = new Map();
    socket.on('framesent', ({payload}) => {
      const message = JSON.parse(String(payload));
      if (message.id) commands.set(message.id, message.type);
      if (message.type === 'call_service') actions.push(message.type);
    });
    socket.on('framereceived', ({payload}) => {
      const messages = JSON.parse(String(payload));
      for (const message of Array.isArray(messages) ? messages : [messages]) {
        if (message.error?.code === 'unknown_command') unknown.push(commands.get(message.id));
      }
    });
  });
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (request.method() === 'POST') posts.push(new URL(request.url()).pathname); });
  await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
  await page.addInitScript(({origin, token}) => {
    // Only HA's own browser auth cache; these are temporary fixture credentials.
    localStorage.setItem('hassTokens', JSON.stringify({hassUrl:origin, clientId:origin + '/', access_token:token,
      refresh_token:'fixture-unused', token_type:'Bearer', expires_in:1800, expires:Date.now() + 1800000}));
    window.shellRejections = [];
    window.addEventListener('unhandledrejection', event => window.shellRejections.push({
      code:event.reason?.code, message:event.reason?.message, name:event.reason?.name}));
  }, {origin, token:process.env.HA_BROWSER_TOKEN});
  const editor = page.locator('home-panel-config');
  const idle = async () => {
    for (let attempt = 0; attempt < 400; attempt++) {
      if (await editor.evaluate(element => element._loaded && !element._busy)) return;
      await page.waitForTimeout(30);
    }
    throw new Error('Installed editor did not become idle');
  };
  async function prompt(action, accept) {
    const received = page.waitForEvent('dialog');
    const pending = action();
    const dialog = await Promise.race([received, pending.then(() => received)]);
    assert.equal(dialog.type(), 'confirm');
    assert.match(dialog.message(), /unsaved|несохран/);
    await (accept ? dialog.accept() : dialog.dismiss());
    await pending;
  }
  try {
    await page.goto(origin + '/home-panel-config', {waitUntil:'domcontentloaded'});
    await editor.waitFor({timeout:25000}); await idle();
    assert.equal(await page.locator('home-assistant').count(), 1);
    const settings = page.locator('ha-sidebar #sidebar-config');
    await settings.click(); await page.waitForURL(origin + '/config/dashboard');
    await page.locator('ha-sidebar #sidebar-panel-home-panel-config').click(); await idle();
    await editor.locator('#panel').selectOption(process.env.HA_BROWSER_ENTRY); await idle();
    await editor.locator('[data-import="active"]').click(); await idle();
    await editor.locator('#edit-original').click();
    await editor.locator('#draft-room-name').fill('Несохранённая комната');
    await prompt(() => editor.locator('[data-title="settings"]').click(), false);
    assert.equal(new URL(page.url()).pathname, '/home-panel-config');
    assert.equal(await editor.locator('#draft-room-name').inputValue(), 'Несохранённая комната');
    // Actual sidebar links are handled by HA, not the fixture router.
    await prompt(() => settings.click(), false);
    assert.equal(new URL(page.url()).pathname, '/home-panel-config');
    await prompt(() => page.evaluate(() => history.back()), false);
    assert.equal(new URL(page.url()).pathname, '/home-panel-config');
    assert.equal(await editor.locator('#draft-room-name').inputValue(), 'Несохранённая комната');
    assert.ok(await editor.locator('ha-icon').count() > 0);
    await page.screenshot({path:path.join(output, 'shell-dirty-desktop.png'), fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({path:path.join(output, 'shell-dirty-mobile.png'), fullPage:true});
    await page.setViewportSize({width:1280,height:900});
    await prompt(() => settings.click(), true);
    await page.waitForURL(origin + '/config/dashboard');
    await editor.waitFor({state:'detached'});
    // Returning mounts a clean component; accepted discard did not save fields.
    await page.locator('ha-sidebar #sidebar-panel-home-panel-config').click();
    await idle();
    assert.equal(await editor.locator('#panel').inputValue(), '');
    await editor.locator('#panel').selectOption(process.env.HA_BROWSER_ENTRY); await idle();
    assert.equal(await editor.locator('#draft-work').isVisible(), false);
    await page.locator('ha-sidebar #sidebar-config').click();
    await page.waitForURL(origin + '/config/dashboard');
    assert.deepEqual(errors, []);
    assert.deepEqual(unknown, [], 'The installed HA shell has its real standard APIs');
    assert.deepEqual(posts, [], 'Editor navigation never posts to device or HA services');
    assert.deepEqual(actions, [], 'No HA service calls');
    console.log('Installed HA shell acceptance passed: actual router/sidebar/icons, dirty cancellation and discard, mobile/desktop.');
  } catch (error) {
    await page.screenshot({path:path.join(output, 'shell-failure.png'), fullPage:true});
    console.error('Shell location:', page.url(), 'Errors:', errors, 'Unknown commands:', unknown, 'Rejections:', await page.evaluate(() => window.shellRejections));
    if (await editor.count()) console.error('Editor state:', await editor.evaluate(e => ({loaded:e._loaded, busy:e._busy, attempted:e._attempted, admin:e._admin, error:e._errorCode, entries:e._entries.length})));
    throw error;
  } finally { await context.close(); await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
