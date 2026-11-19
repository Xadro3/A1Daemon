/* A1Daemon's independent Steam adapter. No Steam bundles are modified on disk.
 * Uses runtime capability detection; if discovery fails the stock QAM stays intact.
 * Native QAM tab shape researched against upstream Steam UI integrations.
 */
(() => {
  const config = __A1_CONFIG__;
  const build = '0.5.0';
  if (globalThis.__a1daemon?.url === config.url && globalThis.__a1daemon?.build === build && globalThis.__a1daemon?.navigationKey === config.navigation_key) return globalThis.__a1daemon.status;
  globalThis.__a1daemon?.dispose?.();
  const state = {url: config.url, build, navigationKey:config.navigation_key, status: {phase:'discovering'}, undo: [], arrays: new Set(), diagnostics:{renders:0,portals:0,focusWrappers:[],fiberMatches:0}};
  globalThis.__a1daemon = state;
  state.dispose = () => {
    state.undo.reverse().forEach(fn => fn());
    state.arrays.forEach(tabs => { for(let i=tabs.length-1;i>=0;i--) if(tabs[i]?.a1daemon) tabs.splice(i,1); });
    state.status = {phase:'removed'};
    delete globalThis.__a1daemon;
  };
  const chunks = globalThis.webpackChunksteamui;
  if (!chunks?.push) { state.status = {phase:'waiting', reason:'Steam module loader not found'}; delete globalThis.__a1daemon; return state.status; }
  let requireModule;
  chunks.push([[`a1daemon_${Date.now()}`], {}, r => {requireModule=r;}]);
  const exports = Object.values(requireModule?.c || {}).map(m => m?.exports).filter(Boolean);
  // Newer Steam webpack builds hide the module cache. Only load factories
  // matching React itself or QAM; never execute every module to discover them.
  for(const [id,factory] of Object.entries(requireModule?.m || {})) {
    const source=Function.prototype.toString.call(factory);
    if((/react\.production(?:\.min)?\.js/.test(source) && /createElement/.test(source)) || /QuickAccessMenuBrowserView|QuickAccessMenuEmbedded/.test(source) || (source.includes('elemProps') && source.includes('gamepadEvents') && source.includes('focusWithinClassName')) || (source.includes('"DIR_UP"') && source.includes('"LSTICK_CLICK"'))) {
      try {exports.push(requireModule(id));} catch {}
    }
  }
  const values = [];
  for(const exported of exports) { values.push(exported); try { values.push(...Object.values(exported)); } catch {} }
  const React = values.find(v => v?.createElement && v?.useState && v?.isValidElement);
  if (!React) {state.status={phase:'waiting',reason:'React runtime not found'}; delete globalThis.__a1daemon; return state.status;}
  const candidates = values.filter(v => typeof v?.type === 'function' && /QuickAccessMenuBrowserView|QuickAccessMenuEmbedded/.test(Function.prototype.toString.call(v.type)));
  if(!candidates.length) {state.status={phase:'waiting',reason:'Quick Access renderer not loaded'}; delete globalThis.__a1daemon; return state.status;}
  const element = React.createElement;
  const Focusable=values.find(v=>typeof v==='function' && v.toString().includes('"flow-children"') && v.toString().includes('gamepadEvents') && v.toString().includes('elemProps'));
  const buttons=values.find(v=>v && typeof v==='object' && Number.isInteger(v.DIR_UP) && Number.isInteger(v.OK) && Number.isInteger(v.CANCEL));
  state.diagnostics.nativeNavigation=!!(Focusable && buttons && config.navigation_key);
  function Panel() {
    const frame=React.useRef(null), focused=React.useRef(false);
    const send=action=>{
      frame.current?.contentWindow?.postMessage({type:'a1daemon-navigation',channel:config.navigation_key,action},new URL(config.url).origin);
      state.diagnostics.lastNavigation=action;
    };
    const iframe=element('iframe', {ref:frame,src:config.url+'&sidebar=1&bridge='+encodeURIComponent(config.navigation_key || ''), title:'Claw control',tabIndex:-1,
      style:{width:'100%',height:'calc(100vh - 50px)',border:0,display:'block',background:'#0d1118'},
      onLoad:()=>{if(focused.current)send('focus');}});
    if(!Focusable || !buttons) return iframe;
    const actions=new Map([[buttons.DIR_UP,'up'],[buttons.DIR_DOWN,'down'],[buttons.DIR_LEFT,'left'],[buttons.DIR_RIGHT,'right'],[buttons.OK,'activate']]);
    return element(Focusable, {focusable:true,noFocusRing:true,'data-a1daemon-navigation':'true',
      onGamepadFocus:()=>{focused.current=true;send('focus');},
      onGamepadBlur:()=>{focused.current=false;send('blur');},
      onButtonDown:event=>{
        const action=actions.get(event.detail?.button);
        if(!action) return false; // B and Steam system buttons retain native behaviour.
        event.stopPropagation();event.preventDefault();
        if(action!=='activate' || !event.detail?.is_repeat)send(action);
        return true;
      }},iframe);
  }
  function addTab(tabs) {
    if(!Array.isArray(tabs) || Object.isFrozen(tabs)) return;
    state.arrays.add(tabs);
    if(state.arrays.size>8) state.arrays.delete(state.arrays.values().next().value);
    if(tabs.some(tab=>tab?.a1daemon)) return;
    tabs.push({key: 17641, a1daemon:true, title:'Claw',
      tab:element('svg',{viewBox:'0 0 24 24',width:24,height:24,fill:'none',stroke:'currentColor',strokeWidth:2},element('path',{d:'M13 2 4 14h7l-1 8 10-12h-7z'})),
      panel:element(Panel)});
    state.status={phase:'tab-inserted',tabs:tabs.length};
  }
  const wrapped = new WeakMap();
  function wrap(fn, depth) {
    if(wrapped.has(fn)) return wrapped.get(fn);
    function Render(...args) {
      state.diagnostics.renders++;
      const original=fn.apply(this,args);
      try {return inspect(original,0);} catch(error) {
        state.status={phase:'unsupported',reason:String(error.message||error)};
        return original;
      }
    }
    wrapped.set(fn,Render); return Render;
  }
  function inspect(tree, depth=0) {
    if(depth>40 || tree==null) return tree;
    if(Array.isArray(tree)) return tree.map(node=>inspect(node,depth+1));
    if(tree.$$typeof===Symbol.for('react.portal')) {state.diagnostics.portals++; return {...tree,children:inspect(tree.children,depth+1)};}
    if(!React.isValidElement(tree)) return tree;
    const props=tree.props || {};
    if(props.onFocusNavDeactivated && state.diagnostics.focusWrappers.length<8) state.diagnostics.focusWrappers.push({type:typeof tree.type,keys:Object.keys(tree.type||{})});
    if(Array.isArray(props.tabs)) { addTab(props.tabs); return tree; }
    // Traverse already created children, and instrument the QAM focus wrapper
    // whose tab list is constructed only when React later renders it.
    const replacements={};
    if(props.children) replacements.children=inspect(props.children,depth+1);
    if(props.onFocusNavDeactivated && typeof tree.type==='function') {
      return element(wrap(tree.type,depth+1),{...props,...replacements,key:tree.key});
    }
    if(props.onFocusNavDeactivated && typeof tree.type?.type==='function') {
      return element({...tree.type,type:wrap(tree.type.type,depth+1)},{...props,...replacements,key:tree.key});
    }
    return Object.keys(replacements).length ? React.cloneElement(tree,replacements) : tree;
  }
  for(const candidate of new Set(candidates)) {
    const original=candidate.type, replacement=wrap(original,0);
    candidate.type=replacement;
    state.undo.push(()=>{if(candidate.type===replacement) candidate.type=original;});
    // A mounted memo component may cache the original renderer in its fiber.
    const root=document.getElementById('root');
    const rootKey=root && Object.keys(root).find(k=>k.startsWith('__reactContainer$'));
    const container=rootKey && root[rootKey];
    const start=container?.stateNode?.current || container?.current || container;
    const stack=start ? [start] : [], visited=new Set();
    while(stack.length && visited.size<50000) {
      const fiber=stack.pop(); if(!fiber || visited.has(fiber)) continue; visited.add(fiber);
      if(fiber.elementType===candidate) {
        state.diagnostics.fiberMatches++;
        fiber.type=replacement;
        if(fiber.alternate) fiber.alternate.type=replacement;
        state.undo.push(()=>{if(fiber.type===replacement) fiber.type=original; if(fiber.alternate?.type===replacement) fiber.alternate.type=original;});
      }
      if(fiber.child) stack.push(fiber.child); if(fiber.sibling) stack.push(fiber.sibling);
      if(fiber.current) stack.push(fiber.current);
    }
  }
  state.status={phase:'hook-installed',renderers:candidates.length,note:'Open the Quick Access Menu to render the Claw tab.'};
  return state.status;
})()
