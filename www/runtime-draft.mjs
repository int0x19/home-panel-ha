// Logical edits only. The shared native validator remains authoritative.
const OWNED_FEATURES = ['widget.action', 'action-pages.v1', 'script-controls.v1'];
const ACTION_FIELDS = new Set(['entity', 'name', 'icon', 'interaction', 'enabled', 'allow_stop']);
const ENTITY = /^(script|scene|button|input_button)\.[a-z0-9_]+$/;
const ID = /^[a-z_][a-z0-9_]{0,63}$/;
export class DraftError extends Error {
  constructor(code) { super(code); this.code = code; }
}
const fail = code => { throw new DraftError(code); };
export function identity(prefix) {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  return prefix + '_' + [...bytes].map(b => b.toString(16).padStart(2, '0')).join('');
}
export function move(items, from, to) {
  if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0 || from >= items.length || to >= items.length) return;
  items.splice(to, 0, items.splice(from, 1)[0]);
}
export function normalizedDraft(document) {
  const doc = structuredClone(document);
  doc.requires = [...new Set([...doc.requires.filter(f => !OWNED_FEATURES.includes(f)),
    ...(doc.rooms.some(r => r.widgets.some(w => w.type === 'action')) ? ['widget.action'] : []),
    ...(doc.rooms.some(r => r.kind === 'actions') ? ['action-pages.v1'] : []),
    ...(doc.rooms.some(r => r.widgets.some(w => w.type === 'action' && Object.hasOwn(w.settings, 'allow_stop'))) ? ['script-controls.v1'] : [])])].sort();
  return doc;
}
export function nextRevision(document, highWater) {
  const value = Math.max(document.revision, highWater);
  if (!Number.isInteger(value) || value < 1 || value >= 0xffffffff) fail('revision_limit');
  return value + 1;
}
export function actionCapacity(document) {
  const s = document.style.layout;
  const keys = ['page_padding', 'header_height', 'nav_button_height', 'control_row_padding', 'page_gap',
    'navigation_gap', 'card_gap', 'light_card_height', 'light_tile_columns'];
  if (keys.some(k => !Number.isInteger(s[k]) || s[k] < 0 || s[k] > 4096) || !s.light_card_height || !s.light_tile_columns) fail('geometry');
  const available = 480 - 2 * s.page_padding - s.header_height - s.nav_button_height -
    2 * s.control_row_padding - s.page_gap - s.navigation_gap;
  return Math.max(0, Math.floor((available + s.card_gap) / (s.light_card_height + s.card_gap))) * s.light_tile_columns;
}
export function editableAction(widget, caps) {
  return widget?.type === 'action' && Object.keys(widget.settings).every(k => ACTION_FIELDS.has(k)) &&
    ENTITY.test(widget.settings.entity) && (!widget.settings.icon || caps.validation.action_icons.includes(widget.settings.icon)) &&
    (!widget.settings.interaction || caps.validation.interactions.includes(widget.settings.interaction));
}
function text(value, maximum) {
  if (typeof value !== 'string' || !value.trim() || /[\x00-\x1f\x7f-\x9f]/.test(value) ||
      [...value].some(c => c.length === 1 && c.charCodeAt(0) >= 0xd800 && c.charCodeAt(0) <= 0xdfff) ||
      new TextEncoder().encode(value).length > maximum) fail('text');
}
function feature(caps, name) { if (!caps.features.includes(name)) fail('capability'); }
function actionSettings(settings, caps) {
  if (!settings || Object.keys(settings).some(k => !ACTION_FIELDS.has(k))) fail('action_fields');
  text(settings.name, caps.limits.string_bytes);
  if (!ENTITY.test(settings.entity) || settings.entity.length > 127) fail('entity');
  if (!caps.validation.action_icons.includes(settings.icon) || !caps.validation.interactions.includes(settings.interaction) ||
      typeof settings.enabled !== 'boolean') fail('action_fields');
  if (Object.hasOwn(settings, 'allow_stop')) {
    feature(caps, 'script-controls.v1');
    if (!settings.entity.startsWith('script.') || typeof settings.allow_stop !== 'boolean') fail('action_fields');
  }
}
function knownRoom(room) {
  if (!['room', 'actions'].includes(room.kind || 'room') || Object.keys(room.groups).length || room.widgets.some(w => w.type !== 'action')) fail('opaque_room');
}
export function assertDraftBudget(doc, caps) {
  if (doc.rooms.length < 1 || doc.rooms.length > caps.limits.rooms) fail('room_limit');
  const count = doc.rooms.reduce((n, r) => n + r.widgets.length, 0) + (doc.views || []).reduce((n, v) => n + v.definition.widgets.length, 0);
  if (count > caps.limits.widgets) fail('widget_limit');
  const capacity = actionCapacity(doc);
  let pages = 0;
  for (const room of doc.rooms) {
    if (room.widgets.some(w => w.type !== 'action') || Object.keys(room.groups).length) { pages++; continue; }
    if (!capacity && room.widgets.length) fail('geometry');
    if (room.kind !== 'actions' && room.widgets.length > capacity) fail('room_full');
    pages += room.kind === 'actions' ? Math.max(1, Math.ceil(room.widgets.length / (capacity || 1))) : 1;
  }
  if (pages > caps.limits.room_pages) fail('page_limit');
  if (new TextEncoder().encode(JSON.stringify(doc)).length > caps.limits.document_bytes) fail('byte_limit');
}

export function editDraft(document, operation, caps) {
  const doc = structuredClone(document);
  const room = doc.rooms.find(r => r.id === operation.room);
  if (operation.type !== 'add_room' && !room) fail('missing');
  switch (operation.type) {
    case 'add_room': {
      if (!ID.test(operation.id) || doc.rooms.some(r => r.id === operation.id)) fail('identity');
      text(operation.name, caps.limits.string_bytes);
      if (!['room', 'actions'].includes(operation.kind)) fail('capability');
      feature(caps, operation.kind === 'actions' ? 'action-pages.v1' : 'rooms.v1');
      doc.rooms.push({id:operation.id, name:operation.name, ...(operation.kind === 'actions' ? {kind:'actions'} : {}), groups:{}, widgets:[]});
      break;
    }
    case 'room_settings':
      text(operation.name, caps.limits.string_bytes);
      if ((room.kind || 'room') !== operation.kind) {
        knownRoom(room);
        if (!['room', 'actions'].includes(operation.kind)) fail('capability');
        feature(caps, operation.kind === 'actions' ? 'action-pages.v1' : 'rooms.v1');
        if (operation.kind === 'actions') room.kind = 'actions'; else delete room.kind;
      }
      room.name = operation.name;
      break;
    case 'move_room': {
      const index = doc.rooms.indexOf(room);
      move(doc.rooms, index, index + operation.offset);
      break;
    }
    case 'delete_room':
      knownRoom(room);
      if (doc.attention?.sources?.some(s => s.room === room.id)) fail('referenced_room');
      doc.rooms.splice(doc.rooms.indexOf(room), 1);
      break;
    case 'move_action':
    case 'delete_action': {
      const index = room.widgets.findIndex(w => w.id === operation.id);
      if (index < 0 || !editableAction(room.widgets[index], caps)) fail('opaque_action');
      if (operation.type === 'move_action') move(room.widgets, index, index + operation.offset);
      else room.widgets.splice(index, 1);
      break;
    }
    case 'put_action': {
      feature(caps, 'widget.action');
      actionSettings(operation.settings, caps);
      const previous = operation.previous ? room.widgets.find(w => w.id === operation.previous) : null;
      if (operation.previous && !editableAction(previous, caps)) fail('opaque_action');
      const target = doc.rooms.find(r => r.id === operation.target);
      if (!target) fail('missing');
      knownRoom(target);
      const id = previous?.id || operation.id;
      if (!ID.test(id)) fail('identity');
      if (target.widgets.some(w => w !== previous && (w.id === id || w.settings.entity === operation.settings.entity))) fail('duplicate');
      const widget = previous ? structuredClone(previous) : {id, type:'action'};
      widget.settings = structuredClone(operation.settings);
      const oldIndex = previous ? room.widgets.indexOf(previous) : -1;
      if (previous) room.widgets.splice(oldIndex, 1);
      if (previous && target === room) target.widgets.splice(oldIndex, 0, widget); else target.widgets.push(widget);
      break;
    }
    default: fail('operation');
  }
  const result = normalizedDraft(doc);
  assertDraftBudget(result, caps);
  return result;
}
