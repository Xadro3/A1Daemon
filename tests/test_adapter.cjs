// Synthetic Steam runtime fixture: checks tab preservation, deduplication and cleanup.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('steam/adapter.js','utf8').replace('__A1_CONFIG__',JSON.stringify({url:'http://127.0.0.1:17641/#token=fixture',navigation_key:'fixture-channel'}));
const React = {
  createElement:(type,props,...children)=>({type,props:{...props,...(children.length?{children}: {})}}),
  cloneElement:(tree,props)=>({...tree,props:{...tree.props,...props}}),
  isValidElement:tree=>Boolean(tree?.type && tree?.props), useState:()=>{},
};
const tabs=[{key:1,title:'Steam'}];
const renderer={type:function QuickAccessMenuBrowserView(){ return React.createElement('tabs',{tabs}); }};
const fixture={document:{getElementById:()=>null},webpackChunksteamui:{push:(chunk)=>chunk[2]({c:{react:{exports:React},qam:{exports:{renderer}}}})}};
const context=vm.createContext(fixture);
assert.equal(vm.runInContext(source,context).phase,'hook-installed');
renderer.type();
assert.equal(tabs.length,2); assert.equal(tabs[0].title,'Steam'); assert.equal(tabs[1].title,'Claw');
renderer.type(); assert.equal(tabs.length,2);
assert.equal(vm.runInContext(source,context).phase,'tab-inserted');
vm.runInContext('globalThis.__a1daemon.dispose()',context);
assert.equal(tabs.length,1); assert.match(renderer.type.name,/QuickAccess/);
assert.equal(vm.runInNewContext(source,{document:{}}).phase,'waiting');
// React 19: hidden webpack cache, portal, deep QAM tree and an existing memo fiber.
const nativeTabs=[{key:0,title:'Settings'}];
function QamContent(){let tree=React.createElement('tabs',{tabs:nativeTabs});for(let i=0;i<14;i++)tree=React.createElement('div',{},tree);return tree;}
const modernRenderer={type:function QuickAccessMenuBrowserView(){return {$$typeof:Symbol.for('react.portal'),children:React.createElement(QamContent,{onFocusNavDeactivated:()=>{}})};}};
const modernOriginal=modernRenderer.type;
const messages=[];
let refIndex=0;
const frame={contentWindow:{postMessage:(message,origin)=>messages.push({message,origin})}};
React.useRef=()=>({current:refIndex++%2===0?frame:false});
function NativeFocusable(){/* "flow-children" gamepadEvents elemProps */}
const buttons={DIR_UP:9,DIR_DOWN:10,DIR_LEFT:11,DIR_RIGHT:12,OK:1,CANCEL:2};
const fiber={elementType:modernRenderer,type:()=>null,alternate:{type:()=>null}};
const root={'__reactContainer$fixture':{stateNode:{current:{child:fiber}}}};
function reactFactory(){/* react.production.js */ return 'createElement';}
function qamFactory(){return 'QuickAccessMenuBrowserView';}
function focusFactory(){return 'elemProps gamepadEvents focusWithinClassName';}
function buttonFactory(){return '"DIR_UP" "LSTICK_CLICK"';}
const requireModern=id=>id==='react'?React:id==='focus'?{NativeFocusable}:id==='buttons'?{buttons}:{modernRenderer}; requireModern.m={react:reactFactory,qam:qamFactory,focus:focusFactory,buttons:buttonFactory};
const modern=vm.createContext({URL,document:{getElementById:()=>root},webpackChunksteamui:{push:chunk=>chunk[2](requireModern)}});
assert.equal(vm.runInContext(source,modern).phase,'hook-installed');
const portal=fiber.type(); const focusWrapper=portal.children; focusWrapper.type(focusWrapper.props);
assert.equal(nativeTabs.length,2); assert.equal(nativeTabs[1].title,'Claw');
const panel=nativeTabs[1].panel.type();assert.equal(panel.type,NativeFocusable);
panel.props.onGamepadFocus();assert.equal(messages.at(-1).message.action,'focus');
const event=button=>({detail:{button,is_repeat:false},preventDefault(){},stopPropagation(){}});
panel.props.onButtonDown(event(buttons.DIR_DOWN));assert.equal(messages.at(-1).message.action,'down');
panel.props.onButtonDown(event(buttons.OK));assert.equal(messages.at(-1).message.action,'activate');
const count=messages.length;
assert.equal(panel.props.onButtonDown(event(buttons.CANCEL)),false);assert.equal(messages.length,count,'B remains native');
panel.props.onButtonDown({...event(buttons.OK),detail:{button:buttons.OK,is_repeat:true}});assert.equal(messages.length,count);
panel.props.onGamepadBlur();assert.equal(messages.at(-1).message.action,'blur');
vm.runInContext('globalThis.__a1daemon.dispose()',modern);
assert.equal(nativeTabs.length,1); assert.equal(fiber.type,modernOriginal); assert.equal(modernRenderer.type,modernOriginal);
console.log('Steam adapter fixtures passed: legacy and React 19 discovery, portals, deep trees, mounted fibers, deduplication and removal');
