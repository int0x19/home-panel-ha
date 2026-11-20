// Synthetic negotiated reading profile; real HA catalog/checkpoint/model WS.
// This never widens the actual firmware inventory or sends a household command.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
module.exports = async function testSensors(page, output) {
  const document = () => page.evaluate(() => harness.element.$('draft-editor').document);
  const idle = () => page.waitForFunction(() => !harness.element._busy);
  await page.locator('#tab-editor').click();
  await page.evaluate(() => {
    const parent = harness.element, draft = parent.$('draft-editor');
    parent._sensorOriginalCaps = structuredClone(parent._status.capabilities);
    draft.begin(parent._original, parent._status.capabilities, 40);
  });
  assert.equal(await page.locator('#draft-add-sensor').isDisabled(), true, 'Action-only firmware must stay gated');
  assert.equal(await page.locator('#draft-add-status').isHidden(), true, 'Action-only firmware cannot edit binary sensors');
  await page.evaluate(() => {
    const parent = harness.element, caps = parent._status.capabilities;
    caps.features.push('widget.sensor', 'widget.status', 'sensor-groups.v1'); caps.widget_types.push('sensor', 'status');
    caps.limits.subscriptions = caps.limits.entity_bindings;
    parent._update(); parent.$('draft-editor').begin(parent._original, caps, 40);
  });
  assert.equal(await page.locator('#scope').textContent(), 'Room readings preview');
  await page.locator('#draft-room-name').fill('Спальня');
  await page.locator('#draft-update-room').click();
  const before = await page.evaluate(() => harness.calls.length);
  await page.locator('#draft-add-sensor').click();
  await page.locator('#draft-choose-sensor').click(); await idle();
  assert.ok(await page.locator('.entity-result').count() >= 2);
  assert.equal(await page.locator('.entity-result').evaluateAll(items => items.every(item => item.dataset.entity.startsWith('sensor.'))), true, 'Sensor catalog excludes action families');
  await page.locator('[data-entity="sensor.bedroom_temperature"]').click();
  assert.equal(await page.locator('#draft-sensor-unit').inputValue(), '°C');
  assert.equal(await page.locator('#draft-sensor-class').inputValue(), 'temperature');
  await page.locator('#draft-sensor-name').fill('Температура');
  await page.locator('#draft-sensor-group').selectOption('@new');
  await page.locator('#draft-group-name').fill('Комната');
  assert.equal(await page.locator('#draft-save-ha').isDisabled(), true, 'Pending binding cannot be saved');
  await page.evaluate(() => harness.update());
  assert.equal(await page.locator('#draft-group-name').inputValue(), 'Комната', 'HA updates preserve fields');
  await page.locator('#draft-update-sensor').click();
  let draft = await document();
  const first = draft.rooms[0].widgets[0], group = first.settings.group;
  assert.equal(first.settings.entity, 'sensor.bedroom_temperature');
  assert.deepEqual(draft.rooms[0].groups, {[group]:{name:'Комната'}});
  await page.locator('#draft-add-sensor').click();
  await page.locator('#draft-choose-sensor').click(); await idle();
  await page.locator('[data-entity="sensor.bedroom_humidity"]').click();
  assert.equal(await page.locator('#draft-sensor-unit').inputValue(), '%', 'Unavailable sensor retains metadata');
  await page.locator('#draft-sensor-name').fill('Влажность');
  await page.locator('#draft-sensor-group').selectOption(group);
  await page.locator('#draft-update-sensor').click();
  assert.match(await page.locator('#draft-fit').textContent(), /^40 \/ 390 px$/);
  assert.equal(await page.locator('#draft-room-kind option[value="actions"]').evaluate(option => option.disabled), true);
  assert.equal(await page.evaluate(() => harness.calls.slice(-2).every(c => c.type.endsWith('/entities'))), true);
  assert.equal(await page.evaluate(() => harness.calls.length), before + 2, 'Local edits use no device requests');
  await page.locator('#draft-add-action').click();
  await page.locator('#draft-action-name').fill('Вечер');
  await page.locator('#draft-entity').fill('scene.evening');
  await page.locator('#draft-update-action').click();
  assert.match(await page.locator('#draft-fit').textContent(), /^126 \/ 390 px$/, 'Mixed room shares the existing row planner');
  await page.locator(`[data-widget-id="${first.id}"] .draft-widget-main`).click();
  await page.locator('#draft-sensor-name').fill('Моя температура');
  await page.locator('#draft-group-name').fill('');
  await page.locator('#draft-update-sensor').click();
  draft = await document();
  assert.equal(draft.rooms[0].widgets[0].id, first.id, 'Edits preserve placement identity');
  assert.deepEqual(draft.rooms[0].groups[group], {}, 'Empty common name retains unnamed grouping');
  fs.writeFileSync(path.join(output, 'sensor-draft.json'), JSON.stringify(draft));
  await page.locator('#draft-add-status').click();
  assert.equal(await page.locator('#draft-sensor-unit').isHidden(), true);
  assert.equal(await page.locator('#draft-sensor-group').isHidden(), true);
  await page.locator('#draft-choose-sensor').click(); await idle();
  assert.equal(await page.locator('.entity-result').evaluateAll(items =>
    items.every(item => item.dataset.entity.startsWith('binary_sensor.'))), true);
  await page.locator('[data-entity="binary_sensor.plug_problem"]').click();
  assert.equal(await page.locator('#draft-sensor-class').inputValue(), 'problem');
  await page.locator('#draft-update-sensor').click();
  draft = await document();
  const status = draft.rooms[0].widgets.at(-1);
  assert.equal(status.type, 'status');
  assert.deepEqual(status.settings, {name:'Plug fault', entity:'binary_sensor.plug_problem', device_class:'problem'});
  assert.ok(draft.requires.includes('widget.status'));
  assert.match(await page.locator('#draft-fit').textContent(), /^206 \/ 390 px$/);
  await page.locator(`[data-widget-id="${status.id}"] .draft-widget-main`).click();
  await page.locator('#draft-sensor-name').fill('Outlet fault');
  await page.locator('#draft-update-sensor').click();
  draft = await document();
  assert.equal(draft.rooms[0].widgets.at(-1).id, status.id, 'Status title edits keep the placement ID');
  await page.locator('#draft-model-check').click(); await idle();
  assert.match(await page.locator('#draft-model-status').textContent(), /Valid model/);
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor')._modelValidation.deployment_ready), false);
  await page.locator('#draft-save-ha').click(); await idle();
  await page.locator('#draft-load-ha').click(); await idle();
  assert.deepEqual(await document(), draft, 'Sensor settings survive HA checkpoint restore');
  fs.writeFileSync(path.join(output, 'status-draft.json'), JSON.stringify(draft));
  for (const language of ['en', 'ru']) {
    await page.evaluate(language => { harness.hass.locale.language = language; harness.update(); }, language);
    for (const dark of [false, true]) {
      await page.evaluate(dark => harness.theme(dark), dark);
      for (const width of [1280, 390, 320]) {
        await page.setViewportSize({width, height:width > 700 ? 900 : 844});
        await page.locator(`[data-widget-id="${first.id}"] .draft-widget-main`).click();
        assert.deepEqual(await page.evaluate(() => {
          const root = harness.element.$('draft-editor').shadowRoot;
          return [...root.querySelectorAll('.draft-toolbar, .draft-fields, .draft-widget, button, input, select')]
            .filter(n => n.getClientRects().length && n.scrollWidth > n.clientWidth + 1).map(n => n.id || n.className);
        }), [], `Sensor form overflow ${language} ${dark} ${width}`);
        await page.screenshot({path:path.join(output, `sensors-${language}-${dark ? 'dark' : 'light'}-${width}.png`), fullPage:true});
        await page.locator('#draft-cancel-sensor').click();
      }
    }
  }
  page.once('dialog', dialog => dialog.accept());
  await page.locator('#draft-delete-ha').click(); await idle();
  await page.evaluate(() => {
    const parent = harness.element;
    parent.$('draft-editor').clear(); parent._status.capabilities = parent._sensorOriginalCaps;
    delete parent._sensorOriginalCaps; harness.hass.locale.language = 'en'; harness.theme(false); harness.update();
  });
  await page.setViewportSize({width:1280, height:900});
};
