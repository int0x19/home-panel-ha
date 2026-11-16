// Local visual fixture only: no HA credentials, validator, network jobs or writes.
import "/home_panel_static/home-panel.js";

const data = await (await fetch("/preview.json")).json();
const prefix = "home_panel/config/";
const element = document.querySelector("home-panel-config");
const panels = structuredClone(data[prefix + "panels/"]);
panels.panels = panels.panels.filter(entry => entry.state === "loaded");
let archives = [];
let checkpoint = {version:1, generation:0, revision:'fixture:0', record:null, history:[], document_high_water:0,
  history_limits:{entries:3}, model_validated:false, deployment_ready:false};
element.hass = {
  user: {id: "visual-fixture", is_admin: true},
  locale: {language: "ru"}, connection: {connected: true},
  async callWS(command) {
    if (command.type === prefix + "panels") return structuredClone(panels);
    if (command.type === prefix + 'entities') {
      const catalog = structuredClone(data[prefix + 'entities/']);
      if (!catalog) throw {code:'not_found'};
      const needle = (command.query || '').trim().toLowerCase();
      const items = catalog.items.filter(item => (!command.domain || item.domain === command.domain) &&
        (!command.area_id && command.area_id !== null || item.area_id === command.area_id) &&
        (command.include_inactive || !item.disabled && !item.hidden) &&
        (!needle || (item.entity_id + ' ' + item.name).toLowerCase().includes(needle)));
      const offset = command.offset || 0, limit = command.limit || 25;
      return {...catalog, items:items.slice(offset, offset + limit), total:items.length, offset,
        next_offset:offset + limit < items.length ? offset + limit : null};
    }
    if ([prefix + "validate", prefix + "model_check", prefix + "model_changes"].includes(command.type)) throw {code: "panel_unavailable"};
    if (command.type === prefix + 'draft_get') return structuredClone(checkpoint);
    if (command.type === prefix + 'draft_history_get') {
      if (command.expected_revision !== checkpoint.revision) throw {code:'draft_conflict'};
      const item = archives.find(item => item.generation === command.history_generation);
      if (!item) throw {code:'draft_history_missing'};
      return {version:1, generation:checkpoint.generation, revision:checkpoint.revision,
        history_generation:item.generation, saved_at:item.saved_at, record:structuredClone(item.record),
        document_high_water:checkpoint.document_high_water, model_validated:false, deployment_ready:false};
    }
    if ([prefix + 'draft_save', prefix + 'draft_delete'].includes(command.type)) {
      if (command.expected_revision !== checkpoint.revision) throw {code:'draft_conflict'};
      let record = null;
      if (command.type.endsWith('draft_save')) {
        const document = JSON.stringify(JSON.parse(command.document));
        const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(document));
        const sha256 = [...new Uint8Array(bytes)].map(b => b.toString(16).padStart(2, '0')).join('');
        record = {document, sha256, original:structuredClone(command.original), capabilities:structuredClone(command.capabilities)};
      }
      const generation = checkpoint.generation + 1;
      if (record && checkpoint.record) archives.unshift({generation:checkpoint.generation, saved_at:checkpoint.saved_at, record:structuredClone(checkpoint.record)});
      archives = record ? archives.slice(0, 3) : [];
      const history = archives.map(item => ({generation:item.generation, saved_at:item.saved_at,
        document_revision:JSON.parse(item.record.document).revision, sha256:item.record.sha256,
        bytes:new TextEncoder().encode(item.record.document).length}));
      checkpoint = {...checkpoint, generation, revision:'fixture:' + generation, record, history, saved_at:record ? Date.now() : null,
        document_high_water:Math.max(checkpoint.document_high_water, record ? JSON.parse(record.document).revision : 0)};
      return structuredClone(checkpoint);
    }
    const result = data[command.type + "/" + (command.source || "")];
    if (!result) throw {code: "not_found"};
    return structuredClone(result);
  },
};
