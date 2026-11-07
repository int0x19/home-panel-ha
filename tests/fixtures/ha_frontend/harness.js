// Test-only HA property adapter. Commands use the actual HA WebSocket server.
import "/home_panel_static/home-panel.js";

const element = document.querySelector("home-panel-config");
const waiting = new Map();
let socket, nextId = 0;
const harness = window.harness = {
  element, calls: [], results: {}, faults: [], menuEvents: 0,
  hass: {user: {id: "test-admin", is_admin: true}, locale: {language: "en"}, connection: {connected: false}},
  update() { element.hass = this.hass; },
  theme(dark) {
    const colors = dark ? {"primary-background-color": "#111416", "card-background-color": "#1d2225",
      "primary-text-color": "#e9edef", "secondary-text-color": "#aab6bd", "divider-color": "#414b51",
      "secondary-background-color": "#2b3338", "primary-color": "#67c9bc", "text-primary-color": "#102a27",
      "app-header-background-color": "#1d2225", "app-header-text-color": "#e9edef", "success-color": "#72cc9b",
      "warning-color": "#efb253"} : {};
    element.removeAttribute("style");
    for (const [key, value] of Object.entries(colors)) element.style.setProperty("--" + key, value);
  },
  async connect() {
    socket = new WebSocket(location.origin.replace("http", "ws") + "/api/websocket");
    await new Promise((resolve, reject) => {
      socket.onmessage = event => {
        const message = JSON.parse(event.data);
        if (message.type === "auth_required") socket.send(JSON.stringify({type: "auth", access_token: window.testCredentials}));
        else if (message.type === "auth_ok") resolve();
        else if (message.type === "auth_invalid") reject(new Error("Test authentication rejected"));
        else if (message.type === "result") {
          const job = waiting.get(message.id);
          if (!job) return;
          waiting.delete(message.id);
          message.success ? job.resolve(message.result) : job.reject(message.error);
        }
      };
      socket.onerror = () => reject(new Error("Test socket unavailable"));
    });
    socket.onclose = () => {
      this.hass.connection.connected = false;
      this.update();
      for (const job of waiting.values()) job.reject({code: "cannot_connect"});
      waiting.clear();
    };
    this.hass.connection = {connected: true};
    this.update();
  },
  async close() {
    if (socket.readyState === WebSocket.CLOSED) return;
    await new Promise(resolve => { socket.addEventListener("close", resolve, {once: true}); socket.close(); });
  },
};
harness.hass.callWS = async command => {
  harness.calls.push(structuredClone(command));
  const fault = harness.faults.shift();
  if (fault?.error) throw {code: fault.error, message: "UNTRUSTED PRIVATE TRANSPORT DETAIL"};
  const result = await new Promise((resolve, reject) => {
    const id = ++nextId;
    waiting.set(id, {resolve, reject});
    socket.send(JSON.stringify({id, ...command}));
  });
  harness.results[command.type + '/' + (command.source || '')] = structuredClone(result);
  if (fault?.lost) throw {code:'cannot_connect'};
  if (fault?.mutate) fault.mutate(result);
  if (fault?.hold) await new Promise(resolve => { harness.release = resolve; });
  return result;
};
element.addEventListener("hass-toggle-menu", () => harness.menuEvents++);
harness.update();
await harness.connect();
