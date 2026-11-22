import {DraftError, editDraft, identity, nextRevision, normalizedDraft, actionCapacity, editableAction, editableReading, editableRoom, roomPlan, assertDraftBudget, supportsReading} from './runtime-draft.mjs';

const labels = {
  en: {empty:'No local draft', room:'Room', addRoom:'Add room', up:'Move up', down:'Move down', delete:'Delete',
    name:'Name', kind:'Page type', normal:'Room', actions:'Actions', update:'Update draft', cancel:'Cancel',
    widgets:'Widgets', addAction:'Add action', addSensor:'Add sensor', entity:'Entity', destination:'Page', icon:'Icon', interaction:'Activation',
    addStatus:'Add binary sensor', unit:'Unit', deviceClass:'Sensor class', group:'Sensor group', groupName:'Group title', ungrouped:'Standalone', newGroup:'New group',
    sensor_fields:'Unsupported sensor settings', opaque_sensor:'Sensor is read-only', sensor_page:'Sensors need a Room page',
    binding_limit:'Entity binding limit reached', groupError:'Invalid sensor group', pixels:'px',
    tap:'Tap', hold:'Hold', confirm:'Confirmation', enabled:'Enabled', stop:'Stop control', check:'On ESP32', checkHA:'In HA', hostModel:'HA model',
    export:'Export draft', reset:'Discard local draft', local:'Local draft', notChecked:'Not checked', previous:'Previous validation',
    saveHA:'Save in HA', loadHA:'Load HA draft', deleteHA:'Delete HA draft', savedHA:'Saved in HA', unsaved:'Unsaved',
    sendPanel:'Send to panel', confirmSend:'Save this candidate on the panel? It will not be applied or restart the panel.', sentCandidate:'Candidate saved; not applied',
    storageUnknown:'HA draft status unknown', conflict:'HA draft version conflict', discardLoad:'Replace local changes with the HA draft?',
    confirmDeleteHA:'Delete the saved HA draft, history and local edits?', restoreInvalid:'Saved draft is not editable',
    history:'HA history', historyEmpty:'No earlier versions', openHistory:'Open as draft',
    confirmHistory:'Replace the local draft with this version?', unknownTime:'Time unknown', bytes:'bytes',
    accepted:'Valid model', rejected:'Invalid model', newRoom:'New room', deleteRoom:'Delete room and its widgets?',
    deleteAction:'Delete action?', deleteSensor:'Delete sensor?', discardFields:'Discard uncommitted fields?', discardDraft:'Discard local draft?',
    readOnly:'Read-only', pending:'Uncommitted fields', changedSource:'Source changed since draft creation',
    changedCaps:'Capabilities changed', offline:'Status refresh required', pages:'pages', tiles:'tiles',
    changes:'Compare', compareWith:'Compare with', originalBase:'Imported original', savedBase:'Saved HA draft',
    changeSummary:'Changes', noChanges:'No structural changes', changesTotal:'Total', changesShown:'Shown', previousChanges:'Previous comparison',
    changesError:'Comparison unavailable', revision:'Revision', room_added:'Room added', room_removed:'Room removed',
    room_changed:'Room changed', room_order:'Room order changed', widget_added:'Widget added', widget_removed:'Widget removed',
    widget_moved:'Widget moved', widget_changed:'Widget changed', widget_order:'Widget order changed', section_changed:'Section changed',
    panel:'Panel settings', style:'Appearance', requires:'Required features', views:'Reusable views', attention:'Attention',
    groups:'Sensor groups', settings:'Settings', type:'Widget type', other:'Other fields',
    chooseEntity:'Choose entity', search:'Search', area:'Area', domain:'Domain', all:'All', unassigned:'No area',
    includeInactive:'Include disabled and hidden', disabled:'Disabled', hidden:'Hidden', unavailable:'Unavailable',
    unknown:'Unknown', missingState:'No state', loading:'Loading', noEntities:'No matching entities', catalogError:'Entity search failed',
    previousPage:'Previous page', nextPage:'Next page', areasTruncated:'Area list is limited; use search across all areas',
    geometry:'Invalid geometry', text:'Invalid or oversized text', entityError:'Invalid entity',
    action_fields:'Unsupported action settings', capability:'Capability unavailable', room_limit:'Room limit reached',
    widget_limit:'Widget limit reached', room_full:'Room is full', page_limit:'Page limit reached', byte_limit:'JSON byte limit exceeded',
    opaque_room:'This page contains unsupported fields/widgets', opaque_action:'Action is read-only', duplicate:'Duplicate action on page',
    identity:'Duplicate or invalid ID', missing:'Item no longer exists', referenced_room:'Room is referenced by attention',
    revision_limit:'Revision limit reached', operation:'Unsupported edit', failed:'Draft edit rejected'},
  ru: {empty:'Нет локального черновика', room:'Комната', addRoom:'Добавить комнату', up:'Переместить выше', down:'Переместить ниже', delete:'Удалить',
    name:'Название', kind:'Тип страницы', normal:'Комната', actions:'Действия', update:'Обновить черновик', cancel:'Отмена',
    widgets:'Виджеты', addAction:'Добавить действие', addSensor:'Добавить сенсор', entity:'Сущность', destination:'Страница', icon:'Иконка', interaction:'Активация',
    addStatus:'Добавить бинарный датчик', unit:'Единица измерения', deviceClass:'Класс сенсора', group:'Группа сенсоров', groupName:'Название группы', ungrouped:'Отдельная карточка', newGroup:'Новая группа',
    sensor_fields:'Неподдерживаемые настройки сенсора', opaque_sensor:'Сенсор доступен только для чтения', sensor_page:'Сенсорам нужна страница комнаты',
    binding_limit:'Достигнут лимит источников данных', groupError:'Некорректная группа сенсоров', pixels:'пкс',
    tap:'Нажатие', hold:'Удержание', confirm:'Подтверждение', enabled:'Включено', stop:'Кнопка остановки', check:'На ESP32', checkHA:'В HA', hostModel:'Модель HA',
    export:'Экспорт черновика', reset:'Отбросить локальный черновик', local:'Локальный черновик', notChecked:'Не проверено', previous:'Предыдущая проверка',
    saveHA:'Сохранить в HA', loadHA:'Загрузить черновик HA', deleteHA:'Удалить черновик HA', savedHA:'Сохранён в HA', unsaved:'Не сохранён',
    sendPanel:'Отправить на панель', confirmSend:'Сохранить кандидата на панели? Он не будет применён, панель не перезагрузится.', sentCandidate:'Кандидат сохранён, не применён',
    storageUnknown:'Статус черновика HA неизвестен', conflict:'Конфликт версии черновика HA', discardLoad:'Заменить локальные изменения черновиком из HA?',
    confirmDeleteHA:'Удалить сохранённый черновик HA, историю и локальные правки?', restoreInvalid:'Сохранённый черновик недоступен для редактирования',
    history:'История HA', historyEmpty:'Предыдущих версий нет', openHistory:'Открыть как черновик',
    confirmHistory:'Заменить локальный черновик этой версией?', unknownTime:'Время неизвестно', bytes:'байт',
    accepted:'Модель корректна', rejected:'Ошибка модели', newRoom:'Новая комната', deleteRoom:'Удалить комнату и её виджеты?',
    deleteAction:'Удалить действие?', deleteSensor:'Удалить сенсор?', discardFields:'Отбросить незавершённые поля?', discardDraft:'Отбросить локальный черновик?',
    readOnly:'Только чтение', pending:'Незавершённые поля', changedSource:'Источник изменился после создания черновика',
    changedCaps:'Возможности панели изменились', offline:'Нужно обновить статус', pages:'стр.', tiles:'плиток',
    changes:'Сравнить', compareWith:'Сравнить с', originalBase:'Импортированный оригинал', savedBase:'Сохранённый черновик HA',
    changeSummary:'Изменения', noChanges:'Нет структурных изменений', changesTotal:'Всего', changesShown:'Показано', previousChanges:'Предыдущее сравнение',
    changesError:'Сравнение недоступно', revision:'Ревизия', room_added:'Комната добавлена', room_removed:'Комната удалена',
    room_changed:'Комната изменена', room_order:'Порядок комнат изменён', widget_added:'Виджет добавлен', widget_removed:'Виджет удалён',
    widget_moved:'Виджет перемещён', widget_changed:'Виджет изменён', widget_order:'Порядок виджетов изменён', section_changed:'Раздел изменён',
    panel:'Настройки панели', style:'Оформление', requires:'Требуемые возможности', views:'Переиспользуемые окна', attention:'События внимания',
    groups:'Группы сенсоров', settings:'Настройки', type:'Тип виджета', other:'Другие поля',
    chooseEntity:'Выбрать сущность', search:'Поиск', area:'Зона', domain:'Домен', all:'Все', unassigned:'Без зоны',
    includeInactive:'Включая отключённые и скрытые', disabled:'Отключена', hidden:'Скрыта', unavailable:'Недоступна',
    unknown:'Неизвестно', missingState:'Нет состояния', loading:'Загрузка', noEntities:'Ничего не найдено', catalogError:'Ошибка поиска сущностей',
    previousPage:'Предыдущая страница', nextPage:'Следующая страница', areasTruncated:'Список зон ограничен; используйте поиск по всем зонам',
    geometry:'Некорректная геометрия', text:'Некорректный или слишком длинный текст', entityError:'Некорректная сущность',
    action_fields:'Неподдерживаемые настройки действия', capability:'Возможность недоступна', room_limit:'Достигнут лимит комнат',
    widget_limit:'Достигнут лимит виджетов', room_full:'Комната заполнена', page_limit:'Достигнут лимит страниц', byte_limit:'Превышен лимит JSON',
    opaque_room:'На странице есть неподдерживаемые поля или виджеты', opaque_action:'Действие доступно только для чтения', duplicate:'Действие уже есть на странице',
    identity:'Некорректный или повторяющийся ID', missing:'Элемент больше не существует', referenced_room:'На комнату ссылается источник внимания',
    revision_limit:'Достигнут предел ревизии', operation:'Неподдерживаемая операция', failed:'Изменение отклонено'},
};
const icons = {'refresh-cw':'refresh', palette:'palette', power:'power', bell:'bell', moon:'weather-night', sun:'white-balance-sunny',
  house:'home', save:'content-save', fan:'fan', sprout:'sprout'};
const catalogDomains = {action:['script', 'scene', 'button', 'input_button'], sensor:['sensor'], status:['binary_sensor']};

class HomePanelDraft extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:'open'});
    this._version = 0;
    this._lang = 'en';
    this._context = {};
    this._draft = null;
    this._unsaved = false;
    this._storeFresh = false;
    this._storeRevision = null;
    this._room = '';
    this._editing = null;
    this._fields = false;
    this._catalogRequest = 0;
    this._catalog = null;
    this._historyItems = [];
    this._historyLimit = 3;
    this.shadowRoot.innerHTML = `
      <link rel="stylesheet" href="${new URL('./home-panel.css', import.meta.url)}">
      <div class="draft-toolbar" id="draft-storage-tools">
        <button id="draft-save-ha"><ha-icon icon="mdi:content-save-outline">&#9633;</ha-icon><span data-label="saveHA"></span></button>
        <button id="draft-load-ha"><ha-icon icon="mdi:folder-open-outline">&#8595;</ha-icon><span data-label="loadHA"></span></button>
        <button id="draft-delete-ha" class="icon danger" data-tool="deleteHA"><ha-icon icon="mdi:trash-can-outline">&#215;</ha-icon></button>
      </div>
      <p id="draft-storage-status" class="report muted" role="status"></p>
      <details id="draft-history"><summary><span data-label="history"></span> <span id="draft-history-count"></span></summary>
        <p id="draft-history-status" class="report muted" role="status"></p>
        <div id="draft-history-items"></div>
      </details>
      <p id="draft-empty" class="muted"></p>
      <section id="draft-work" hidden>
        <div class="draft-toolbar"><span id="draft-base" class="muted"></span>
          <button id="draft-model-check"><ha-icon icon="mdi:check-decagram-outline">&#10003;</ha-icon><span data-label="checkHA"></span></button>
          <button id="draft-check"><ha-icon icon="mdi:check">&#10003;</ha-icon><span data-label="check"></span></button>
          <button id="draft-export" class="icon" data-tool="export"><ha-icon icon="mdi:download">&#8595;</ha-icon></button>
          <button id="draft-send"><ha-icon icon="mdi:tray-arrow-up">&#8593;</ha-icon><span data-label="sendPanel"></span></button>
          <button id="draft-reset" class="icon" data-tool="reset"><ha-icon icon="mdi:undo">&#8630;</ha-icon></button>
        </div>
        <p id="draft-model-status" class="report" role="status"></p>
        <p id="draft-status" class="report" role="status"></p><p id="draft-send-status" class="report success" role="status" hidden></p><p id="draft-error" class="warning" role="status" hidden></p>
        <div id="draft-change-tools" class="draft-toolbar">
          <label class="grow"><span data-label="compareWith"></span><select id="draft-compare-base"><option value="original" data-label="originalBase"></option><option value="saved" data-label="savedBase"></option></select></label>
          <button id="draft-changes" type="button"><ha-icon icon="mdi:file-compare">&#8800;</ha-icon><span data-label="changes"></span></button>
        </div>
        <details id="draft-change-details" hidden><summary data-label="changeSummary"></summary>
          <p id="draft-change-status" class="report muted" role="status"></p>
          <ol id="draft-change-items" class="draft-change-items"></ol>
        </details>
        <div class="draft-toolbar"><label class="grow"><span data-label="room"></span><select id="draft-room"></select></label>
          <button id="draft-add-room" class="icon" data-tool="addRoom"><ha-icon icon="mdi:plus">+</ha-icon></button>
          <button id="draft-room-up" class="icon" data-tool="up"><ha-icon icon="mdi:arrow-up">&#8593;</ha-icon></button>
          <button id="draft-room-down" class="icon" data-tool="down"><ha-icon icon="mdi:arrow-down">&#8595;</ha-icon></button>
          <button id="draft-delete-room" class="icon danger" data-tool="delete"><ha-icon icon="mdi:trash-can-outline">&#215;</ha-icon></button>
        </div>
        <form id="draft-room-form" class="draft-fields">
          <label><span data-label="name"></span><input id="draft-room-name" required maxlength="256" autocomplete="off"></label>
          <label><span data-label="kind"></span><select id="draft-room-kind"><option value="room" data-label="normal"></option><option value="actions" data-label="actions"></option></select></label>
          <div class="draft-toolbar"><button id="draft-update-room" type="submit" data-label="update"></button><button id="draft-cancel-room" type="button" data-label="cancel"></button><span id="draft-room-id" class="muted"></span></div>
        </form>
        <div class="draft-toolbar"><h2 data-label="widgets"></h2><span id="draft-fit" class="muted"></span><button id="draft-add-action" class="icon" data-tool="addAction"><ha-icon icon="mdi:gesture-tap-button">+</ha-icon></button><button id="draft-add-sensor" class="icon" data-tool="addSensor"><ha-icon icon="mdi:thermometer-plus">+</ha-icon></button><button id="draft-add-status" class="icon" data-tool="addStatus"><ha-icon icon="mdi:circle-half-full">+</ha-icon></button></div>
        <div id="draft-widgets"></div>
        <form id="draft-action-form" class="draft-fields" hidden>
          <label><span data-label="name"></span><input id="draft-action-name" required maxlength="256" autocomplete="off"></label>
          <div class="entity-field"><label><span data-label="entity"></span><input id="draft-entity" required maxlength="127" pattern="(script|scene|button|input_button)\\.[a-z0-9_]+" list="draft-entities" autocomplete="off" spellcheck="false"><datalist id="draft-entities"></datalist></label><button id="draft-choose-entity" type="button" class="icon" data-tool="chooseEntity"><ha-icon icon="mdi:magnify">&#9906;</ha-icon></button></div>
          <label><span data-label="destination"></span><select id="draft-target"></select></label>
          <label><span data-label="icon"></span><select id="draft-icon"></select></label>
          <label><span data-label="interaction"></span><select id="draft-interaction"></select></label>
          <label class="draft-check"><input type="checkbox" id="draft-enabled"><span data-label="enabled"></span></label>
          <label class="draft-check" id="draft-stop-field"><input type="checkbox" id="draft-stop"><span data-label="stop"></span></label>
          <div class="draft-toolbar"><button type="submit" id="draft-update-action" class="primary" data-label="update"></button><button type="button" id="draft-cancel-action" data-label="cancel"></button></div>
        </form>
        <form id="draft-sensor-form" class="draft-fields" hidden>
          <label><span data-label="name"></span><input id="draft-sensor-name" required maxlength="256" autocomplete="off"></label>
          <div class="entity-field"><label><span data-label="entity"></span><input id="draft-sensor-entity" required maxlength="127" pattern="sensor\\.[a-z0-9_]+" list="draft-sensor-entities" autocomplete="off" spellcheck="false"><datalist id="draft-sensor-entities"></datalist></label><button id="draft-choose-sensor" type="button" class="icon" data-tool="chooseEntity"><ha-icon icon="mdi:magnify">&#9906;</ha-icon></button></div>
          <label><span data-label="destination"></span><select id="draft-sensor-target"></select></label>
          <label><span data-label="unit"></span><input id="draft-sensor-unit" maxlength="256" autocomplete="off"></label>
          <label><span data-label="deviceClass"></span><input id="draft-sensor-class" maxlength="256" list="draft-sensor-classes" autocomplete="off"><datalist id="draft-sensor-classes"><option value="temperature"></option><option value="humidity"></option></datalist></label>
          <label><span data-label="group"></span><select id="draft-sensor-group"></select></label>
          <label id="draft-group-name-field"><span data-label="groupName"></span><input id="draft-group-name" maxlength="256" autocomplete="off"></label>
          <div class="draft-toolbar"><button type="submit" id="draft-update-sensor" class="primary" data-label="update"></button><button type="button" id="draft-cancel-sensor" data-label="cancel"></button></div>
        </form>
      </section>
      <dialog id="entity-picker" aria-labelledby="entity-picker-title">
        <h2 id="entity-picker-title" data-label="chooseEntity"></h2>
        <form id="entity-search-form" class="draft-fields">
          <div class="entity-field entity-query"><label><span data-label="search"></span><input id="entity-query" type="search" maxlength="128" autocomplete="off"></label><button type="submit" class="icon" data-tool="search"><ha-icon icon="mdi:magnify">&#9906;</ha-icon></button></div>
          <label><span data-label="domain"></span><select id="entity-domain"></select></label>
          <label><span data-label="area"></span><select id="entity-area"></select></label>
          <label class="draft-check entity-query"><input id="entity-inactive" type="checkbox"><span data-label="includeInactive"></span></label>
        </form>
        <p id="entity-results-status" class="report muted" role="status" aria-live="polite"></p>
        <p id="entity-areas-warning" class="report warning" data-label="areasTruncated" hidden></p>
        <div id="entity-results" aria-busy="false"></div>
        <div class="draft-toolbar entity-paging"><button id="entity-previous" type="button" class="icon" data-tool="previousPage"><ha-icon icon="mdi:chevron-left">&#8249;</ha-icon></button><span id="entity-page" class="muted"></span><button id="entity-next" type="button" class="icon" data-tool="nextPage"><ha-icon icon="mdi:chevron-right">&#8250;</ha-icon></button></div>
        <div class="dialog-actions"><button id="entity-cancel" type="button" data-label="cancel"></button></div>
      </dialog>`;
    this.$('draft-choose-entity').onclick = () => this._openEntities('action');
    this.$('draft-choose-sensor').onclick = () => this._openEntities(this._editingKind);
    this.$('entity-search-form').onsubmit = event => { event.preventDefault(); this._searchEntities(); };
    for (const id of ['entity-domain', 'entity-area', 'entity-inactive']) this.$(id).onchange = () => this._searchEntities();
    this.$('entity-previous').onclick = () => this._searchEntities(Math.max(0, this._catalog.offset - 25));
    this.$('entity-next').onclick = () => this._searchEntities(this._catalog.next_offset);
    this.$('entity-cancel').onclick = () => this._closeEntities();
    this.$('entity-picker').oncancel = event => { event.preventDefault(); this._closeEntities(); };
    this.$('draft-room').onchange = event => {
      if (!this._canLeave()) { event.target.value = this._room; return; }
      this._room = event.target.value; this._editing = null; this._fields = false; this._render();
    };
    this.$('draft-add-room').onclick = () => this._edit({type:'add_room', id:identity('room'), name:this.t('newRoom'), kind:'room'}, true);
    for (const [id, offset] of [['draft-room-up', -1], ['draft-room-down', 1]]) this.$(id).onclick = () => this._edit({type:'move_room', room:this._room, offset});
    this.$('draft-delete-room').onclick = () => { if (confirm(this.t('deleteRoom'))) this._edit({type:'delete_room', room:this._room}); };
    this.$('draft-room-form').onsubmit = event => {
      event.preventDefault(); this._edit({type:'room_settings', room:this._room, name:this.$('draft-room-name').value.trim(), kind:this.$('draft-room-kind').value});
    };
    this.$('draft-cancel-room').onclick = () => { this._fields = false; this._render(); };
    this.$('draft-add-action').onclick = () => this._openAction(null);
    this.$('draft-add-sensor').onclick = () => this._openSensor(null);
    this.$('draft-add-status').onclick = () => this._openSensor(null, 'status');
    this.$('draft-cancel-sensor').onclick = () => { if (this._canLeave()) { this._editing = null; this._fields = false; this._render(); } };
    this.$('draft-sensor-form').onsubmit = event => {
      event.preventDefault();
      const settings = {name:this.$('draft-sensor-name').value.trim(), entity:this.$('draft-sensor-entity').value.trim()};
      const unit = this.$('draft-sensor-unit').value.trim(), deviceClass = this.$('draft-sensor-class').value.trim();
      const kind = this._editingKind;
      if (kind === 'sensor' && unit) settings.unit = unit;
      if (deviceClass) settings.device_class = deviceClass;
      const selected = kind === 'sensor' ? this.$('draft-sensor-group').value : '';
      if (selected) settings.group = selected === '@new' ? this._newGroupId : selected;
      this._edit({type:'put_' + kind, room:this._room, previous:this._editing || null, id:identity(kind),
        target:this.$('draft-sensor-target').value, settings,
        ...(selected ? {group_name:this.$('draft-group-name').value.trim()} : {})});
    };
    this.$('draft-sensor-entity').onchange = () => this._sensorDefaults(this._entityStates?.[this.$('draft-sensor-entity').value]?.attributes);
    this.$('draft-sensor-target').onchange = () => { if (this._editingKind === 'sensor') this._sensorGroups(this.$('draft-sensor-group').value); };
    this.$('draft-sensor-group').onchange = () => this._sensorGroupField();
    this.$('draft-cancel-action').onclick = () => { if (this._canLeave()) { this._editing = null; this._fields = false; this._render(); } };
    this.$('draft-action-form').onsubmit = event => {
      event.preventDefault();
      const settings = {name:this.$('draft-action-name').value.trim(), entity:this.$('draft-entity').value.trim(), icon:this.$('draft-icon').value,
        interaction:this.$('draft-interaction').value, enabled:this.$('draft-enabled').checked};
      if (settings.entity.startsWith('script.') && this.$('draft-stop').checked) settings.allow_stop = true;
      this._edit({type:'put_action', room:this._room, previous:this._editing || null, id:identity('action'), target:this.$('draft-target').value, settings});
    };
    for (const form of ['draft-room-form', 'draft-action-form', 'draft-sensor-form']) this.$(form).oninput = () => { this._fields = true; this._controls(); };
    this.$('draft-entity').onchange = () => {
      const state = this._entityStates?.[this.$('draft-entity').value];
      if (!this.$('draft-action-name').value && state) this.$('draft-action-name').value = state.attributes.friendly_name || state.entity_id;
      this._stopField();
    };
    this.$('draft-check').onclick = () => {
      if (this._context.canValidate && !this._fields && this._draft && !this._capsChanged()) this.dispatchEvent(new CustomEvent('draft-validate',
        {bubbles:true, composed:true, detail:{document:JSON.stringify(normalizedDraft(this._draft)), version:this._version}}));
    };
    this.$('draft-model-check').onclick = () => {
      if (this._context.storageOnline && !this._context.busy && !this._fields && this._editing === null && this._draft) {
        this.dispatchEvent(new CustomEvent('draft-model-check', {bubbles:true, composed:true,
          detail:{document:JSON.stringify(normalizedDraft(this._draft)), version:this._version}}));
      }
    };
    this.$('draft-compare-base').onchange = () => this._controls();
    this.$('draft-changes').onclick = () => {
      const base = this._comparisonBase();
      if (this._context.storageOnline && !this._context.busy && !this._fields && this._editing === null && this._draft && base) {
        this.dispatchEvent(new CustomEvent('draft-changes', {bubbles:true, composed:true, detail:{base,
          target:this.$('draft-compare-base').value, document:JSON.stringify(normalizedDraft(this._draft)), version:this._version}}));
      }
    };
    this.$('draft-export').onclick = () => this._export();
    this.$('draft-send').onclick = () => {
      if (this._canSend() && confirm(this.t('confirmSend'))) this.dispatchEvent(new CustomEvent('draft-send', {
        bubbles:true, composed:true, detail:{document:this._candidateDocument, import_id:this._sendImport, version:this._version}}));
    };
    this.$('draft-reset').onclick = () => { if (confirm(this.t('discardDraft'))) this.clear(); };
    this.$('draft-save-ha').onclick = () => {
      if (this._draft && this._storeFresh && !this._fields && this._editing === null && this._context.storageOnline) this._storageEvent('save', {
        expected_revision:this._storeRevision, document:JSON.stringify(normalizedDraft(this._draft)),
        original:this._origin, capabilities:this._caps, version:this._version});
    };
    this.$('draft-load-ha').onclick = () => { if (!this.dirty || confirm(this.t('discardLoad'))) this._storageEvent('load', {}); };
    this.$('draft-delete-ha').onclick = () => { if (this._storeFresh && confirm(this.t('confirmDeleteHA'))) this._storageEvent('delete', {expected_revision:this._storeRevision}); };
  }
  $(id) { return this.shadowRoot.getElementById(id); }
  t(key) { return (labels[this._lang] || labels.en)[key] || key; }
  get dirty() { return this._unsaved || this._fields; }
  get version() { return this._version; }
  get source() { return this._base?.source; }
  get sourceHash() { return this._base?.sha256; }
  get importId() { return this._sendImport; }
  get document() { return this._draft ? structuredClone(this._draft) : null; }
  setEntityStates(states) { this._entityStates = states; }
  set context(value) {
    if (value.catalogKey !== this._context.catalogKey || !value.storageOnline) this._closeEntities();
    const languageChanged = this._lang !== (value.language || 'en');
    this._context = value;
    this._lang = value.language || 'en';
    this._controls();
    if (languageChanged && this._catalog && !this._catalogPending) this.acceptEntities(this._catalog, this._catalogRequest);
  }
  begin(original, caps, highWater) {
    try {
      const doc = JSON.parse(original.document);
      if (doc.format !== 'home-panel-runtime' || doc.schema_version !== 1 || !Array.isArray(doc.rooms) || !doc.rooms.length) throw new DraftError('capability');
      doc.revision = nextRevision(doc, highWater);
      assertDraftBudget(doc, caps);
      this._draft = doc; this._base = {source:original.source, sha256:original.sha256, revision:original.revision};
      this._origin = {source:original.source, sha256:original.sha256, revision:original.revision, document:original.document};
      this._sendImport = original.import_id || null; this._candidateDocument = this._sent = null;
      this._unsaved = true;
      this._restoredGeneration = null;
      this._caps = structuredClone(caps); this._room = doc.rooms[0].id;
      this._editing = null; this._fields = false; this._validation = this._modelValidation = this._changes = null; this._changesError = false; this._error = ''; this._version++;
      this._render(); this._notify();
    } catch (error) { this._error = error.code || 'failed'; this._controls(); }
  }
  clear(resetStorage = false) {
    this._closeEntities();
    this._draft = this._base = this._caps = this._validation = this._modelValidation = this._changes = null;
    this._changesError = false; this.$('draft-compare-base').value = 'original';
    this._room = ''; this._editing = null; this._fields = false; this._error = ''; this._version++;
    this._origin = null; this._unsaved = false;
    this._sendImport = this._candidateDocument = this._sent = null;
    this._restoredGeneration = null; this._historyError = '';
    if (resetStorage) { this._storeRevision = null; this._storeFresh = false; this._storeHasRecord = false; this._storeGeneration = 0; this._storeError = ''; this._checkpointDocument = null; this._historyItems = []; }
    for (const input of this.shadowRoot.querySelectorAll('input')) { input.value = ''; input.checked = false; }
    this.$('draft-widgets').replaceChildren(); this.$('draft-entities').replaceChildren(); this.$('draft-target').replaceChildren();
    this.$('draft-room').replaceChildren(); this._controls(); this._notify();
  }
  _storageEvent(operation, detail) { this.dispatchEvent(new CustomEvent('draft-storage-' + operation, {bubbles:true, composed:true, detail})); }
  invalidateStorage(code = '') { this._storeFresh = false; this._storeError = code; this._controls(); }
  acceptStored(result, restore = false, version = this._version) {
    if (restore) this.clear();
    this._storeRevision = result.revision; this._storeGeneration = result.generation;
    this._storeHasRecord = !!result.record; this._storeFresh = true; this._storeError = '';
    this._checkpointDocument = result.record?.document || null;
    this._historyItems = result.history || []; this._historyLimit = result.history_limits?.entries || 3; this._historyError = '';
    if (!this._checkpointDocument) this.$('draft-compare-base').value = 'original';
    if (restore && result.record) {
      try {
        const record = result.record, doc = JSON.parse(record.document);
        assertDraftBudget(doc, record.capabilities);
        this._draft = doc; this._origin = structuredClone(record.original);
        this._base = {source:this._origin.source, sha256:this._origin.sha256, revision:this._origin.revision};
        this._caps = structuredClone(record.capabilities); this._room = doc.rooms[0].id;
        this._unsaved = false; this._version++; this._validation = null; this._validationFresh = false;
        this._render();
      } catch { this._error = 'restoreInvalid'; }
    } else if (!restore && version === this._version) this._unsaved = false;
    this._controls(); this._notify();
    return !result.record || !!this._draft;
  }
  restoreHistory(result, detail) {
    if (this._version !== detail.version || !this._storeFresh || this._storeRevision !== detail.expected_revision ||
        result.revision !== detail.expected_revision || result.history_generation !== detail.history_generation) return false;
    try {
      const record = result.record, doc = JSON.parse(record.document);
      doc.revision = nextRevision(doc, Math.max(result.document_high_water || 0, this._draft?.revision || 0,
        this._context.revisionHighWater || 0, this._origin?.revision || 0));
      assertDraftBudget(doc, record.capabilities);
      const origin = structuredClone(record.original), caps = structuredClone(record.capabilities);
      this.clear();
      this._draft = doc; this._origin = origin; this._caps = caps;
      this._base = {source:origin.source, sha256:origin.sha256, revision:origin.revision};
      this._room = doc.rooms[0].id; this._unsaved = true; this._restoredGeneration = detail.history_generation;
      this._version++; this._render(); this._notify(); return true;
    } catch (error) {
      this._historyError = error.code || 'restoreInvalid'; this._controls(); return false;
    }
  }
  _renderHistory() {
    this.$('draft-history').hidden = !this._context.storageOnline && !this._historyItems.length;
    this.$('draft-history-count').textContent = `${this._historyItems.length} / ${this._historyLimit}`;
    this.$('draft-history-status').textContent = this._historyError ? this.t(this._historyError) :
      !this._storeFresh ? this.t('storageUnknown') : this._historyItems.length ? '' : this.t('historyEmpty');
    if (this._historyRendered !== this._historyItems || this._historyLanguage !== this._lang) {
      this._historyRendered = this._historyItems; this._historyLanguage = this._lang;
      this.$('draft-history-items').replaceChildren(...this._historyItems.map(item => {
        const row = document.createElement('div'), text = document.createElement('div'), title = document.createElement('strong'),
          time = document.createElement('time'), info = document.createElement('small'), button = document.createElement('button'), icon = document.createElement('ha-icon');
        row.className = 'draft-history-row'; row.dataset.generation = String(item.generation);
        title.textContent = `HA v${item.generation} \u00b7 r${item.document_revision}`;
        const date = item.saved_at == null ? null : new Date(item.saved_at);
        if (date && Number.isFinite(date.getTime())) {
          time.dateTime = date.toISOString(); time.textContent = new Intl.DateTimeFormat(this._lang, {dateStyle:'short', timeStyle:'short'}).format(date);
        } else time.textContent = this.t('unknownTime');
        info.textContent = `${item.sha256.slice(0, 12)} \u00b7 ${item.bytes.toLocaleString(this._lang)} ${this.t('bytes')}`; info.title = item.sha256;
        text.append(title, time, info); icon.setAttribute('icon', 'mdi:restore'); icon.textContent = '\u21b6';
        button.type = 'button'; button.title = button.ariaLabel = this.t('openHistory'); button.append(icon, this.t('openHistory'));
        button.onclick = () => {
          if (this._context.busy || !this._storeFresh || !this._context.storageOnline || !confirm(this.t('confirmHistory'))) return;
          this._storageEvent('history', {expected_revision:this._storeRevision, history_generation:item.generation, version:this._version});
        };
        row.append(text, button); return row;
      }));
    }
    for (const button of this.$('draft-history-items').querySelectorAll('button')) button.disabled = this._context.busy || !this._storeFresh || !this._context.storageOnline;
  }
  invalidate() { this._validationFresh = false; this._candidateDocument = null; this._controls(); }
  invalidateImport() { this._sendImport = null; this.invalidate(); }
  bindImport(original) {
    this._sendImport = this._origin && original.source === this._origin.source && original.sha256 === this._origin.sha256 &&
      original.revision === this._origin.revision && JSON.stringify(original.capabilities) === JSON.stringify(this._caps) ? original.import_id : null;
    this._sent = null; this.invalidate();
  }
  _canSend() {
    return this._context.canSend && this._sendImport && this._candidateDocument && this._validation?.valid &&
      this._validationFresh && this._validationVersion === this._version && this._context.fresh &&
      !this._context.busy && !this._fields && this._editing === null && !this._capsChanged();
  }
  acceptSent(receipt, version) {
    this.invalidateImport();
    if (version === this._version) this._sent = receipt;
    this._controls();
  }
  acceptValidation(report, version, candidateDocument = null) {
    if (!this._draft || this._version !== version) return;
    this._validation = report; this._validationVersion = version; this._validationFresh = true;
    this._candidateDocument = report.valid ? candidateDocument : null; this._controls();
  }
  acceptModelValidation(report, version) {
    if (!this._draft || this._version !== version) return;
    this._modelValidation = report; this._modelValidationVersion = version; this._controls();
  }
  _comparisonBase() { return this.$('draft-compare-base').value === 'saved' ? this._storeFresh && this._checkpointDocument : this._origin?.document; }
  acceptChanges(report, detail) {
    if (!this._draft || this._version !== detail.version || this._comparisonBase() !== detail.base || this.$('draft-compare-base').value !== detail.target) return;
    this._changes = report; this._changesVersion = detail.version; this._changesBase = detail.base; this._changesTarget = detail.target;
    this._changesError = false; this.$('draft-change-details').open = true; this._controls();
  }
  rejectChanges(detail) {
    if (!this._draft || this._version !== detail.version || this._comparisonBase() !== detail.base || this.$('draft-compare-base').value !== detail.target) return;
    this._changesError = true; this.$('draft-change-details').open = true; this._controls();
  }
  _renderChanges() {
    const result = this._changes;
    this.$('draft-change-details').hidden = !result && !this._changesError;
    const stale = this._fields || this._changesVersion !== this._version || this._changesBase !== this._comparisonBase() || this._changesTarget !== this.$('draft-compare-base').value;
    this.$('draft-change-status').textContent = this._changesError ? this.t('changesError') : !result ? '' :
      (stale ? this.t('previousChanges') + ': ' : '') + (result.total ? `${this.t('changesTotal')}: ${result.total}${result.truncated ? ` \u00b7 ${this.t('changesShown')}: ${result.items.length}` : ''}` : this.t('noChanges')) +
      ` \u00b7 ${this.t('revision')}: ${result.base_revision} \u2192 ${result.document_revision}`;
    if (this._changesRendered === result && this._changesLanguage === this._lang) return;
    this._changesRendered = result; this._changesLanguage = this._lang;
    this.$('draft-change-items').replaceChildren(...(result?.items || []).map(item => {
      const row = document.createElement('li'), title = document.createElement('strong'), name = document.createElement('span'), info = document.createElement('small');
      title.textContent = this.t(item.kind); name.textContent = item.name || (item.section ? this.t(item.section) : '');
      info.textContent = [item.from_room ? `${item.from_room} \u2192 ${item.room}` : item.room,
        item.id, item.fields?.map(field => this.t(field)).join(', ')].filter(Boolean).join(' \u00b7 ');
      row.append(title); if (name.textContent) row.append(name); if (info.textContent) row.append(info); return row;
    }));
  }
  _notify() { this.dispatchEvent(new CustomEvent('draft-changed', {bubbles:true, composed:true})); }
  _canLeave() { return !this._fields || confirm(this.t('discardFields')); }
  _capsChanged() { return this._caps && this._context.capabilities && JSON.stringify(this._caps) !== JSON.stringify(this._context.capabilities); }
  _edit(operation, selectLast = false) {
    if (!this._draft || this._context.busy || this._capsChanged()) return;
    try {
      this._draft = editDraft(this._draft, operation, this._caps);
      this._candidateDocument = this._sent = null;
      this._version++; this._unsaved = true; this._validationFresh = false; this._error = ''; this._fields = false; this._editing = null;
      if (selectLast) this._room = this._draft.rooms.at(-1).id;
      if (!this._draft.rooms.some(r => r.id === this._room)) this._room = this._draft.rooms[0].id;
      if (['put_action', 'put_sensor', 'put_status'].includes(operation.type)) this._room = operation.target;
      this._render(); this._notify();
    } catch (error) { this._error = error.code || 'failed'; this._controls(); }
  }
  _button(glyph, key, handler) {
    const button = document.createElement('button'), icon = document.createElement('ha-icon');
    button.type = 'button'; button.className = 'icon'; button.title = button.ariaLabel = this.t(key);
    icon.setAttribute('icon', 'mdi:' + glyph); icon.textContent = glyph === 'arrow-up' ? '\u2191' : glyph === 'arrow-down' ? '\u2193' : '\u00d7';
    button.append(icon); button.onclick = handler; return button;
  }
  _render() {
    if (!this._draft) { this._controls(); return; }
    const room = this._draft.rooms.find(r => r.id === this._room);
    this.$('draft-room').replaceChildren(...this._draft.rooms.map(r => new Option(r.name, r.id)));
    this.$('draft-room').value = room.id; this.$('draft-room-name').value = room.name; this.$('draft-room-kind').value = room.kind || 'room';
    this.$('draft-room-id').textContent = room.id;
    this.$('draft-widgets').replaceChildren(...room.widgets.map((widget, index) => {
      const row = document.createElement('div'); row.className = 'draft-widget'; row.dataset.widgetId = widget.id;
      const edit = document.createElement('button'), name = document.createElement('strong'), entity = document.createElement('small'), glyph = document.createElement('ha-icon');
      const reading = editableReading(widget, this._caps) && editableRoom(room, this._caps), supported = reading || editableAction(widget, this._caps);
      const type = reading ? widget.type : 'action';
      edit.type = 'button'; edit.className = 'draft-widget-main'; edit.disabled = !supported;
      glyph.setAttribute('icon', 'mdi:' + (type === 'status' ? 'circle-half-full' : reading ?
        widget.settings.device_class === 'humidity' ? 'water-percent' : 'thermometer' : supported ? icons[widget.settings.icon] || 'gesture-tap-button' : 'lock-outline'));
      glyph.textContent = supported ? '\u25c7' : '\u2014';
      name.textContent = widget.settings.name; entity.textContent = [widget.settings.entity || widget.type, reading && widget.settings.group &&
        (Object.hasOwn(room.groups, widget.settings.group) && room.groups[widget.settings.group].name || widget.settings.group)].filter(Boolean).join(' \u00b7 ');
      const text = document.createElement('span'); text.append(name, entity); edit.append(glyph, text); edit.onclick = () => reading ? this._openSensor(widget.id, type) : this._openAction(widget.id);
      const tools = document.createElement('div'); tools.className = 'draft-widget-tools';
      for (const [offset, glyph, label] of [[-1, 'arrow-up', 'up'], [1, 'arrow-down', 'down']]) {
        const button = this._button(glyph, label, () => this._edit({type:'move_' + type, room:room.id, id:widget.id, offset}));
        button.dataset.blocked = String(!supported || index + offset < 0 || index + offset >= room.widgets.length); tools.append(button);
      }
      const remove = this._button('trash-can-outline', 'delete', () => { if (confirm(this.t(reading ? 'deleteSensor' : 'deleteAction'))) this._edit({type:'delete_' + type, room:room.id, id:widget.id}); });
      remove.dataset.blocked = String(!supported); tools.append(remove); row.append(edit, tools); return row;
    }));
    this.$('draft-action-form').hidden = this._editing === null || this._editingKind !== 'action';
    this.$('draft-sensor-form').hidden = this._editing === null || this._editingKind === 'action';
    this._controls();
  }
  _openAction(id) {
    if (!this._canLeave()) return;
    const room = this._draft.rooms.find(r => r.id === this._room);
    const settings = id ? room.widgets.find(w => w.id === id).settings : {name:'', entity:'', icon:this._caps.validation.action_icons[0], interaction:'tap', enabled:true};
    this._editing = id || ''; this._editingKind = 'action'; this._fields = false;
    this.$('draft-action-name').value = settings.name; this.$('draft-entity').value = settings.entity;
    this.$('draft-icon').replaceChildren(...this._caps.validation.action_icons.map(i => new Option(i, i)));
    this.$('draft-interaction').replaceChildren(...this._caps.validation.interactions.map(i => new Option(this.t(i), i)));
    this.$('draft-icon').value = settings.icon || this._caps.validation.action_icons[0]; this.$('draft-interaction').value = settings.interaction || 'tap';
    this.$('draft-enabled').checked = settings.enabled !== false; this.$('draft-stop').checked = settings.allow_stop === true;
    const targets = this._draft.rooms.filter(r => editableRoom(r, this._caps));
    this.$('draft-target').replaceChildren(...targets.map(r => new Option(r.name, r.id)));
    this.$('draft-target').value = room.id;
    if (!id && room.kind !== 'actions' && room.widgets.every(w => w.type === 'action') && room.widgets.length >= actionCapacity(this._draft)) {
      this.$('draft-target').value = targets.find(r => r.kind === 'actions')?.id || room.id;
    }
    this.$('draft-entities').replaceChildren(...Object.entries(this._entityStates || {}).filter(([id]) => /^(script|scene|button|input_button)\./.test(id)).slice(0, 50).map(([id, state]) => new Option(state.attributes.friendly_name || id, id)));
    this.$('draft-action-form').hidden = false;
    this.$('draft-sensor-form').hidden = true;
    this._stopField(); this._controls(); this.$('draft-action-name').focus();
  }
  _stopField() {
    this.$('draft-stop-field').hidden = !this._caps?.features.includes('script-controls.v1') || !this.$('draft-entity').value.startsWith('script.');
  }
  _openSensor(id, kind = 'sensor') {
    if (!this._canLeave() || !this._draft || this._capsChanged()) return;
    const room = this._draft.rooms.find(r => r.id === this._room);
    if (!editableRoom(room, this._caps) || room.kind === 'actions' || !supportsReading(kind, this._caps)) return;
    const settings = id ? room.widgets.find(w => w.id === id).settings : {name:'', entity:''};
    const binary = kind === 'status', domain = catalogDomains[kind][0];
    this._editing = id || ''; this._editingKind = kind; this._fields = false; this._newGroupId = identity('group');
    this.$('draft-sensor-entity').pattern = domain + '\\.[a-z0-9_]+';
    this.$('draft-sensor-unit').closest('label').hidden = binary;
    this.$('draft-sensor-group').closest('label').hidden = binary;
    this.$('draft-sensor-classes').replaceChildren(...(binary ? ['problem', 'motion', 'door', 'window'] : ['temperature', 'humidity']).map(value => new Option(value)));
    for (const [field, value] of [['name', settings.name], ['entity', settings.entity], ['unit', settings.unit], ['class', settings.device_class]]) this.$('draft-sensor-' + field).value = value || '';
    this.$('draft-sensor-target').replaceChildren(...this._draft.rooms.filter(r => r.kind !== 'actions' && editableRoom(r, this._caps)).map(r => new Option(r.name, r.id)));
    this.$('draft-sensor-target').value = room.id;
    if (binary) this.$('draft-group-name-field').hidden = true;
    else this._sensorGroups(settings.group || '');
    this.$('draft-sensor-entities').replaceChildren(...Object.entries(this._entityStates || {}).filter(([id]) => id.startsWith(domain + '.')).slice(0, 50).map(([id, state]) => new Option(state.attributes.friendly_name || id, id)));
    this.$('draft-action-form').hidden = true; this.$('draft-sensor-form').hidden = false;
    this._controls(); this.$('draft-sensor-name').focus();
  }
  _sensorGroups(selected) {
    const room = this._draft.rooms.find(r => r.id === this.$('draft-sensor-target').value);
    const source = this._draft.rooms.find(r => r.id === this._room);
    const ids = Object.keys(room.groups);
    if (selected && selected !== '@new' && !ids.includes(selected)) ids.push(selected);
    this.$('draft-sensor-group').replaceChildren(new Option(this.t('ungrouped'), ''), ...ids.map(id =>
      new Option((Object.hasOwn(room.groups, id) ? room.groups[id].name : Object.hasOwn(source.groups, id) ? source.groups[id].name : '') || id, id)),
      new Option(this.t('newGroup'), '@new'));
    this.$('draft-sensor-group').value = selected;
    this._sensorGroupField();
  }
  _sensorGroupField() {
    const id = this.$('draft-sensor-group').value;
    const target = this._draft?.rooms.find(r => r.id === this.$('draft-sensor-target').value);
    const source = this._draft?.rooms.find(r => r.id === this._room);
    this.$('draft-group-name').value = id && target ? (Object.hasOwn(target.groups, id) ? target.groups[id].name : Object.hasOwn(source.groups, id) ? source.groups[id].name : '') || '' : '';
    this.$('draft-group-name-field').hidden = !id;
  }
  _sensorDefaults(attributes) {
    if (!attributes) return;
    for (const [field, value] of [['name', attributes.friendly_name], ['unit', attributes.unit_of_measurement], ['class', attributes.device_class]]) {
      if (field === 'unit' && this._editingKind === 'status') continue;
      if (!this.$('draft-sensor-' + field).value && typeof value === 'string' &&
          !/[\x00-\x1f\x7f-\x9f]/.test(value) && new TextEncoder().encode(value).length <= this._caps.limits.string_bytes) this.$('draft-sensor-' + field).value = value;
    }
  }
  _openEntities(kind) {
    if (!this._context.storageOnline || this._context.busy || this._editing === null || this._capsChanged()) return;
    this._entityKind = kind;
    this._catalog = null; this._catalogError = false;
    this.$('entity-query').value = '';
    this.$('entity-domain').replaceChildren(new Option(this.t('all'), ''), ...catalogDomains[kind].map(d => new Option(d, d)));
    this.$('entity-area').replaceChildren(new Option(this.t('all'), ''), new Option(this.t('unassigned'), '@none'));
    this.$('entity-inactive').checked = false;
    this.$('entity-results').replaceChildren(); this.$('entity-areas-warning').hidden = true;
    this.$('entity-picker').showModal(); this._searchEntities(); this.$('entity-query').focus();
  }
  _closeEntities() {
    this._catalogRequest++; this._catalogPending = false;
    if (this.$('entity-picker').open) {
      this.$('entity-picker').close();
      if (this.isConnected) this.$(this._entityKind === 'action' ? 'draft-choose-entity' : 'draft-choose-sensor').focus();
    }
  }
  _searchEntities(offset = 0) {
    if (!this.$('entity-picker').open || this._context.busy || !this._context.storageOnline) return;
    const area = this.$('entity-area').value;
    this._catalogPending = true; this._catalogError = false;
    this.$('entity-results').replaceChildren();
    this.dispatchEvent(new CustomEvent('draft-entities', {bubbles:true, composed:true, detail:{
      request:++this._catalogRequest, query:{scope:this._entityKind, query:this.$('entity-query').value.trim(), domain:this.$('entity-domain').value,
        area_id:area === '@none' ? null : area.startsWith('id:') ? area.slice(3) : '',
        include_inactive:this.$('entity-inactive').checked, offset, limit:25}}}));
    this._catalogControls();
  }
  acceptEntities(result, request) {
    if (!this.$('entity-picker').open || request !== this._catalogRequest) return;
    this._catalogPending = false; this._catalog = result;
    const selectedArea = this.$('entity-area').value;
    this.$('entity-area').replaceChildren(new Option(this.t('all'), ''), new Option(this.t('unassigned'), '@none'),
      ...result.areas.map(area => new Option(area.name, 'id:' + area.id)));
    this.$('entity-area').value = selectedArea;
    this.$('entity-areas-warning').hidden = !result.areas_truncated;
    this.$('entity-results').replaceChildren(...result.items.map(item => {
      const button = document.createElement('button'), text = document.createElement('span'), name = document.createElement('strong'),
        description = document.createElement('small'), icon = document.createElement('ha-icon');
      button.type = 'button'; button.className = 'entity-result'; button.dataset.entity = item.entity_id;
      icon.setAttribute('icon', 'mdi:' + ({script:'script-text-outline', scene:'palette-outline', button:'gesture-tap-button', input_button:'gesture-tap-button', sensor:'thermometer', binary_sensor:'circle-half-full'}[item.domain]));
      icon.textContent = '\u25c7'; name.textContent = item.name;
      description.textContent = [item.entity_id, item.area_name, item.disabled && this.t('disabled'), item.hidden && this.t('hidden'),
        item.availability !== 'available' && this.t({missing:'missingState', unavailable:'unavailable', unknown:'unknown'}[item.availability])].filter(Boolean).join(' \u00b7 ');
      text.append(name, description); button.append(icon, text);
      button.onclick = () => {
        if (this._context.busy || this._editing === null || this._capsChanged()) return;
        if (this._entityKind !== 'action') {
          this.$('draft-sensor-entity').value = item.entity_id;
          this._sensorDefaults({friendly_name:item.name, unit_of_measurement:item.defaults?.unit, device_class:item.defaults?.device_class});
        } else {
          this.$('draft-entity').value = item.entity_id;
          if (!this.$('draft-action-name').value.trim()) this.$('draft-action-name').value = item.name;
        }
        this._fields = true; this._stopField(); this._closeEntities(); this._controls();
      };
      return button;
    }));
    this._catalogControls();
  }
  rejectEntities(request) {
    if (!this.$('entity-picker').open || request !== this._catalogRequest) return;
    this._catalogPending = false; this._catalogError = true; this._catalog = null; this._catalogControls();
  }
  _catalogControls() {
    if (!this.$('entity-picker').open) return;
    this.$('entity-domain').options[0].text = this.t('all');
    const pending = this._catalogPending || this._context.busy, result = this._catalog;
    this.$('entity-results').setAttribute('aria-busy', String(!!this._catalogPending));
    this.$('entity-results-status').textContent = this._catalogPending ? this.t('loading') : this._catalogError ? this.t('catalogError') : result?.items.length ? '' : this.t('noEntities');
    this.$('entity-page').textContent = result?.items.length ? `${result.offset + 1}\u2013${result.offset + result.items.length} / ${result.total}` : '';
    this.$('entity-previous').disabled = pending || !result || result.offset === 0;
    this.$('entity-next').disabled = pending || result?.next_offset == null;
    for (const control of this.$('entity-search-form').querySelectorAll('input, select, button')) control.disabled = pending;
    for (const button of this.$('entity-results').querySelectorAll('button')) button.disabled = pending;
    this.$('entity-cancel').disabled = false;
  }
  _controls() {
    const root = this.shadowRoot, blocked = !!this._context.busy;
    root.querySelectorAll('[data-label]').forEach(e => { e.textContent = this.t(e.dataset.label); });
    root.querySelectorAll('[data-tool]').forEach(e => { e.title = e.ariaLabel = this.t(e.dataset.tool); });
    this.$('draft-empty').textContent = this.t('empty'); this.$('draft-empty').hidden = !!this._draft;
    this.$('draft-work').hidden = !this._draft;
    this._renderChanges();
    const formOpen = this._editing !== null;
    this.$('draft-save-ha').disabled = blocked || !this._context.storageOnline || !this._storeFresh || !this._draft || !this._unsaved || this._fields || formOpen;
    this.$('draft-load-ha').disabled = blocked || !this._context.storageOnline;
    this.$('draft-delete-ha').disabled = blocked || !this._context.storageOnline || !this._storeFresh || !this._storeHasRecord;
    this.$('draft-storage-status').textContent = this._storeError === 'draft_conflict' ? this.t('conflict') :
      !this._storeFresh ? this.t('storageUnknown') : this._unsaved || this._fields ? this.t('unsaved') :
      this._storeHasRecord ? `${this.t('savedHA')} \u00b7 v${this._storeGeneration}` : '';
    this._renderHistory();
    if (!this._draft) return;
    const room = this._draft.rooms.find(r => r.id === this._room), index = this._draft.rooms.indexOf(room);
    const cap = actionCapacity(this._draft);
    const opaque = !editableRoom(room, this._caps), readings = room.widgets.some(w => w.type === 'sensor' || w.type === 'status');
    const plan = roomPlan(this._draft, room, this._caps);
    this.$('draft-base').textContent = `${this.t('local')} r${this._draft.revision} \u00b7 ${this._base.source} r${this._base.revision}` + (this._restoredGeneration ? ` \u00b7 ${this.t('history')} v${this._restoredGeneration}` : '');
    this.$('draft-fit').textContent = opaque ? this.t('readOnly') : readings ? `${plan.height} / ${plan.available} ${this.t('pixels')}` : `${room.widgets.length} / ${cap} ${this.t('tiles')} \u00b7 ${plan.pages} ${this.t('pages')}`;
    const stale = !this._validationFresh || this._validationVersion !== this._version || !this._context.fresh;
    this.$('draft-status').textContent = [this._fields && this.t('pending'), this._context.sourceCurrent === false && this.t('changedSource'), this._capsChanged() && this.t('changedCaps'),
      'ESP32: ' + (this._validation ? `${stale ? this.t('previous') + ': ' : ''}${this.t(this._validation.valid ? 'accepted' : 'rejected')}` : this.t('notChecked'))].filter(Boolean).join(' \u00b7 ');
    this.$('draft-status').className = 'report ' + (this._validation && !stale ? this._validation.valid ? 'success' : 'warning' : 'muted');
    this.$('draft-send-status').hidden = !this._sent || this._fields;
    this.$('draft-send-status').textContent = this._sent ? `${this.t('sentCandidate')} \u00b7 r${this._sent.revision} \u00b7 ${this._sent.sha256.slice(0, 12)}` : '';
    const modelStale = this._fields || this._modelValidationVersion !== this._version;
    this.$('draft-model-status').textContent = this.t('hostModel') + ': ' + (this._modelValidation ?
      `${modelStale ? this.t('previous') + ': ' : ''}${this.t(this._modelValidation.valid ? 'accepted' : 'rejected')}` : this.t('notChecked'));
    this.$('draft-model-status').className = 'report ' + (this._modelValidation && !modelStale ? this._modelValidation.valid ? 'success' : 'warning' : 'muted');
    this.$('draft-error').hidden = !this._error; this.$('draft-error').textContent = this.t(this._error === 'entity' ? 'entityError' : this._error === 'group' ? 'groupError' : this._error || 'failed');
    for (const e of root.querySelectorAll('button, input, select')) e.disabled = blocked;
    this.$('draft-save-ha').disabled = blocked || !this._context.storageOnline || !this._storeFresh || !this._unsaved || this._fields || formOpen;
    this.$('draft-load-ha').disabled = blocked || !this._context.storageOnline;
    this.$('draft-delete-ha').disabled = blocked || !this._context.storageOnline || !this._storeFresh || !this._storeHasRecord;
    for (const id of ['draft-add-room', 'draft-room-up', 'draft-room-down', 'draft-delete-room', 'draft-add-action', 'draft-add-sensor', 'draft-add-status']) this.$(id).disabled = blocked || this._fields || formOpen || this._capsChanged();
    this.$('draft-add-room').disabled ||= this._draft.rooms.length >= this._caps.limits.rooms;
    this.$('draft-room-up').disabled ||= index === 0; this.$('draft-room-down').disabled ||= index === this._draft.rooms.length - 1;
    this.$('draft-delete-room').disabled ||= this._draft.rooms.length === 1 || !!opaque;
    const full = this._draft.rooms.reduce((n, r) => n + r.widgets.length, 0) >= this._caps.limits.widgets;
    this.$('draft-add-action').disabled ||= opaque || !this._caps.features.includes('widget.action') || full;
    for (const kind of ['sensor', 'status']) {
      this.$('draft-add-' + kind).hidden = kind === 'status' && !supportsReading(kind, this._caps);
      this.$('draft-add-' + kind).disabled ||= opaque || room.kind === 'actions' || !supportsReading(kind, this._caps) || full;
    }
    this.$('draft-update-room').disabled = blocked || !this._fields || formOpen || this._capsChanged(); this.$('draft-cancel-room').disabled = blocked || !this._fields || formOpen;
    this.$('draft-room-name').disabled = blocked || formOpen || this._capsChanged(); this.$('draft-room-kind').disabled = blocked || formOpen || !!opaque || this._capsChanged();
    this.$('draft-room-kind').querySelector('[value="actions"]').disabled = readings || !this._caps.features.includes('action-pages.v1');
    for (const button of root.querySelectorAll('#draft-widgets button')) {
      const widget = room.widgets.find(w => w.id === button.parentElement.dataset.widgetId);
      button.disabled = blocked || this._fields || formOpen || this._capsChanged() || button.dataset.blocked === 'true' ||
        (button.classList.contains('draft-widget-main') && !editableAction(widget, this._caps) && !(editableReading(widget, this._caps) && !opaque));
    }
    this.$('draft-check').disabled = blocked || this._fields || formOpen || !this._context.canValidate || this._capsChanged();
    this.$('draft-send').disabled = !this._canSend();
    this.$('draft-model-check').disabled = blocked || this._fields || formOpen || !this._context.storageOnline;
    this.$('draft-changes').disabled = blocked || this._fields || formOpen || !this._context.storageOnline || !this._comparisonBase();
    this.$('draft-compare-base').disabled = blocked || this._fields || formOpen;
    this.$('draft-compare-base').querySelector('[value="saved"]').disabled = !this._storeFresh || !this._checkpointDocument;
    this.$('draft-export').disabled = blocked || this._fields || formOpen;
    this.$('draft-update-action').disabled = blocked || this._capsChanged();
    this.$('draft-update-sensor').disabled = blocked || this._capsChanged();
    this.$('draft-choose-sensor').disabled = blocked || !this._context.storageOnline || this._capsChanged();
    this.$('draft-sensor-group').disabled = blocked || this._capsChanged() || !this._caps.features.includes('sensor-groups.v1');
    this.$('draft-choose-entity').disabled = blocked || !this._context.storageOnline || this._capsChanged();
    this._renderHistory();
    this._catalogControls();
    this._stopField();
  }
  _export() {
    if (!this._draft || this._fields || this._editing !== null || this._context.busy) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(normalizedDraft(this._draft))], {type:'application/json'}));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `panel-draft-r${this._draft.revision}.json`; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}
if (!customElements.get('home-panel-draft')) customElements.define('home-panel-draft', HomePanelDraft);
