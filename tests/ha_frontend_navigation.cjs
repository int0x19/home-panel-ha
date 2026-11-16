// Real browser History/Navigation APIs and production custom element; no router patches.
const assert = require('node:assert/strict');

module.exports = async function navigationAcceptance(browser, origin, token, entry) {
  const context = await browser.newContext({viewport:{width:390, height:844}});
  const page = await context.newPage(), errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(token => {
    window.testCredentials = token;
    window.finishedNavigations = 0;
    for (const type of ['navigatesuccess', 'navigateerror']) navigation.addEventListener(type, () => window.finishedNavigations++);
  }, token);
  async function ready() {
    await page.waitForFunction(() => window.harness?.element._loaded && !harness.element._busy);
  }
  async function prompt(action, accept = false, kind = 'confirm') {
    const finished = await page.evaluate(() => window.finishedNavigations);
    const received = page.waitForEvent('dialog');
    const operation = action().catch(error => { if (kind !== 'beforeunload') throw error; });
    const dialog = await received;
    assert.equal(dialog.type(), kind);
    if (kind === 'confirm') assert.match(dialog.message(), /unsaved|несохран/);
    await (accept ? dialog.accept() : dialog.dismiss());
    await operation;
    if (kind === 'confirm') await page.waitForFunction(count => window.finishedNavigations > count, finished);
  }
  async function urlPath() { return new URL(page.url()).pathname; }
  async function traverse(method) {
    await page.evaluate(method => {
      let button = document.getElementById('history-step');
      if (!button) {
        button = document.createElement('button'); button.id = 'history-step'; button.textContent = 'History';
        button.style.cssText = 'position:fixed;top:0;right:0;z-index:9999'; document.body.append(button);
      }
      button.onclick = () => history[method]();
    }, method);
    await page.locator('#history-step').click();
  }
  const fixture = '/home_panel_browser_fixture/index.html';
  try {
    await page.goto(origin + fixture); await ready();
    await page.locator('#panel').selectOption(entry); await ready();
    await page.locator('[data-import="active"]').click(); await ready();
    await page.locator('#edit-original').click();
    assert.equal(await page.evaluate(() => harness.element.$('draft-editor').dirty), true);
    const original = await page.evaluate(() => harness.element.$('draft-editor').document);
    const calls = await page.evaluate(() => harness.calls.length);

    // Canceled push/replace preserve URL, history payload, model and WS traffic.
    for (const method of ['pushState', 'replaceState']) {
      const before = await page.evaluate(() => ({state:history.state, length:history.length}));
      await prompt(() => page.evaluate(method => history[method]({sentinel:method}, '', '/config'), method));
      assert.equal(await urlPath(), fixture);
      assert.deepEqual(await page.evaluate(() => ({state:history.state, length:history.length})), before);
    }
    assert.deepEqual(await page.evaluate(() => harness.element.$('draft-editor').document), original);
    assert.equal(await page.evaluate(() => harness.calls.length), calls);

    // HA dialog/query history and tabs retain the mounted editor and do not prompt.
    await page.evaluate(() => history.pushState({dialog:'test'}, '', location.pathname + '?dialog=test#more-info'));
    await page.locator('#tab-check').click();
    await page.locator('#input').fill('uncommitted JSON');
    await prompt(() => page.locator('[data-title="settings"]').click(), false, 'beforeunload');
    assert.equal(await page.locator('#input').inputValue(), 'uncommitted JSON');

    // Both Back and Forward cancellation keep the history cursor at the editor.
    await prompt(() => page.evaluate(() => history.pushState({from:'editor'}, '', '/other')), true);
    await page.evaluate(fixture => history.pushState({from:'/other'}, '', fixture), fixture);
    await prompt(() => traverse('back'));
    assert.equal(await urlPath(), fixture);
    await prompt(() => traverse('back'), true);
    await page.waitForURL(origin + '/other');
    await traverse('forward');
    await page.waitForURL(origin + fixture);
    await prompt(() => page.evaluate(() => history.pushState({from:'editor'}, '', '/future')), true);
    await traverse('back');
    await page.waitForURL(origin + fixture);
    await prompt(() => traverse('forward'));
    assert.equal(await urlPath(), fixture);

    // A real reload retains the page after dismissal; no auto checkpoint is written.
    await prompt(() => page.reload(), false, 'beforeunload');
    assert.equal(await page.locator('#input').inputValue(), 'uncommitted JSON');
    assert.equal(await page.evaluate(() => harness.calls.length), calls);
    await page.evaluate(() => { harness.element.$('input').value = ''; harness.element.$('input').dispatchEvent(new Event('input')); });
    await page.locator('#tab-editor').click();
    await page.locator('#draft-save-ha').click(); await ready();
    assert.equal(await page.evaluate(() => harness.element.$('draft-editor').dirty), false);
    await page.evaluate(() => history.pushState({saved:true}, '', '/saved-checkpoint'));
    assert.equal(await urlPath(), '/saved-checkpoint');
    await page.evaluate(fixture => history.replaceState({}, '', fixture), fixture);

    // Uncommitted form fields remain protected even when the model was checkpointed.
    await page.locator('#draft-room-name').fill('Uncommitted room');
    await prompt(() => page.evaluate(() => history.pushState({}, '', '/config')));
    assert.equal(await page.locator('#draft-room-name').inputValue(), 'Uncommitted room');

    // Offline edits are still protected. Privilege loss and detach release guards.
    await page.evaluate(() => harness.close());
    await prompt(() => page.evaluate(() => history.replaceState({}, '', '/offline')));
    await page.evaluate(() => { harness.hass.user.is_admin = false; harness.update(); });
    await page.evaluate(() => history.pushState({}, '', '/signed-out'));
    assert.equal(await urlPath(), '/signed-out');
    await page.evaluate(() => { harness.element.remove(); history.pushState({}, '', '/detached'); });
    assert.equal(await urlPath(), '/detached');
    assert.deepEqual(errors, []);
  } finally { await context.close(); }

  // No Navigation API: link interception and unload work; expose the history limitation.
  const fallback = await browser.newContext();
  const old = await fallback.newPage();
  try {
    await old.addInitScript(token => {
      window.testCredentials = token;
      Object.defineProperty(window, 'navigation', {value:undefined, configurable:true});
    }, token);
    await old.goto(origin + fixture);
    await old.waitForFunction(() => window.harness?.element._loaded && !harness.element._busy);
    await old.locator('#tab-check').click();
    await old.locator('#input').fill('keep me');
    assert.equal(await old.locator('#navigation-warning').isVisible(), true);
    const event = old.waitForEvent('dialog');
    const click = old.locator('[data-title="settings"]').click();
    await (await event).dismiss(); await click;
    assert.equal(new URL(old.url()).pathname, fixture);
    assert.equal(await old.locator('#input').inputValue(), 'keep me');
    await old.evaluate(() => harness.element.remove());
    await old.evaluate(() => history.pushState({}, '', '/fallback-detached'));
    assert.equal(new URL(old.url()).pathname, '/fallback-detached');
    await old.evaluate(() => harness.close());
  } finally { await fallback.close(); }
};
