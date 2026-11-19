/* No Decky, framework runtime, external assets, or CDN dependencies. */
const $ = id => document.getElementById(id);
const launch = new URLSearchParams(location.hash.slice(1));
const token = launch.get('token') || '';
document.body.classList.toggle('sidebar', launch.get('sidebar') === '1');
history.replaceState(null, '', location.pathname);
let initialized = false, pending = false, writeAllowed = false, rgbDirty = false;
const fmt = (v, digits = 1) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
function notice(message, error = false) { $('notice').textContent = message; $('notice').classList.toggle('error', error); }
async function api(path, body) {
  const result = await fetch('/api/' + path, {method: body ? 'POST' : 'GET', headers: {Authorization: 'Bearer ' + token, ...(body ? {'Content-Type':'application/json'} : {})}, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(5000)});
  const data = await result.json(); if (!result.ok) throw Error(data.error || 'Request failed'); return data;
}
function selectPage(name) {
  document.querySelectorAll('.tab').forEach(e => e.classList.toggle('active', e.dataset.page === name));
  document.querySelectorAll('.page').forEach(e => e.classList.toggle('active', e.id === name));
}
document.querySelectorAll('[data-page]').forEach(e => e.onclick = () => selectPage(e.dataset.page));
function labels() { for (const id of ['sustained', 'boost', 'brightness', 'speed']) $(id + '-value').textContent = $(id).value + (['sustained','boost'].includes(id) ? ' W' : id === 'brightness' ? '%' : ''); }
for (const id of ['sustained', 'boost', 'brightness', 'speed']) $(id).oninput = () => {
  if (+$('boost').value < +$('sustained').value) $('boost').value = $('sustained').value;
  labels();
  if (id === 'brightness' || id === 'speed') {rgbDirty = true; lightingEditor();}
};
document.querySelectorAll('[data-preset]').forEach(e => e.onclick = () => {
  const [sustained, boost] = e.dataset.preset.split(','); $('sustained').value = sustained; $('boost').value = boost; labels();
  document.querySelectorAll('[data-preset]').forEach(b => b.classList.toggle('selected', b === e));
});
function locks() { document.querySelectorAll('.write').forEach(b => b.disabled = pending || !writeAllowed); }
async function apply(path, payload) {
  pending = true; locks();
  try {
    const response = await api(path, payload);
    if (path === 'rgb') {rgbDirty = false; lightingControls(response);}
    notice(path === 'power' ? response.status : !response.enabled ? 'Lighting is off. Colour and effect changes will not be visible.' : response.brightness === 0 ? 'Lighting brightness is zero. Increase brightness to see the lights.' : 'Lighting enabled. Settings updated.');
    await refresh();
  }
  catch (error) { notice(error.message, true); }
  finally { pending = false; locks(); }
}
$('apply-power').onclick = () => apply('power', {sustained_w: +$('sustained').value, boost_w: +$('boost').value,remember:$('remember-power').checked});
const effectNames = {monocolor:'Solid colour',breathe:'Breathe',chroma:'Chroma',rainbow:'Rainbow',frostfire:'Frostfire'};
function lightingEditor() {
  const on = $('rgb-enabled').checked, brightness = +$('brightness').value, solid = ['monocolor','breathe'].includes($('effect').value);
  $('apply-rgb').textContent = on ? 'Apply lighting · On' : 'Apply lighting · Off';
  $('lighting-help').textContent = !on ? 'Lighting will stay off when you apply. Enable it above, or press Turn lighting on.' : brightness === 0 ? 'Brightness is zero. Increase it to make lighting visible.' : 'Your changes become visible when you press Apply.';
  $('color').disabled = !solid;
  for(const channel of ['r','g','b']) $('channel-'+channel).disabled = !solid;
  $('color-help').textContent = solid ? 'Use the colour picker or adjust Red, Green and Blue with the D-pad.' : 'This effect uses its own colours. Choose Solid colour or Breathe to set a colour.';
  $('speed').disabled = $('effect').value === 'monocolor';
}
function lightingControls(rgb) {
  if ([...$('effect').options].map(o=>o.value).join(',') !== rgb.effects.join(',')) $('effect').replaceChildren(...rgb.effects.map(v => Object.assign(document.createElement('option'), {value:v,textContent:effectNames[v] || v})));
  $('effect').value = rgb.effect; $('rgb-enabled').checked = rgb.enabled;
  if (rgb.brightness != null) $('brightness').value = rgb.brightness;
  if (rgb.speed != null) $('speed').value = rgb.speed;
  if (rgb.color.length === 3) $('color').value = '#' + rgb.color.map(v => Math.round(v / 100 * 255).toString(16).padStart(2,'0')).join('');
  labels(); colorChannels(); lightingEditor();
}
function colorChannels() {
  const values=$('color').value.slice(1).match(/../g).map(v=>Math.round(parseInt(v,16)/255*100));
  ['r','g','b'].forEach((channel,i)=>{$('channel-'+channel).value=values[i];$('channel-'+channel+'-value').textContent=values[i]+'%';});
}
for(const channel of ['r','g','b']) $('channel-'+channel).oninput=()=>{
  rgbDirty=true;
  $('color').value='#'+['r','g','b'].map(c=>Math.round(+$('channel-'+c).value/100*255).toString(16).padStart(2,'0')).join('');
  colorChannels(); lightingEditor();
};
function applyLighting() { return apply('rgb', {enabled: $('rgb-enabled').checked, brightness: +$('brightness').value, speed: +$('speed').value, effect: $('effect').value, color: $('color').value.slice(1).match(/../g).map(v => Math.round(parseInt(v,16) / 255 * 100)),remember:$('remember-rgb').checked}); }
$('apply-rgb').onclick = applyLighting;
$('enable-rgb').onclick = () => { $('rgb-enabled').checked = true; if (+$('brightness').value === 0) $('brightness').value = 35; lightingEditor(); return applyLighting(); };
for (const id of ['effect','color','rgb-enabled']) $(id).onchange = () => {rgbDirty = true; if(id==='color')colorChannels(); lightingEditor();};
$('color').oninput = () => {rgbDirty = true; colorChannels(); lightingEditor();};
async function refresh() {
  try {
    const state = await api('state'), t = state.telemetry, rgb = state.rgb;
    writeAllowed = state.writes_enabled; locks(); $('connection').textContent = 'Connected';
    $('watts').replaceChildren(document.createTextNode(fmt(t.package_w)), Object.assign(document.createElement('small'), {textContent:' W'}));
    $('temperature').textContent = fmt(t.package_temperature_c, 0) + ' °C';
    $('battery').textContent = t.battery ? `${t.battery.percent}% · ${t.battery.status}` : 'Battery unavailable';
    $('flow').textContent = t.battery?.discharge_w != null ? `${fmt(t.battery.discharge_w)} W discharge` : t.battery?.charge_w != null ? `${fmt(t.battery.charge_w)} W charging` : 'Battery flow —';
    $('cpu').textContent = fmt(t.cpu_percent, 0) + '%'; $('cpu-bar').style.width = (t.cpu_percent || 0) + '%';
    const m = t.memory || {}, used = m.MemTotal - m.MemAvailable;
    $('memory').textContent = Number.isFinite(used) ? `${fmt(used / 2**30)} / ${fmt(m.MemTotal / 2**30)} GiB` : 'Unavailable';
    $('memory-bar').style.width = m.MemTotal ? (used / m.MemTotal * 100) + '%' : '0%';
    $('gpu-clock').textContent = Object.entries(t.gpu_frequency_mhz || {}).map(([k,v]) => `${k}: ${v == null ? '—' : v === 0 ? 'idle' : v+' MHz'}`).join(' · ') || 'Unavailable';
    $('gpu').textContent = t.gpu_percent == null ? 'Unavailable' : fmt(t.gpu_percent,0) + '%'; $('gpu-note').textContent = t.gpu_note;
    $('device').textContent = `${state.device.product} · ${state.device.board}\n${state.device.kernel}`;
    $('applied').textContent = state.power.interfaces.map(p => `${p.interface}: ${fmt(p.constraints.long_term?.watts,0)} W sustained / ${fmt(p.constraints.short_term?.watts,0)} W boost`).join('\n') || 'No package power controls detected';
    const visible = rgb.enabled && rgb.brightness > 0;
    $('rgb-status').textContent = !rgb.available ? 'UNAVAILABLE' : visible ? 'ON' : 'OFF';
    $('lighting-state').textContent = !rgb.available ? 'Lighting controls are unavailable.' : !rgb.enabled ? 'Lighting is currently off.' : rgb.brightness === 0 ? 'Lighting is dark because brightness is zero.' : `Lighting on · ${effectNames[rgb.effect] || rgb.effect} · ${rgb.brightness}%`;
    $('enable-rgb').hidden = !rgb.available || visible;
    if (!rgbDirty && !pending) lightingControls(rgb);
    if (!initialized) {
      for(const kind of ['power','rgb']) { $('remember-'+kind).disabled=!state.preferences?.available; $('remember-'+kind).checked=!!state.preferences?.[kind]; }
      initialized = true;
      notice(writeAllowed ? 'Connected to your Claw. Changes require Apply.' : 'Read-only preview · hardware changes are disabled.');
    }
    if (state.telemetry_error) notice('Telemetry: ' + state.telemetry_error, true);
    if (state.restore_error) notice('Some saved settings could not be restored: '+state.restore_error,true);
  } catch (error) { writeAllowed = false; locks(); $('connection').textContent = 'Offline'; notice(error.message, true); }
}
window.A1Navigation.create(document,window,{sidebar:document.body.classList.contains('sidebar'),bridge:launch.get('bridge')}).install();
locks(); refresh(); setInterval(refresh, 1500);
