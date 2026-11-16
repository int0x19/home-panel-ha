// Real HA registry catalog; choosing never commits the model or calls a service.
const assert = require('node:assert/strict');
const path = require('node:path');
module.exports = async function testEntities(page, output) {
  async function idle() {
    await page.waitForFunction(() => !harness.element._busy);
  }
  async function open() { await page.locator('#draft-choose-entity').click(); await idle(); }
  async function search(text) {
    await page.locator('#entity-query').fill(text);
    await page.locator('#entity-query').press('Enter'); await idle();
  }
  const original = await page.evaluate(() => harness.element.$('draft-editor').document);
  await open();
  assert.equal(await page.locator('.entity-result').count(), 25);
  assert.equal(await page.locator('[data-entity="scene.hidden"]').count(), 0);
  await page.locator('#entity-next').click(); await idle();
  assert.match(await page.locator('#entity-page').textContent(), /^26/);
  await page.locator('#entity-previous').click(); await idle();
  await page.locator('#entity-domain').selectOption('scene'); await idle();
  await page.locator('#entity-area').selectOption({label:'Спальня'}); await idle();
  assert.equal(await page.locator('.entity-result').count(), 1);
  await page.locator('#entity-inactive').check(); await idle();
  assert.equal(await page.locator('[data-entity="scene.hidden"]').count(), 1);
  await page.locator('#entity-inactive').uncheck(); await idle();
  await search('not_present');
  assert.equal(await page.locator('.entity-result').count(), 0);
  assert.match(await page.locator('#entity-results-status').textContent(), /No matching entities/);
  await search('ВЕЧЕР');
  assert.equal(await page.locator('.entity-result').count(), 1);
  assert.match(await page.locator('.entity-result').textContent(), /Вечер.*scene.evening.*Спальня/);
  for (const language of ['en', 'ru']) {
    await page.evaluate(language => { harness.hass.locale.language = language; harness.update(); }, language);
    assert.match(await page.locator('.entity-result').textContent(), language === 'ru' ? /Неизвестно/ : /Unknown/);
    for (const dark of [false, true]) {
      await page.evaluate(dark => harness.theme(dark), dark);
      for (const width of [1280, 390, 320]) {
        await page.setViewportSize({width, height:width > 700 ? 900 : 844});
        assert.deepEqual(await page.evaluate(() => {
          const root = harness.element.$('draft-editor').$('entity-picker');
          return [root, ...root.querySelectorAll('button, input, select, form')]
            .filter(n => n.scrollWidth > n.clientWidth + 1).map(n => n.id || n.className);
        }), [], `Catalog overflow ${language} ${dark} ${width}`);
        await page.screenshot({path:path.join(output, `entities-${language}-${dark ? 'dark' : 'light'}-${width}.png`)});
      }
    }
  }
  await page.evaluate(() => { harness.hass.locale.language = 'en'; harness.theme(false); harness.update(); });
  await page.setViewportSize({width:1280, height:900});
  await page.locator('[data-entity="scene.evening"]').click();
  assert.equal(await page.locator('#draft-action-name').inputValue(), 'Вечер');
  assert.equal(await page.locator('#draft-entity').inputValue(), 'scene.evening');
  assert.deepEqual(await page.evaluate(() => harness.element.$('draft-editor').document), original);
  await page.locator('#draft-action-name').fill('Моя подпись');
  await open(); await search('good_night');
  await page.locator('[data-entity="script.good_night"]').click();
  assert.equal(await page.locator('#draft-action-name').inputValue(), 'Моя подпись', 'Selection preserves explicit label');
  assert.equal(await page.locator('#draft-stop-field').isVisible(), true);
  // Closing while the reply is held must not repopulate/reopen the picker.
  await page.evaluate(() => harness.faults.push({hold:true}));
  await page.locator('#draft-choose-entity').click();
  await page.waitForFunction(() => typeof harness.release === 'function');
  await page.locator('#entity-cancel').click();
  await page.evaluate(() => { harness.release(); delete harness.release; }); await idle();
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor').$('entity-picker').open), false);
  assert.equal(await page.locator('#draft-entity').inputValue(), 'script.good_night');
  const freshness = await page.evaluate(() => [harness.element._fresh, harness.element.$('draft-editor')._storeFresh]);
  await page.evaluate(() => harness.faults.push({error:'cannot_connect'}));
  await open();
  assert.match(await page.locator('#entity-results-status').textContent(), /Entity search failed/);
  assert.deepEqual(await page.evaluate(() => [harness.element._fresh, harness.element.$('draft-editor')._storeFresh]), freshness);
  await search('evening');
  await page.locator('#entity-cancel').focus(); await page.keyboard.press('Escape');
  assert.equal(await page.evaluate(() => harness.element.$('draft-editor').$('entity-picker').open), false);
  // Return to the fixture's expected entity; a blank label is initialized once.
  await page.locator('#draft-action-name').fill('');
  await open(); await search('evening');
  await page.locator('[data-entity="scene.evening"]').click();
};
