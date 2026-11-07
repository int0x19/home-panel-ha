const assert = require('node:assert/strict');
const path = require('node:path');
module.exports = async function testPersistence(page, output, original) {
  async function until(p, predicate) {
    for (let i = 0; i < 300; i++) { if (await p.evaluate(predicate)) return; await p.waitForTimeout(30); }
    throw new Error('HA draft persistence timed out: ' + predicate);
  }
  const idle = p => until(p, () => !harness.element._busy);
  const current = p => p.evaluate(() => harness.element.$('draft-editor').document);
  assert.equal(await page.locator('#draft-save-ha').isEnabled(), true);
  await page.locator('#draft-save-ha').click(); await idle(page);
  const saved = await current(page);
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor').dirty), false);
  assert.match(await page.locator('#draft-storage-status').textContent(), /Saved in HA/);
  // Internal HA navigation detaches this element without a full browser reload.
  await page.evaluate(() => { harness.element.remove(); document.body.append(harness.element); });
  await until(page, () => harness.element._loaded && !harness.element._busy);
  await page.locator('#panel').selectOption(process.env.HA_BROWSER_ENTRY);
  await until(page, () => !!harness.element.$('draft-editor').document && !harness.element._busy);
  assert.deepEqual(await current(page), saved);
  assert.equal(await page.locator('#document').textContent(), original);
  assert.equal(await page.locator('#input').inputValue(), '', 'Raw-check input is not a persisted draft');
  assert.match(await page.locator('#draft-status').textContent(), /Not checked/, 'Saved does not mean validated');
  assert.equal(await page.evaluate(() => harness.calls.at(-1).type), 'home_panel/config/draft_get', 'Restore does not wait for device I/O');
  assert.equal(await page.locator('#draft-check').isDisabled(), true);
  assert.equal(await page.locator('#draft-model-check').isEnabled(), true, 'HA model check does not need fresh ESP32 metadata');
  await page.locator('#draft-model-check').click(); await idle(page);
  assert.match(await page.locator('#draft-model-status').textContent(), /HA model: Valid model/);
  assert.equal(await page.evaluate(() => harness.element._fresh), false);
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor').dirty), false);
  await page.locator('#refresh').click(); await idle(page);
  await page.evaluate(() => harness.faults.push({error:'model_check_busy'}));
  await page.locator('#draft-model-check').click(); await idle(page);
  assert.equal(await page.evaluate(() => harness.element._fresh), true, 'Host check error does not invalidate ESP32 metadata');
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor')._storeFresh), true);
  const second = await page.context().newPage();
  try {
    await second.addInitScript(token => { window.testCredentials = token; }, process.env.HA_BROWSER_TOKEN);
    await second.goto(page.url(), {waitUntil:'domcontentloaded'});
    await until(second, () => window.harness?.element._loaded && !harness.element._busy);
    await second.locator('#panel').selectOption(process.env.HA_BROWSER_ENTRY);
    await until(second, () => !!harness.element.$('draft-editor').document && !harness.element._busy);
    assert.deepEqual(await current(second), saved);
    await page.locator('#draft-room-name').fill('Editor A');
    await page.locator('#draft-update-room').click();
    await page.locator('#draft-save-ha').click(); await idle(page);
    await second.locator('#draft-room-name').fill('Editor B');
    await second.locator('#draft-update-room').click();
    await second.locator('#draft-save-ha').click(); await idle(second);
    assert.equal((await current(second)).rooms[0].name, 'Editor B');
    assert.match(await second.locator('#message').textContent(), /version conflict/);
    assert.equal(await second.locator('#draft-save-ha').isDisabled(), true);
    await second.setViewportSize({width:390, height:844});
    await second.locator('#draft-storage-status').scrollIntoViewIfNeeded();
    await second.screenshot({path:path.join(output, 'draft-conflict-390.png'), fullPage:true});
    second.once('dialog', d => d.accept());
    await second.locator('#draft-load-ha').click(); await idle(second);
    assert.equal((await current(second)).rooms[0].name, 'Editor A');
    // The real save commits on HA disk, then our test adapter loses the reply.
    await page.locator('#draft-room-name').fill('Saved despite lost reply');
    await page.locator('#draft-update-room').click();
    await page.evaluate(() => harness.faults.push({lost:true}));
    await page.locator('#draft-save-ha').click(); await idle(page);
    assert.equal(await page.locator('#draft-save-ha').isDisabled(), true);
    assert.equal(await page.evaluate(() => harness.element.$('draft-editor').dirty), true);
    assert.equal(await page.evaluate(() => harness.element._fresh), true, 'HA storage failure does not invalidate device metadata');
    const writes = await page.evaluate(() => harness.calls.filter(c => c.type.endsWith('/draft_save')).length);
    await page.waitForTimeout(60);
    assert.equal(await page.evaluate(() => harness.calls.filter(c => c.type.endsWith('/draft_save')).length), writes);
    page.once('dialog', d => d.accept());
    await page.locator('#draft-load-ha').click(); await idle(page);
    assert.equal((await current(page)).rooms[0].name, 'Saved despite lost reply');
    assert.equal(await page.evaluate(() => harness.element.$('draft-editor').dirty), false);
    page.once('dialog', d => d.accept());
    await page.locator('#draft-delete-ha').click(); await idle(page);
    assert.equal(await current(page), null);
    assert.equal(await page.locator('#document').textContent(), original);
    await second.evaluate(() => harness.close());
  } finally { await second.close(); }
  // Restore the independent local input used by the read/check acceptance tail.
  await page.locator('#tab-check').click(); await page.locator('#input').fill('broken');
  await page.locator('#tab-original').click();
};
