// Summary is read-only display metadata, independent of validation/storage.
const assert = require('node:assert/strict');
const path = require('node:path');
module.exports = async function testChanges(page, output) {
  const idle = () => page.waitForFunction(() => !harness.element._busy);
  const model = await page.evaluate(() => harness.element.$('draft-editor').document);
  const state = await page.evaluate(() => [harness.element._fresh, harness.element.$('draft-editor')._storeFresh]);
  const revision = await page.evaluate(() => harness.element.$('draft-editor')._storeRevision);
  await page.locator('#draft-changes').click(); await idle();
  const report = await page.evaluate(() => harness.element.$('draft-editor')._changes);
  assert.equal(report.scope, 'ha_structural_changes');
  assert.equal(report.counts.room_added, 1); assert.equal(report.counts.widget_added, 1);
  assert.equal(report.model_validated, false); assert.equal(report.device_checked, false);
  assert.equal(report.deployment_ready, false);
  assert.deepEqual(await page.evaluate(() => harness.element.$('draft-editor').document), model);
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor')._storeRevision), revision);
  assert.deepEqual(await page.evaluate(() => [harness.element._fresh, harness.element.$('draft-editor')._storeFresh]), state);
  assert.equal(await page.locator('#draft-compare-base option[value=saved]').evaluate(option => option.disabled), true);
  assert.match(await page.locator('#draft-change-status').textContent(), /Total:/);
  assert.match(await page.locator('#draft-change-items').textContent(), /Widget added/);
  for (const language of ['en', 'ru']) {
    await page.evaluate(language => { harness.hass.locale.language = language; harness.update(); }, language);
    assert.match(await page.locator('#draft-change-items').textContent(), language === 'ru' ? /Виджет добавлен/ : /Widget added/);
    for (const dark of [false, true]) {
      await page.evaluate(dark => harness.theme(dark), dark);
      for (const width of [1280, 390, 320]) {
        await page.setViewportSize({width, height:width > 700 ? 900 : 844});
        await page.locator('#draft-change-details').scrollIntoViewIfNeeded();
        assert.deepEqual(await page.evaluate(() => {
          const root = harness.element.$('draft-editor');
          return [...root.shadowRoot.querySelectorAll('#draft-change-details, #draft-change-tools, #draft-change-items, #draft-change-items li, button')]
            .filter(n => n.getClientRects().length && n.scrollWidth > n.clientWidth + 1).map(n => n.id || n.className);
        }), [], `Changes overflow ${language} ${dark} ${width}`);
        await page.screenshot({path:path.join(output, `changes-${language}-${dark ? 'dark' : 'light'}-${width}.png`)});
      }
    }
  }
  await page.evaluate(() => { harness.hass.locale.language = 'en'; harness.theme(false); harness.update(); });
  await page.setViewportSize({width:1280, height:900});
  await page.locator('#draft-room-name').fill('Pending');
  assert.equal(await page.locator('#draft-changes').isDisabled(), true);
  assert.match(await page.locator('#draft-change-status').textContent(), /Previous comparison/);
  await page.locator('#draft-cancel-room').click();
  assert.doesNotMatch(await page.locator('#draft-change-status').textContent(), /Previous comparison/);
  await page.evaluate(() => harness.faults.push({error:'model_check_busy'}));
  await page.locator('#draft-changes').click(); await idle();
  assert.match(await page.locator('#draft-change-status').textContent(), /Comparison unavailable/);
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor')._storeRevision), revision);
  assert.deepEqual(await page.evaluate(() => [harness.element._fresh, harness.element.$('draft-editor')._storeFresh]), state);
  await page.locator('#draft-changes').click(); await idle();
  // A stale callback cannot replace the comparison for this local model.
  assert.equal(await page.evaluate(() => {
    const draft = harness.element.$('draft-editor'), report = draft._changes;
    draft.acceptChanges({total:999}, {version:draft.version - 1, base:draft._origin.document, target:'original'});
    return draft._changes === report;
  }), true);
  assert.deepEqual(await page.evaluate(() => harness.element.$('draft-editor').document), model);
};
