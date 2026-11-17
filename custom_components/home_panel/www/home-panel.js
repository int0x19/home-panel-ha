// HA owns authentication and transport. This module never contacts the device.
import './draft-editor.js';
const PREFIX = "home_panel/config/";
const HARD_LIMIT = 65536;
const words = {
  en: {
    panel: "Panel", choose: "Select a panel", refresh: "Refresh status", settings: "Integration settings",
    menu: "Open sidebar", reload: "Reload panels", admin: "Administrator access required",
    empty: "No panels configured", unavailable: "Metadata unavailable", offline: "HA disconnected",
    stale: "Status refresh required", loading: "Loading", ready: "Available", busy: "Busy",
    sd: "Configuration storage", present: "Ready", absent: "Unavailable", loaded: "Loaded configuration",
    "sd-files": "SD", "flash-nvs": "Flash", "flash-confirmed": "Confirmed flash",
    "flash-previous": "Previous flash", "flash-trial": "Trial flash",
    revision: "Revision", limit: "JSON byte limit", authority: "Authority", unmanaged: "Unmanaged",
    managed: "HA-managed", scope: "Action preview", readingsScope: "Room readings preview", deployment: "Deployment unavailable",
    source: "Source", active: "Active", candidate: "Candidate", backup: "Backup", builtin: "Builtin",
    file: "File", bytes: "Bytes", state: "State", valid: "Valid", invalid: "Invalid", missing: "Missing",
    import: "Import", original: "Imported JSON", check: "Check JSON", download: "Download original",
    noOriginal: "No document imported", openFile: "Open JSON file", validate: "Validate", editor: "Draft", edit: "Edit draft",
    json: "JSON document", checks: "Validation", accepted: "Valid model", rejected: "Invalid model",
    modelError: "Model error", rooms: "Rooms", digest: "SHA-256", earlier: "Source changed since import",
    checkedEarlier: "Previous validation", validationFailed: "Validation unavailable", checking: "Checking",
    notChecked: "Not checked", inputLimit: "Input exceeds the byte limit", badFile: "Invalid UTF-8 file",
    tooLarge: "File exceeds the byte limit", discard: "Discard", cancel: "Cancel",
    discardTitle: "Discard local changes?", leaveTitle: "Leave Home Panel and discard unsaved changes?",
    navigationLimited: "This browser cannot protect unsaved changes when using Back/Forward. Save in HA before leaving.",
    noStatus: "Select a panel to load metadata",
    schema: "Schema", widgets: "Widget types", capabilities: "Capabilities", unmeasured: "Limits not measured on device",
    incomplete: "Asset inventory incomplete", sourceStatus: "File status", setup_retry: "Setup retry",
    setup_error: "Setup error", not_loaded: "Not loaded", migration_error: "Migration error",
    failed_unload: "Unload failed", setup_in_progress: "Connecting", unload_in_progress: "Unloading",
    saved: "Downloaded", imported: "Imported and validated", fileLoaded: "Local file loaded",
    filename: "Filename", input: "Local input", connection: "Connection", unsupported: "Firmware metadata incompatible",
  },
  ru: {
    panel: "Панель", choose: "Выберите панель", refresh: "Обновить статус", settings: "Настройки интеграции",
    menu: "Открыть меню", reload: "Обновить список", admin: "Требуются права администратора",
    empty: "Панели не настроены", unavailable: "Метаданные недоступны", offline: "Нет соединения с HA",
    stale: "Нужно обновить статус", loading: "Загрузка", ready: "Доступна", busy: "Занято",
    sd: "Хранилище конфигурации", present: "Готово", absent: "Недоступно", loaded: "Загружена конфигурация",
    "sd-files": "SD", "flash-nvs": "Flash", "flash-confirmed": "Подтверждённая flash",
    "flash-previous": "Предыдущая flash", "flash-trial": "Пробная flash",
    revision: "Ревизия", limit: "Лимит JSON, байт", authority: "Управление", unmanaged: "Локальное",
    managed: "Через HA", scope: "Превью действий", readingsScope: "Превью сенсоров комнат", deployment: "Применение недоступно",
    source: "Источник", active: "Активный", candidate: "Кандидат", backup: "Резервный", builtin: "Встроенная",
    file: "Файл", bytes: "Байт", state: "Состояние", valid: "Корректный", invalid: "Некорректный", missing: "Отсутствует",
    import: "Импорт", original: "Исходный JSON", check: "Проверка JSON", download: "Скачать оригинал",
    noOriginal: "Нет импортированного документа", openFile: "Открыть JSON", validate: "Проверить", editor: "Черновик", edit: "Создать черновик",
    json: "JSON-документ", checks: "Проверка", accepted: "Модель корректна", rejected: "Ошибка модели",
    modelError: "Ошибка модели", rooms: "Комнат", digest: "SHA-256", earlier: "Источник изменился после импорта",
    checkedEarlier: "Предыдущая проверка", validationFailed: "Проверка недоступна", checking: "Проверка",
    notChecked: "Не проверено", inputLimit: "Превышен лимит байт", badFile: "Некорректный UTF-8",
    tooLarge: "Файл превышает лимит байт", discard: "Отбросить", cancel: "Отмена",
    discardTitle: "Отбросить локальные изменения?", leaveTitle: "Покинуть Home Panel и отбросить несохранённые изменения?",
    navigationLimited: "Этот браузер не защищает несохранённые изменения при переходах Назад/Вперёд. Сохраните черновик в HA перед выходом.",
    noStatus: "Выберите панель для чтения метаданных",
    schema: "Схема", widgets: "Типы виджетов", capabilities: "Возможности", unmeasured: "Лимиты не измерены на устройстве",
    incomplete: "Неполный набор ресурсов", sourceStatus: "Статус файла", setup_retry: "Повтор подключения",
    setup_error: "Ошибка подключения", not_loaded: "Не загружена", migration_error: "Ошибка миграции",
    failed_unload: "Ошибка выгрузки", setup_in_progress: "Подключение", unload_in_progress: "Выгрузка",
    saved: "Скачано", imported: "Импортировано и проверено", fileLoaded: "Локальный файл загружен",
    filename: "Имя файла", input: "Локальный текст", connection: "Соединение", unsupported: "Несовместимые метаданные прошивки",
  },
};
const errors = {
  unauthorized: ["Administrator access required", "Требуются права администратора"],
  panel_unavailable: ["Panel or configuration storage unavailable", "Панель или хранилище недоступны"],
  panel_busy: ["Panel is busy", "Панель занята"],
  invalid_auth: ["Panel access key rejected", "Ключ панели отклонён"],
  identity_mismatch: ["Paired panel identity changed", "Изменилась привязка к панели"],
  incompatible_response: ["Firmware metadata missing, stale or incompatible", "Метаданные прошивки отсутствуют, устарели или несовместимы"],
  invalid_document: ["Invalid document or byte limit exceeded", "Некорректный документ или превышен лимит байт"],
  invalid_import: ["Imported file failed validation", "Импортированный файл не прошёл проверку"],
  candidate_conflict: ["Import and check the draft again before sending", "Повторно импортируйте и проверьте черновик перед отправкой"],
  not_found: ["File or receipt unavailable", "Файл или результат недоступен"],
  read_conflict: ["Panel boot or source changed; refresh status", "Панель или источник изменились: обновите статус"],
  expired: ["Receipt expired; refresh status", "Результат устарел: обновите статус"],
  outcome_unknown: ["Result unknown; refresh status before another request", "Результат неизвестен: сначала обновите статус"],
  status_refresh_required: ["Status refresh required", "Нужно обновить статус"],
  cannot_connect: ["Panel connection unavailable", "Нет соединения с панелью"],
  internal_error: ["Internal read/check error", "Внутренняя ошибка чтения/проверки"],
  panel_error: ["Panel request failed", "Ошибка запроса к панели"],
  draft_conflict: ['HA draft version conflict; local changes retained', 'Конфликт версии черновика HA; локальные правки сохранены'],
  draft_busy: ['HA draft storage is busy', 'Хранилище черновика HA занято'],
  model_check_busy: ['HA model processing is busy', 'Обработка модели в HA занята'],
  invalid_draft: ['Invalid or oversized HA draft', 'Некорректный черновик HA или превышен лимит'],
  draft_storage_error: ['HA draft storage unavailable; local changes retained', 'Хранилище черновика HA недоступно; локальные правки сохранены'],
  draft_history_missing: ['HA history version unavailable; reload the checkpoint', 'Версия истории HA недоступна; загрузите текущий черновик'],
};

class HomePanelConfig extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this._epoch = 0;
    this._fileGeneration = 0;
    this._attempted = false;
    this._validationFresh = false;
    this._entries = [];
    this._entry = "";
    this._status = null;
    this._original = null;
    this._input = "";
    this._inputVersion = 0;
    this._checkedVersion = -1;
    this._validation = null;
    this._tab = "original";
    this._busy = false;
    this._fresh = false;
    this._needsRefresh = false;
    this._errorCode = "";
    this._notice = "";
    this._beforeUnload = event => {
      if (this._hasLocalChanges) { event.preventDefault(); event.returnValue = ""; }
    };
    this._guardNavigation = event => {
      if (event.cancelable && event.destination.sameDocument && !this._confirmDeparture(event.destination.url)) event.preventDefault();
    };
    this._guardLink = event => {
      if (this._navigation || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const anchor = event.composedPath().find(node => node.localName === 'a' && node.hasAttribute('href'));
      if (!anchor || anchor.hasAttribute('download') || (anchor.target && anchor.target !== '_self')) return;
      const url = new URL(anchor.getAttribute('href'), document.baseURI);
      if (url.origin !== location.origin || this._confirmDeparture(url.href)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    this.shadowRoot.innerHTML = `
      <link rel="stylesheet" href="${new URL("./home-panel.css", import.meta.url)}">
      <header>
        <button id="menu" class="icon" data-title="menu"><ha-icon icon="mdi:menu">&#9776;</ha-icon></button>
        <h1>Home Panel</h1>
        <a class="icon" href="/config/integrations/integration/home_panel" data-title="settings"><ha-icon icon="mdi:cog-outline">&#9881;</ha-icon></a>
      </header>
      <p id="access" role="status" hidden></p>
      <main hidden>
        <section class="selection">
          <label><span data-text="panel"></span><select id="panel"></select></label>
          <button id="reload" class="icon" data-title="reload"><ha-icon icon="mdi:refresh">&#8635;</ha-icon></button>
          <button id="refresh"><ha-icon icon="mdi:sync">&#8635;</ha-icon><span data-text="refresh"></span></button>
        </section>
        <div class="status-line" aria-live="polite"><span id="connection" class="badge"></span><span id="scope" class="badge"></span><span class="muted" data-text="deployment"></span></div>
        <p id="message" role="status" hidden></p>
        <p id="navigation-warning" class="warning" role="status" data-text="navigationLimited" hidden></p>
        <section id="metadata" hidden>
          <dl class="facts">
            <div><dt data-text="loaded"></dt><dd id="loaded"></dd></div>
            <div><dt data-text="revision"></dt><dd id="revision"></dd></div>
            <div><dt data-text="sd"></dt><dd id="sd"></dd></div>
            <div><dt data-text="limit"></dt><dd id="limit"></dd></div>
            <div><dt data-text="authority"></dt><dd id="authority"></dd></div>
            <div><dt data-text="widgets"></dt><dd id="widgets"></dd></div>
          </dl>
          <div class="files" role="table" aria-label="Configuration files">
            <div class="file-head" role="row"><span data-text="source"></span><span data-text="revision"></span><span data-text="bytes"></span><span data-text="state"></span><span></span></div>
            ${["active", "candidate", "backup"].map(source => `<div class="file-row" data-source="${source}" role="row"><strong data-text="${source}" role="cell"></strong><span class="file-revision" role="cell"></span><span class="file-bytes" role="cell"></span><span class="file-state" role="cell"></span><button data-import="${source}"><ha-icon icon="mdi:tray-arrow-down">&#8595;</ha-icon><span data-text="import"></span></button></div>`).join("")}
          </div>
          <details id="capabilities"><summary data-text="capabilities"></summary><p id="limitsNote" class="muted"></p><dl id="limits"></dl></details>
        </section>
        <section class="workspace">
          <div class="tabs" role="tablist">
            <button id="tab-original" role="tab" aria-controls="original" data-text="original"></button>
            <button id="tab-editor" role="tab" aria-controls="editor" data-text="editor"></button>
            <button id="tab-check" role="tab" aria-controls="check" data-text="check"></button>
          </div>
          <div id="original" role="tabpanel" aria-labelledby="tab-original">
            <div class="document-bar"><span id="originalInfo" class="muted"></span><button id="edit-original"><ha-icon icon="mdi:pencil-outline">&#9998;</ha-icon><span data-text="edit"></span></button><button id="download" class="icon" data-title="download"><ha-icon icon="mdi:download">&#8595;</ha-icon></button></div>
            <p id="sourceChanged" class="warning" data-text="earlier" hidden></p>
            <p id="originalReport" class="report" hidden></p>
            <pre id="document" tabindex="0"></pre>
            <details id="digest" hidden><summary data-text="digest"></summary><code id="sha"></code></details>
          </div>
          <div id="editor" role="tabpanel" aria-labelledby="tab-editor" hidden><home-panel-draft id="draft-editor"></home-panel-draft></div>
          <div id="check" role="tabpanel" aria-labelledby="tab-check" hidden>
            <div class="document-bar"><button id="openFile"><ha-icon icon="mdi:file-upload-outline">&#8593;</ha-icon><span data-text="openFile"></span></button><input id="file" type="file" accept=".json,application/json" hidden><button id="validate" class="primary"><ha-icon icon="mdi:check">&#10003;</ha-icon><span data-text="validate"></span></button></div>
            <label class="editor-label" for="input"><span data-text="json"></span><span id="inputBytes" class="muted"></span></label>
            <textarea id="input" spellcheck="false" autocapitalize="off" autocomplete="off" maxlength="65536"></textarea>
            <p id="validation" class="report" aria-live="polite"></p>
          </div>
        </section>
      </main>
      <dialog id="discard-dialog"><form method="dialog"><h2 data-text="discardTitle"></h2><div class="dialog-actions"><button value="cancel" data-text="cancel" autofocus></button><button value="discard" class="danger" data-text="discard"></button></div></form></dialog>`;
    this.$("menu").onclick = () => this.dispatchEvent(new CustomEvent("hass-toggle-menu", {bubbles: true, composed: true}));
    this.$("reload").onclick = () => this._loadPanels();
    this.$("panel").onchange = event => this._select(event.target.value);
    this.$("refresh").onclick = () => this._statusRequest();
    this.$("tab-original").onclick = () => this._setTab("original");
    this.$("tab-editor").onclick = () => this._setTab("editor");
    this.$("tab-check").onclick = () => this._setTab("check");
    this.shadowRoot.querySelector(".tabs").onkeydown = event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const tabs = ['original', 'editor', 'check'];
      const tab = event.key === "Home" ? "original" : event.key === "End" ? "check" : tabs[(tabs.indexOf(this._tab) + (event.key === 'ArrowLeft' ? 2 : 1)) % 3];
      this._setTab(tab);
      this.$("tab-" + tab).focus();
    };
    this.$("openFile").onclick = () => this.$("file").click();
    this.$("file").onchange = event => this._readFile(event.target.files[0]);
    this.$("input").oninput = event => {
      this._input = event.target.value;
      this._inputVersion++;
      this._update();
    };
    this.$("validate").onclick = () => this._validate();
    this.$("download").onclick = () => this._download();
    this.$('edit-original').onclick = () => this._editOriginal();
    this.$('draft-editor').addEventListener('draft-validate', event => this._validateDraft(event.detail));
    this.$('draft-editor').addEventListener('draft-send', event => this._sendDraft(event.detail));
    this.$('draft-editor').addEventListener('draft-model-check', event => this._checkModel(event.detail));
    this.$('draft-editor').addEventListener('draft-changes', event => this._compareDraft(event.detail));
    this.$('draft-editor').addEventListener('draft-entities', event => this._queryEntities(event.detail));
    this.$('draft-editor').addEventListener('draft-storage-save', event => this._saveHADraft(event.detail));
    this.$('draft-editor').addEventListener('draft-storage-load', () => this._loadHADraft());
    this.$('draft-editor').addEventListener('draft-storage-delete', event => this._deleteHADraft(event.detail));
    this.$('draft-editor').addEventListener('draft-storage-history', event => this._restoreHADraft(event.detail));
    this.$('draft-editor').addEventListener('draft-changed', () => this._updateNavigationWarning());
    this.shadowRoot.querySelectorAll("[data-import]").forEach(button => {
      button.onclick = () => this._import(button.dataset.import);
    });
  }

  $(id) { return this.shadowRoot.getElementById(id); }
  t(key) { return (words[this._lang] || words.en)[key] || key; }
  get _admin() { return this._hass?.user?.is_admin === true; }
  get _online() { return this._hass?.connection?.connected !== false; }
  get _selected() { return this._entries.find(entry => entry.entry_id === this._entry); }
  get _hasLocalChanges() {
    return this.isConnected && location.pathname === this._guardPath && this._admin && Boolean(this._input || this.$('draft-editor').dirty);
  }

  _confirmDeparture(destination) {
    if (!this._hasLocalChanges || new URL(destination).pathname === location.pathname) return true;
    // Synchronous confirmation lets the original HA navigation continue, without replay or history patches.
    return window.confirm(this.t('leaveTitle'));
  }

  _updateNavigationWarning() {
    this.$('navigation-warning').hidden = Boolean(this._navigation) || !this._hasLocalChanges;
  }

  connectedCallback() {
    this._guardPath = location.pathname;
    this._navigation = window.navigation;
    this._navigation?.addEventListener('navigate', this._guardNavigation);
    window.addEventListener('click', this._guardLink, true);
    window.addEventListener("beforeunload", this._beforeUnload);
    this._update();
    if (this._admin && this._online && !this._attempted) this._loadPanels();
  }

  disconnectedCallback() {
    this._navigation?.removeEventListener('navigate', this._guardNavigation);
    this._navigation = null;
    window.removeEventListener('click', this._guardLink, true);
    window.removeEventListener("beforeunload", this._beforeUnload);
    this._reset();
    this._loaded = false;
    this._attempted = false;
  }

  set hass(value) {
    const connection = this._lastConnection;
    const wasOnline = this._lastOnline;
    const userChanged = this._lastUserId !== undefined && this._lastUserId !== value?.user?.id;
    this._hass = value;
    this._lang = (value?.locale?.language || value?.language || "en").startsWith("ru") ? "ru" : "en";
    if (!this._admin || userChanged) {
      this._reset();
      this._entries = [];
      this._loaded = false;
      this._attempted = false;
    } else if (connection && (connection !== value.connection || wasOnline !== this._online)) {
      this._epoch++;
      this._busy = false;
      this._fresh = false;
      this._validationFresh = false;
      this._needsRefresh = Boolean(this._entry);
      this._attempted = false;
      this.$('draft-editor').invalidateStorage();
      this.$('draft-editor').invalidateImport();
    }
    this._lastConnection = value?.connection;
    this._lastOnline = this._online;
    this._lastUserId = value?.user?.id;
    this._update();
    if (this.isConnected && this._admin && this._online && !this._attempted) this._loadPanels();
  }

  set narrow(value) { this.toggleAttribute("narrow", !!value); }
  set panel(value) { this._panel = value; }
  set route(value) { this._route = value; }

  _reset() {
    this._epoch++;
    this._entry = "";
    this._status = this._original = this._validation = null;
    this._input = "";
    this._inputVersion++;
    this._checkedVersion = -1;
    this._validationFresh = false;
    this._limitsText = undefined;
    this._busy = this._fresh = this._needsRefresh = false;
    this._errorCode = this._notice = "";
    this.$("input").value = "";
    this.$("document").textContent = "";
    this.$("sha").textContent = "";
    this.$("file").value = "";
    this.$('draft-editor').clear(true);
    if (this.shadowRoot.querySelector("dialog").open) this.shadowRoot.querySelector("dialog").close("cancel");
  }

  async _request(operation, data, accept, reject = () => {}) {
    if (!this.isConnected || !this._admin || !this._online || this._busy) return;
    const epoch = this._epoch;
    this._busy = true;
    this._errorCode = this._notice = "";
    this._update();
    try {
      const result = await this._hass.callWS({type: PREFIX + operation, ...data});
      if (epoch !== this._epoch || !this.isConnected || !this._admin) return;
      accept(result);
    } catch (error) {
      if (epoch !== this._epoch || !this.isConnected || !this._admin) return;
      this._errorCode = Object.hasOwn(errors, error?.code) ? error.code : "cannot_connect";
      reject(this._errorCode);
      if (operation.startsWith('draft_')) this.$('draft-editor').invalidateStorage(this._errorCode);
      else if (!['panels', 'model_check', 'model_changes', 'entities'].includes(operation)) {
        this._fresh = false;
        this._validationFresh = false;
        this._needsRefresh = true;
      }
    } finally {
      if (epoch === this._epoch) {
        this._busy = false;
        this._update();
      }
    }
  }

  async _queryEntities(detail) {
    const draft = this.$('draft-editor');
    await this._request('entities', {entry_id:this._entry, ...detail.query},
      result => draft.acceptEntities(result, detail.request), () => draft.rejectEntities(detail.request));
  }

  async _loadPanels() {
    if (this._busy) return;
    this._attempted = true;
    await this._request("panels", {}, result => {
      this._entries = result.panels;
      this._loaded = true;
      if (this._entry && this._selected?.state !== "loaded") {
        this._fresh = false;
        this._needsRefresh = true;
      }
      this._updateOptions();
    });
  }

  _updateOptions() {
    const select = this.$("panel");
    select.replaceChildren(new Option(this.t(this._loaded && !this._entries.length ? "empty" : "choose"), ""));
    for (const entry of this._entries) select.add(new Option(entry.name, entry.entry_id));
    select.value = this._entry;
  }

  async _select(entryId) {
    const epoch = this._epoch;
    const dialog = this.shadowRoot.querySelector("dialog");
    if (!this._admin || !this._online || entryId === this._entry || this._busy || dialog.open) return;
    if (this._input || this.$('draft-editor').dirty) {
      const result = new Promise(resolve => dialog.addEventListener("close", () => resolve(dialog.returnValue), {once: true}));
      dialog.showModal();
      if (await result !== "discard") { this.$("panel").value = this._entry; return; }
    }
    if (epoch !== this._epoch || !this._admin || !this._online || !this.isConnected) return;
    this._reset();
    this._entry = entryId;
    this.$("panel").value = entryId;
    this._update();
    await this._loadHADraft();
    // A restored HA checkpoint must not wait for an offline panel's HTTP timeout.
    if (epoch + 1 === this._epoch && !this._original && this._selected?.state === 'loaded') await this._statusRequest();
  }

  _acceptStatus(result) {
    this._status = result;
    this._fresh = true;
    this._validationFresh = false;
    this._needsRefresh = result.requires_status_refresh;
    this.$('draft-editor').invalidate();
  }

  async _editOriginal() {
    if (!this._original || this._busy || !this._admin) return;
    const epoch = this._epoch;
    const dialog = this.shadowRoot.querySelector('dialog');
    if (dialog.open) return;
    if (this.$('draft-editor').dirty) {
      const result = new Promise(resolve => dialog.addEventListener('close', () => resolve(dialog.returnValue), {once:true}));
      dialog.showModal();
      if (await result !== 'discard') return;
    }
    if (epoch !== this._epoch || !this._admin || !this.isConnected) return;
    const highWater = Math.max(this._status?.status.high_water_revision || 0, this._status?.status.loaded_revision || this._original.revision, ...Object.values(this._status?.status.files || {}).map(f => f.revision));
    this.$('draft-editor').begin(this._original, this._status?.capabilities || this._original.capabilities, highWater);
    this._setTab('editor');
  }

  async _validateDraft(detail) {
    const draft = this.$('draft-editor');
    if (!this._canJob || detail.version !== draft.version) return;
    const import_id = this._status?.candidate_send_available ? draft.importId : null;
    await this._request('validate', {entry_id:this._entry, document:detail.document, ...(import_id ? {import_id} : {})}, result => {
      this._acceptStatus(result);
      draft.acceptValidation(result.validation, detail.version, result.candidate_document);
    });
  }

  async _sendDraft(detail) {
    const draft = this.$('draft-editor');
    if (!this._canJob || !this._status?.candidate_send_available || detail.version !== draft.version || !detail.import_id) return;
    await this._request('send', {entry_id:this._entry, document:detail.document, import_id:detail.import_id}, result => {
      this._acceptStatus(result);
      draft.acceptSent(result.candidate, detail.version);
    }, () => draft.invalidateImport());
  }

  async _checkModel(detail) {
    const draft = this.$('draft-editor');
    if (!this._entry || detail.version !== draft.version) return;
    await this._request('model_check', {entry_id:this._entry, document:detail.document}, result => {
      draft.acceptModelValidation(result, detail.version);
    });
  }

  async _compareDraft(detail) {
    const draft = this.$('draft-editor');
    if (!this._entry || detail.version !== draft.version) return;
    await this._request('model_changes', {entry_id:this._entry, base:detail.base, document:detail.document},
      result => draft.acceptChanges(result, detail), () => draft.rejectChanges(detail));
  }

  async _loadHADraft() {
    if (!this._entry) return;
    await this._request('draft_get', {entry_id:this._entry}, result => {
      const editable = this.$('draft-editor').acceptStored(result, true);
      if (result.record) {
        const origin = result.record.original;
        this._original = {...origin, capabilities:result.record.capabilities, bytes:new TextEncoder().encode(origin.document).length, validation:null};
        this.$('document').textContent = origin.document; this.$('sha').textContent = origin.sha256;
        if (!editable) { this._input = result.record.document; this._inputVersion++; this.$('input').value = this._input; this._errorCode = 'invalid_draft'; }
        this._setTab(editable ? 'editor' : 'check');
      }
    });
  }

  async _saveHADraft(detail) {
    if (!this._entry || detail.version !== this.$('draft-editor').version) return;
    const {version, ...payload} = detail;
    await this._request('draft_save', {entry_id:this._entry, ...payload}, result => this.$('draft-editor').acceptStored(result, false, version));
  }

  async _deleteHADraft(detail) {
    if (!this._entry) return;
    await this._request('draft_delete', {entry_id:this._entry, ...detail}, result => this.$('draft-editor').acceptStored(result, true));
  }

  async _restoreHADraft(detail) {
    const draft = this.$('draft-editor');
    if (!this._entry || detail.version !== draft.version) return;
    const {version, ...payload} = detail;
    await this._request('draft_history_get', {entry_id:this._entry, ...payload}, result => {
      if (!draft.restoreHistory(result, detail)) return;
      const {original:origin, capabilities} = result.record;
      this._original = {...origin, capabilities, bytes:new TextEncoder().encode(origin.document).length, validation:null};
      this.$('document').textContent = origin.document; this.$('sha').textContent = origin.sha256;
      this._setTab('editor');
    });
  }

  async _statusRequest() {
    if (this._selected?.state !== "loaded") return;
    await this._request("status", {entry_id: this._entry}, result => this._acceptStatus(result));
  }

  get _canJob() {
    return this._admin && this._selected?.state === "loaded" && this._fresh && !this._needsRefresh &&
      !this._status?.status.busy && !this._status?.status.restarting && !this._busy && this._online;
  }

  async _import(source) {
    const file = this._status?.status.files[source];
    if (!this._canJob || !file?.valid || !this._status.status.storage_ready) return;
    await this._request("import", {entry_id: this._entry, source}, result => {
      this._acceptStatus(result);
      this._original = result;
      this.$('draft-editor').bindImport(result);
      this.$("document").textContent = result.document;
      this.$("sha").textContent = result.sha256;
      this._notice = "imported";
      this._setTab("original");
    });
  }

  async _validate() {
    if (!this._canJob || !this._input || this._inputBytes > this._byteLimit) return;
    const version = this._inputVersion;
    await this._request("validate", {entry_id: this._entry, document: this._input}, result => {
      this._acceptStatus(result);
      this._validation = result.validation;
      this._checkedVersion = version;
      this._validationFresh = true;
    });
  }

  async _readFile(file) {
    if (!file || this._busy) return;
    const epoch = this._epoch;
    const generation = ++this._fileGeneration;
    const inputVersion = this._inputVersion;
    this._errorCode = this._notice = "";
    try {
      if (file.size > HARD_LIMIT) throw new Error("tooLarge");
      const text = new TextDecoder("utf-8", {fatal: true}).decode(await file.arrayBuffer());
      if (epoch !== this._epoch || generation !== this._fileGeneration || inputVersion !== this._inputVersion || !this.isConnected || !this._admin) return;
      this._input = text;
      this.$("input").value = text;
      this._inputVersion++;
      this._notice = "fileLoaded";
    } catch (error) {
      if (epoch !== this._epoch || generation !== this._fileGeneration || inputVersion !== this._inputVersion) return;
      this._notice = error.message === "tooLarge" ? "tooLarge" : "badFile";
    } finally {
      this.$("file").value = "";
      this._update();
    }
  }

  _setTab(tab) { this._tab = tab; this._update(); }
  get _inputBytes() { return new TextEncoder().encode(this._input).length; }
  get _byteLimit() { return this._status?.status.max_bytes || HARD_LIMIT; }

  _download() {
    if (!this._original || !this._admin) return;
    const data = this._original;
    const url = URL.createObjectURL(new Blob([new TextEncoder().encode(data.document)], {type: "application/json"}));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `panel-${data.source}-r${data.revision}.json`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  _report(report) {
    return `${this.t(report.valid ? "accepted" : "rejected")} · ${this.t("revision")} ${report.document_revision} · ${this.t("rooms")} ${report.rooms}${report.valid ? "" : ` · ${this.t("modelError")} ${report.model_status}/${report.model_error}`}`;
  }

  _update() {
    const root = this.shadowRoot;
    root.querySelector("main").hidden = !this._admin;
    this.$("access").hidden = this._admin;
    this.$("access").textContent = this.t("admin");
    root.querySelectorAll("[data-text]").forEach(node => { node.textContent = this.t(node.dataset.text); });
    root.querySelectorAll("[data-title]").forEach(node => {
      node.title = this.t(node.dataset.title);
      node.setAttribute("aria-label", node.title);
    });
    this.$("input").setAttribute("aria-label", this.t("json"));
    this.$("document").setAttribute("aria-label", this.t("original"));
    root.querySelector(".files").setAttribute("aria-label", this.t("sourceStatus"));
    const select = this.$("panel");
    select.disabled = this._busy || !this._online || !this._admin;
    if (select.options.length !== this._entries.length + 1) this._updateOptions();
    if (select.options[0]) select.options[0].text = this.t(this._loaded && !this._entries.length ? "empty" : "choose");
    this.$("reload").disabled = this._busy || !this._online;
    this.$("refresh").disabled = this._busy || !this._online || this._selected?.state !== "loaded";
    this.$("connection").textContent = this.t(!this._online ? "offline" : this._busy ? "loading" :
      this._selected?.state && this._selected.state !== "loaded" ? this._selected.state : this._needsRefresh || (this._status && !this._fresh) ? "stale" :
      this._fresh ? (this._status.status.busy ? "busy" : "ready") : this._entry ? "unavailable" : "choose");
    this.$("connection").className = "badge " + (this._online && this._fresh && !this._needsRefresh ? "success" : "muted");
    this.$("scope").textContent = this.t(this._status?.capabilities.features.includes('widget.sensor') ? "readingsScope" : "scope");
    const error = errors[this._errorCode];
    this.$("message").hidden = !error && !this._notice;
    this.$("message").textContent = error ? error[this._lang === "ru" ? 1 : 0] : this.t(this._notice);
    this.$("message").className = error ? "warning" : "muted";
    this.$("metadata").hidden = !this._status;
    if (this._status) {
      const state = this._status.status;
      const caps = this._status.capabilities;
      this.$("loaded").textContent = this.t(state.loaded_source);
      this.$("revision").textContent = state.loaded_revision;
      this.$("sd").textContent = `${this.t(state.storage)}: ${this.t(state.storage_ready ? "present" : "absent")}`;
      this.$("limit").textContent = state.max_bytes;
      this.$("authority").textContent = this.t(this._status.authority.mode === "unmanaged" ? "unmanaged" : "managed");
      this.$("widgets").textContent = caps.widget_types.join(", ");
      for (const row of root.querySelectorAll("[data-source]")) {
        const file = state.files[row.dataset.source];
        row.querySelector(".file-revision").textContent = file.present ? file.revision : "-";
        row.querySelector(".file-bytes").textContent = file.present ? file.bytes : "-";
        row.querySelector(".file-bytes").dataset.unit = this.t("bytes");
        row.querySelector(".file-state").textContent = this.t(!file.present ? "missing" : file.valid ? "valid" : "invalid");
        row.querySelector("button").disabled = !this._canJob || !file.valid || !state.storage_ready;
        row.querySelector("button").setAttribute("aria-label", `${this.t("import")} ${this.t(row.dataset.source)}`);
      }
      this.$("limitsNote").textContent = [!caps.limits_measured_on_device && this.t("unmeasured"), !caps.assets_inventory_complete && this.t("incomplete")].filter(Boolean).join(" · ");
      const limitText = JSON.stringify(caps.limits);
      if (this._limitsText !== limitText) {
        this._limitsText = limitText;
        this.$("limits").replaceChildren();
        for (const [key, value] of Object.entries(caps.limits)) {
          const dt = document.createElement("dt"), dd = document.createElement("dd");
          dt.textContent = key; dd.textContent = value;
          this.$("limits").append(dt, dd);
        }
      }
    }
    for (const tab of ["original", "editor", "check"]) {
      this.$(tab).hidden = this._tab !== tab;
      this.$("tab-" + tab).setAttribute("aria-selected", String(this._tab === tab));
      this.$("tab-" + tab).tabIndex = this._tab === tab ? 0 : -1;
    }
    this.$("originalInfo").textContent = this._original ? `${this.t(this._original.source)} · r${this._original.revision} · ${this._original.bytes} ${this.t("bytes")}` : this.t("noOriginal");
    this.$("download").disabled = !this._original;
    this.$('edit-original').disabled = !this._original || this._busy;
    this.$("digest").hidden = !this._original;
    this.$("originalReport").hidden = !this._original;
    this.$("originalReport").textContent = this._original ? this._original.validation ? this._report(this._original.validation) : this.t('notChecked') : "";
    this.$("sourceChanged").hidden = !this._original || this._status?.status.files[this._original.source]?.sha256 === this._original.sha256;
    this.$("openFile").disabled = this._busy || !this._admin;
    this.$("input").readOnly = this._busy;
    this.$("inputBytes").textContent = `${this._inputBytes} / ${this._byteLimit} ${this.t("bytes")}`;
    this.$("inputBytes").className = this._inputBytes > this._byteLimit ? "warning" : "muted";
    this.$("validate").disabled = !this._canJob || !this._input || this._inputBytes > this._byteLimit;
    const staleReport = this._checkedVersion !== this._inputVersion || !this._fresh || !this._validationFresh;
    this.$("validation").textContent = this._inputBytes > this._byteLimit ? this.t("inputLimit") :
      this._validation ? (staleReport ? this.t("checkedEarlier") + ": " : "") + this._report(this._validation) : this.t("notChecked");
    this.$("validation").className = "report " + (this._validation && !staleReport ? (this._validation.valid ? "success" : "warning") : "muted");
    this.$("originalReport").className = "report " + (this._fresh && this._original?.validation ? "success" : "muted");
    const draft = this.$('draft-editor');
    draft.context = {language:this._lang, capabilities:this._status?.capabilities, states:this._hass?.states,
      catalogKey:this._epoch,
      revisionHighWater:Math.max(this._status?.status.high_water_revision || 0, this._status?.status.loaded_revision || 0, ...Object.values(this._status?.status.files || {}).map(file => file.revision || 0)),
      canSend:this._canJob && !!this._status?.candidate_send_available,
      canValidate:this._canJob, fresh:this._fresh && !this._needsRefresh, busy:this._busy,
      storageOnline:this._admin && this._online && !!this._selected,
      sourceCurrent:!this._status || !this._fresh ? null : !draft.source || this._status.status.files[draft.source]?.sha256 === draft.sourceHash};
    this._updateNavigationWarning();
  }
}

if (!customElements.get("home-panel-config")) customElements.define("home-panel-config", HomePanelConfig);
