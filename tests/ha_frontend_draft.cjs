// Called with the same real HA browser session as read/check acceptance.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
module.exports = async function testDraft(page, output, original) {
  async function until(predicate) {
    for (let i = 0; i < 200; i++) { if (await page.evaluate(predicate)) return; await page.waitForTimeout(30); }
    throw new Error('Draft state timed out: ' + predicate);
  }
  const doc = () => page.evaluate(() => harness.element.$('draft-editor').document);
  await page.evaluate(() => { harness.hass.states = {
    'scene.evening':{entity_id:'scene.evening', attributes:{friendly_name:'Вечер'}},
    'script.good_night':{entity_id:'script.good_night', attributes:{friendly_name:'Ночь'}},
    'light.demo':{entity_id:'light.demo', attributes:{friendly_name:'Not an action'}},
  }; harness.update(); });
  const before = await page.evaluate(() => harness.calls.length);
  await page.locator('#edit-original').click();
  await page.locator('#draft-work').waitFor();
  assert.equal((await doc()).revision, 33);
  await page.locator('#draft-room-name').fill('Детская вечером');
  assert.equal(await page.locator('#draft-export').isDisabled(), true, 'Pending fields block export');
  await page.evaluate(() => harness.update());
  assert.equal(await page.locator('#draft-room-name').inputValue(), 'Детская вечером', 'HA updates preserve fields');
  await page.locator('#draft-update-room').click();
  assert.equal((await doc()).rooms[0].name, 'Детская вечером');
  const initialIds = (await doc()).rooms.map(r => r.id);
  await page.locator('#draft-add-room').click();
  await page.locator('#draft-room-name').fill('Вечер');
  await page.locator('#draft-room-kind').selectOption('actions');
  await page.locator('#draft-update-room').click();
  const addedRoom = (await doc()).rooms.at(-1).id;
  await page.locator('#draft-room-up').click();
  assert.equal((await doc()).rooms[2].id, addedRoom);
  await page.locator('#draft-room-down').click();
  assert.deepEqual((await doc()).rooms.slice(0, 3).map(r => r.id), initialIds);
  await page.locator('#draft-add-action').click();
  assert.equal(await page.locator('#draft-entities option').count(), 2, 'Only allowlisted action domains');
  await page.locator('#draft-entity').fill('scene.evening');
  await page.locator('#draft-entity').press('Tab');
  assert.equal(await page.locator('#draft-action-name').inputValue(), 'Вечер');
  assert.equal(await page.locator('#draft-stop-field').isVisible(), false, 'Scenes have no Stop');
  await page.locator('#draft-icon').selectOption('moon');
  await page.locator('#draft-interaction').selectOption('confirm');
  await page.locator('#draft-update-action').click();
  let draft = await doc();
  const widgetId = draft.rooms.at(-1).widgets[0].id;
  assert.equal(draft.rooms.at(-1).widgets[0].settings.entity, 'scene.evening');
  await page.locator(`[data-widget-id="${widgetId}"] .draft-widget-main`).click();
  await page.locator('#draft-target').selectOption('room');
  await page.locator('#draft-update-action').click();
  draft = await doc();
  assert.equal(draft.rooms[0].widgets[0].id, widgetId, 'Moving actions preserves identity');
  assert.equal(draft.rooms.at(-1).widgets.length, 0);
  assert.equal(await page.locator('#document').textContent(), original, 'Original stays exact');
  assert.equal(await page.evaluate(() => harness.calls.length), before, 'Edits make no WS/device requests');
  await page.locator('#draft-model-check').click();
  await until(() => !harness.element._busy);
  assert.match(await page.locator('#draft-model-status').textContent(), /HA model: Valid model/);
  assert.equal(await page.evaluate(() => harness.calls.at(-1).type), 'home_panel/config/model_check');
  const modelReport = await page.evaluate(() => harness.element.$('draft-editor')._modelValidation);
  assert.equal(modelReport.device_checked, false); assert.equal(modelReport.deployment_ready, false);
  // Bad UTF-8 byte length is rejected atomically, then corrected in place.
  await page.locator('#draft-room-name').fill('\u042f'.repeat(129));
  await page.locator('#draft-update-room').click();
  assert.match(await page.locator('#draft-model-status').textContent(), /Previous validation/);
  assert.equal((await doc()).rooms[0].name, 'Детская вечером');
  assert.equal(await page.locator('#draft-error').isVisible(), true);
  await page.locator('#draft-room-name').fill('Детская вечером');
  await page.locator('#draft-update-room').click();
  const downloadEvent = page.waitForEvent('download');
  await page.locator('#draft-export').click();
  await (await downloadEvent).saveAs(path.join(output, 'draft.json'));
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(output, 'draft.json'))), await doc());
  await page.locator('#draft-check').click();
  await until(() => !harness.element._busy);
  assert.match(await page.locator('#draft-status').textContent(), /Valid model/);
  const last = await page.evaluate(() => harness.calls.at(-1));
  assert.equal(last.type, 'home_panel/config/validate');
  assert.deepEqual(JSON.parse(last.document), await doc());
  await page.locator('#refresh').click();
  await until(() => !harness.element._busy);
  assert.match(await page.locator('#draft-status').textContent(), /Previous validation/);
  for (const language of ['en', 'ru']) {
    await page.evaluate(language => { harness.hass.locale.language = language; harness.update(); }, language);
    for (const dark of [false, true]) {
      await page.evaluate(dark => harness.theme(dark), dark);
      for (const width of [1280, 390, 320]) {
        await page.setViewportSize({width, height:width > 700 ? 900 : 844});
        await page.locator('#draft-room-form').scrollIntoViewIfNeeded();
        assert.deepEqual(await page.evaluate(() => {
          const e = harness.element.$('draft-editor');
          return [...e.shadowRoot.querySelectorAll('.draft-toolbar, .draft-fields, .draft-widget, button')]
            .filter(n => n.getClientRects().length && n.scrollWidth > n.clientWidth + 1).map(n => n.id || n.className);
        }), [], `Draft overflow ${language} ${dark} ${width}`);
        await page.screenshot({path:path.join(output, `draft-${language}-${dark ? 'dark' : 'light'}-${width}.png`), fullPage:true});
      }
    }
  }
  await page.setViewportSize({width:1280, height:900});
  await page.evaluate(() => { harness.hass.locale.language = 'en'; harness.theme(false); harness.update(); });
  await require('./ha_frontend_persistence.cjs')(page, output, original);
  await page.locator('#tab-original').click();
};
