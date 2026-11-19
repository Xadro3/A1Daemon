/* Shared navigation for keyboard, standalone Gamepad API and Steam's native bridge. */
(function(root) {
  function create(doc, win, options = {}) {
    let active = false, selected = null;
    const virtual = !!(options.sidebar && options.bridge);
    const current = () => virtual && active ? selected : doc.activeElement;
    const controls = () => [...doc.querySelectorAll('button,input,select')].filter(e => !e.disabled && !e.hidden && e.getClientRects().length);
    function focus(element) {
      if (!element) return;
      doc.querySelectorAll('.controller-focus').forEach(e => e.classList.remove('controller-focus'));
      element.classList.add('controller-focus');
      selected=element;
      // Keep Steam's DOM focus on its native focus target. Moving browser focus
      // across the iframe boundary would disconnect its controller event routing.
      if(!virtual || !active)element.focus({preventScroll:true});
      element.scrollIntoView({block:'nearest',inline:'nearest'});
    }
    function move(delta) {
      const list=controls(); if (!list.length) return;
      const index=list.indexOf(current());
      focus(list[index < 0 ? (delta > 0 ? 0 : list.length-1) : (index+delta+list.length)%list.length]);
    }
    function change(element) {
      element.dispatchEvent(new win.Event('input',{bubbles:true}));
      element.dispatchEvent(new win.Event('change',{bubbles:true}));
    }
    function adjust(delta) {
      const e=current();
      if (e?.type==='range') {
        const step=e.step && e.step!=='any' ? Number(e.step) : 1;
        e.value=String(Math.max(Number(e.min || 0),Math.min(Number(e.max || 100),Number(e.value)+delta*step)));
        change(e);
      } else if (e?.tagName==='SELECT') {
        e.selectedIndex=Math.max(0,Math.min(e.options.length-1,e.selectedIndex+delta)); change(e);
      } else move(delta);
    }
    function action(name) {
      if (name==='focus') {active=true; focus(doc.querySelector('.tab.active') || controls()[0]); return;}
      if (name==='blur') {active=false; doc.querySelectorAll('.controller-focus').forEach(e=>e.classList.remove('controller-focus')); return;}
      if (name==='up' || name==='down') return move(name==='down'?1:-1);
      if (name==='left' || name==='right') return adjust(name==='right'?1:-1);
      if (name==='activate') {
        if (!controls().includes(current())) {focus(doc.querySelector('.tab.active') || controls()[0]); return;}
        const e=current();
        if(e.type==='color') {move(1);return;}
        if (e.tagName==='BUTTON' || e.type==='checkbox') {e.click(); if(!controls().includes(current()))focus(doc.querySelector('.page.active button,.page.active input') || controls()[0]);}
      }
    }
    function message(event) {
      if (!options.bridge || event.origin!=='https://steamloopback.host' || event.data?.type!=='a1daemon-navigation' || event.data?.channel!==options.bridge) return;
      const command=event.data.action;
      if (!['focus','blur','up','down','left','right','activate'].includes(command)) return;
      if (command==='focus' || command==='blur' || active) action(command);
    }
    function keydown(event) {
      const command={ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right',Enter:'activate',' ':'activate'}[event.key];
      if (!command) return;
      // Colour pickers retain native keyboard handling; RGB channel sliders are available for controllers.
      if (current()?.type==='color' && ['Enter',' '].includes(event.key)) return;
      event.preventDefault();
      if (command==='activate' && event.repeat) return;
      action(command);
    }
    function install() {
      doc.addEventListener('keydown',keydown); win.addEventListener('message',message);
      doc.addEventListener('focusin',event=>{if(controls().includes(event.target))selected=event.target;});
      // Steam consumes controller input itself. Polling the browser API inside
      // its iframe misses events and can also double-trigger input on some clients.
      if (!options.sidebar) {
        let previous=[], nextMove=0;
        function poll(now) {
          const pad=[...(win.navigator.getGamepads?.() || [])].find(p=>p?.mapping==='standard');
          if(pad && doc.visibilityState==='visible' && doc.hasFocus()) {
            const current=pad.buttons.map(b=>b.pressed);
            const v=current[13] || pad.axes[1]>.6 ? 'down' : current[12] || pad.axes[1]<-.6 ? 'up' : null;
            const h=current[15] || pad.axes[0]>.6 ? 'right' : current[14] || pad.axes[0]<-.6 ? 'left' : null;
            if(now>nextMove && (v||h)) {action(v||h);nextMove=now+180;}
            if(current[0]&&!previous[0]) action('activate');
            previous=current;
          }
          win.requestAnimationFrame(poll);
        }
        win.requestAnimationFrame(poll);
      }
    }
    return {action, message, keydown, install, current};
  }
  if(typeof module!=='undefined' && module.exports) module.exports={create};
  else root.A1Navigation={create};
})(globalThis);
