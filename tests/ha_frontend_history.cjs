// Real HA Store history, explicit unsaved restoration, no device deployment.
const assert = require('node:assert/strict');
const path = require('node:path');
module.exports = async function testHistory(page, second, output, firstSaved) {
  await page.bringToFront();
  const idle = p => p.waitForFunction(() => !harness.element._busy);
  const current = p => p.evaluate(() => harness.element.$('draft-editor').document);
  const before = await current(page);
  const token = await page.evaluate(() => harness.element.$('draft-editor')._storeRevision);
  const writes = await page.evaluate(() => harness.calls.filter(c => c.type.endsWith('/draft_save')).length);
  if (!await page.locator('#draft-history').evaluate(details => details.open)) await page.locator('#draft-history summary').click();
  assert.equal(await page.locator('.draft-history-row').count(), 2);
  for (const language of ['en', 'ru']) {
    await page.evaluate(language => { harness.hass.locale.language = language; harness.update(); }, language);
    for (const dark of [false, true]) {
      await page.evaluate(dark => harness.theme(dark), dark);
      for (const width of [1280, 390, 320]) {
        await page.setViewportSize({width, height:width > 700 ? 900 : 844});
        await page.locator('#draft-history').scrollIntoViewIfNeeded();
        assert.deepEqual(await page.evaluate(() => {
          const root = harness.element.$('draft-editor').$('draft-history');
          return [root, ...root.querySelectorAll('button, .draft-history-row, small, time')]
            .filter(n => n.scrollWidth > n.clientWidth + 1).map(n => n.id || n.className);
        }), [], `History overflow ${language} ${dark} ${width}`);
        await page.screenshot({path:path.join(output, `history-${language}-${dark ? 'dark' : 'light'}-${width}.png`)});
      }
    }
  }
  await page.evaluate(() => { harness.hass.locale.language = 'en'; harness.theme(false); harness.update(); });
  await page.setViewportSize({width:1280, height:900});
  const calls = await page.evaluate(() => harness.calls.length);
  page.once('dialog', d => d.dismiss());
  await page.locator('.draft-history-row[data-generation="1"] button').click();
  assert.equal(await page.evaluate(() => harness.calls.length), calls, 'Cancelled restoration makes no request');
  page.once('dialog', d => d.accept());
  await page.locator('.draft-history-row[data-generation="1"] button').click(); await idle(page);
  const restored = await current(page);
  assert.ok(restored.revision > before.revision);
  assert.deepEqual({...restored, revision:firstSaved.revision}, firstSaved, 'Only the restored model revision changes');
  assert.equal(await page.evaluate(() => harness.calls.at(-1).type), 'home_panel/config/draft_history_get');
  assert.equal(await page.evaluate(() => harness.calls.filter(c => c.type.endsWith('/draft_save')).length), writes);
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor')._storeRevision), token);
  assert.deepEqual(await page.evaluate(() => JSON.parse(harness.element.$('draft-editor')._checkpointDocument)), before);
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor').dirty), true);
  assert.match(await page.locator('#draft-storage-status').textContent(), /Unsaved/);
  assert.match(await page.locator('#draft-model-status').textContent(), /Not checked/);
  assert.match(await page.locator('#draft-status').textContent(), /Not checked/);
  assert.equal(await page.locator('#draft-save-ha').isEnabled(), true);
  // Failed local preflight must be atomic even after a valid archive read.
  assert.equal(await page.evaluate(() => {
    const draft = harness.element.$('draft-editor'), response = structuredClone(harness.results['home_panel/config/draft_history_get/']);
    response.document_high_water = 0xffffffff;
    return draft.restoreHistory(response, {version:draft.version, expected_revision:draft._storeRevision, history_generation:1});
  }), false);
  assert.deepEqual(await current(page), restored);
  assert.match(await page.locator('#draft-history-status').textContent(), /Revision limit reached/);
  await page.locator('#draft-compare-base').selectOption('saved');
  await page.locator('#draft-changes').click(); await idle(page);
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor')._changes.counts.room_changed), 1);
  await page.locator('#draft-save-ha').click(); await idle(page);
  assert.equal(await page.evaluate(() => harness.calls.filter(c => c.type.endsWith('/draft_save')).length), writes + 1);
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor').dirty), false);
  assert.equal(await page.locator('.draft-history-row').count(), 3);
  // A second browser commits after this browser observed its history list.
  await second.locator('#draft-load-ha').click(); await idle(second);
  await second.locator('#draft-room-name').fill('External latest');
  await second.locator('#draft-update-room').click();
  await second.locator('#draft-save-ha').click(); await idle(second);
  await page.locator('#draft-room-name').fill('Must survive history conflict');
  await page.locator('#draft-update-room').click();
  const local = await current(page);
  page.once('dialog', d => d.accept());
  await page.locator('.draft-history-row[data-generation="3"] button').click(); await idle(page);
  assert.deepEqual(await current(page), local);
  assert.match(await page.locator('#message').textContent(), /version conflict/);
  assert.equal(await page.locator('#draft-save-ha').isDisabled(), true);
  assert.equal(await page.locator('.draft-history-row button').first().isDisabled(), true);
  assert.equal(await page.evaluate(() => harness.element._fresh), true, 'History conflict does not invalidate device metadata');
  const reads = await page.evaluate(() => harness.calls.filter(c => c.type.endsWith('/draft_history_get')).length);
  await page.waitForTimeout(60);
  assert.equal(await page.evaluate(() => harness.calls.filter(c => c.type.endsWith('/draft_history_get')).length), reads);
  page.once('dialog', d => d.accept());
  await page.locator('#draft-load-ha').click(); await idle(page);
  assert.equal((await current(page)).rooms[0].name, 'External latest');
  // A reply from an older HA connection cannot restore over the local model.
  await page.evaluate(() => harness.faults.push({hold:true}));
  page.once('dialog', d => d.accept());
  if (!await page.locator('#draft-history').evaluate(details => details.open)) await page.locator('#draft-history summary').click();
  await page.locator('.draft-history-row[data-generation="3"] button').click();
  await page.waitForFunction(() => typeof harness.release === 'function');
  const unchanged = await current(page);
  await page.evaluate(() => { harness.hass.connection = {connected:true}; harness.update(); });
  await idle(page);
  await page.evaluate(() => { harness.release(); delete harness.release; });
  await page.waitForTimeout(30);
  assert.deepEqual(await current(page), unchanged);
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor')._restoredGeneration), null);
  await page.locator('#draft-load-ha').click(); await idle(page);
  await page.locator('#refresh').click(); await idle(page);
};
