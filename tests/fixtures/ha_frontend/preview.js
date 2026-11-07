// Local visual fixture only: no HA credentials, validator, network jobs or writes.
import "/home_panel_static/home-panel.js";

const data = await (await fetch("/preview.json")).json();
const prefix = "home_panel/config/";
const element = document.querySelector("home-panel-config");
const panels = structuredClone(data[prefix + "panels/"]);
panels.panels = panels.panels.filter(entry => entry.state === "loaded");
let checkpoint = {version:1, generation:0, revision:'fixture:0', record:null, model_validated:false, deployment_ready:false};
element.hass = {
  user: {id: "visual-fixture", is_admin: true},
  locale: {language: "ru"}, connection: {connected: true},
  async callWS(command) {
    if (command.type === prefix + "panels") return structuredClone(panels);
    if ([prefix + "validate", prefix + "model_check"].includes(command.type)) throw {code: "panel_unavailable"};
    if (command.type === prefix + 'draft_get') return structuredClone(checkpoint);
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
      checkpoint = {...checkpoint, generation, revision:'fixture:' + generation, record};
      return structuredClone(checkpoint);
    }
    const result = data[command.type + "/" + (command.source || "")];
    if (!result) throw {code: "not_found"};
    return structuredClone(result);
  },
};
