import React,{useEffect,useRef,useState} from 'react';
import {framely,registerPlugin,Select} from '@framely/sdk';
import {messages,resolveLocale,errorMessage,type Language,type Locale,type Message} from './i18n';
import css from './style.css';

type Settings={enabled:boolean;language:Language;streamOnly:boolean;showSplit:boolean;sharpenAmount:number;sharpness:number;centerRadius:number;edgeAmount:number;debandAmount:number;debandRange:number;debandThreshold:number;detailBoost:number;grainAmount:number;grainSize:number;grainAnimate:boolean;casCross:boolean;casLuma:boolean;cornerSkip:number;splitEyes:boolean};
type GazeKey='gazeDepReprojectEnable'|'gazeDepEyeToHeadEnable';
type State={settings:Settings;loaded:boolean;configured:boolean;running:boolean;restartRequired:boolean;outdated:boolean;guardDisabled:boolean;conflict:boolean;stats:Record<string,number>|null;error:string;gaze:Partial<Record<GazeKey,boolean>>|null;gazeModified:boolean};
type Patch=Partial<Omit<Settings,'enabled'>>;

function useControl(){
 const [info,setInfo]=useState<State|null>(null),[draft,setDraft]=useState<Settings|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[saving,setSaving]=useState(false);
 const alive=useRef(true),pending=useRef<Patch>({}),worker=useRef<Promise<void>|null>(null),timer=useRef<ReturnType<typeof setTimeout>|null>(null),acting=useRef(false),generation=useRef(0),last=useRef<State|null>(null);
 function accept(value:State){last.current=value;if(alive.current){setInfo(value);setDraft({...value.settings,...pending.current});}}
 async function refresh(clearError=false){const version=generation.current;try{const value=await framely.call<State>('status');if(alive.current&&version===generation.current&&!worker.current&&!acting.current&&!Object.keys(pending.current).length){accept(value);if(clearError)setError('');}}catch(e){if(alive.current)setError(String(e));}}
 function flush():Promise<void>{
  if(worker.current)return worker.current;
  if(!Object.keys(pending.current).length)return Promise.resolve();
  if(alive.current)setSaving(true);
  worker.current=(async()=>{try{while(Object.keys(pending.current).length){const values=pending.current;pending.current={};accept(await framely.call<State>('settings.update',values));}if(alive.current)setError('');}catch(e){pending.current={};if(alive.current){setError(String(e));setDraft(last.current?.settings??null);}throw e;}finally{worker.current=null;if(alive.current)setSaving(false);}})();
  return worker.current;
 }
 function patch(value:Patch){generation.current++;pending.current={...pending.current,...value};setDraft(current=>current?{...current,...value}:current);if(timer.current)clearTimeout(timer.current);timer.current=setTimeout(()=>void flush().catch(()=>{}),180);}
 async function action(method:string,params:unknown={}){
  if(acting.current)return;
  acting.current=true;generation.current++;setBusy(true);setError('');
  if(timer.current)clearTimeout(timer.current);
  try{await flush();accept(await framely.call<State>(method,params));}catch(e){if(alive.current)setError(String(e));}finally{acting.current=false;if(alive.current)setBusy(false);}
 }
 useEffect(()=>{alive.current=true;void refresh();const interval=setInterval(()=>void refresh(),2000);return()=>{alive.current=false;clearInterval(interval);if(timer.current)clearTimeout(timer.current);void flush().catch(()=>{});};},[]);
 return {info,draft,error,busy,saving,patch,action,refresh};
}

function useHostLocale(){
 const [locale,setLocale]=useState<Locale>(resolveLocale(navigator.language));
 useEffect(()=>{let active=true,revision=0;const off=framely.onEvent((event:unknown)=>{const e=event as {type?:string;data?:{language?:string}};if(e.type==='language.changed'){revision++;if(active)setLocale(resolveLocale(e.data?.language));}});const initial=revision;void framely.language.get().then(value=>{if(active&&initial===revision)setLocale(resolveLocale(value.language));}).catch(()=>{});return()=>{active=false;off();};},[]);
 return locale;
}

function App(){
 const {info,draft:s,error,busy,saving,patch,action,refresh}=useControl();
 const host=useHostLocale(),locale=s?.language&&s.language!=='auto'?s.language:host,t=messages[locale];
 const [tab,setTab]=useState<'quality'|'experimental'|'steamvr'|'about'>('quality'),[windowError,setWindowError]=useState('');
 useEffect(()=>{document.documentElement.lang=locale==='zh'?'zh-CN':locale;document.title=t.title;},[locale,t.title]);
 const disabled=busy||!s;
 const notice=(text:string,kind='notice')=><div className={kind} role={kind==='error'?'alert':'status'}>{text}</div>;
 function toggle(key:keyof Settings,label:Message,hint?:Message){return <label className="toggle-row" key={key}><span><strong>{t[label]}</strong>{hint&&<small>{t[hint]}</small>}</span><input role="switch" type="checkbox" checked={key==='enabled'&&info?.guardDisabled?false:Boolean(s?.[key])} disabled={disabled} onChange={event=>key==='enabled'?void action('enable',{enabled:event.target.checked}):patch({[key]:event.target.checked})}/></label>;}
 function slider(key:keyof Settings,label:Message,min:number,max:number,step:number,hint?:Message,scale=1,unit=''){
  const value=Number(s?.[key]??0),format=(n:number)=>(n*scale).toLocaleString(locale,{maximumFractionDigits:scale===100?0:2})+unit;
  return <label className="slider-row" key={key}><span className="slider-label"><strong>{t[label]}</strong><output>{format(value)}</output></span>{hint&&<small>{t[hint]}</small>}<input type="range" min={min} max={max} step={step} value={value} disabled={disabled} aria-label={t[label]} aria-valuetext={format(value)} onChange={event=>patch({[key]:event.target.valueAsNumber})}/><span className="range-ends" aria-hidden="true"><span>{format(min)}</span><span>{format(max)}</span></span></label>;
 }
 const status=info?.outdated?'oldLayer':info?.guardDisabled?'disabled':info?.loaded?(s?.enabled&&info.configured?'active':'bypass'):info?.configured?'pendingLoad':info?.running?'disabled':'waiting';
 const errorText=windowError||error||info?.error;
 return <main className="betterframe" aria-busy={busy}>
  <header><div><h1>{t.title}</h1><p>{t.subtitle}</p></div><span className={'state '+(info?.loaded&&s?.enabled&&info.configured?'active':'')}>{t[status]}</span></header>
  <div className="language-row"><span>{t.language}</span><Select label={t.language} value={s?.language??'auto'} disabled={disabled} onChange={language=>patch({language:language as Language})} options={[{value:'auto',label:t.auto},{value:'zh',label:'中文'},{value:'ja',label:'日本語'},{value:'en',label:'English'}]}/></div>
  {errorText&&<div className="error" role="alert"><strong>{t.errorTitle}</strong><p>{errorMessage(locale,errorText)}</p>{errorMessage(locale,errorText)===t.generic_error&&<details><summary>{t.diagnostics}</summary><pre>{errorText}</pre></details>}<button disabled={busy} onClick={()=>{setWindowError('');void refresh(true);}}>{t.retry}</button></div>}
  {!s?<p role="status">{t.loading}</p>:<>
   {info?.guardDisabled&&notice(t.guarded,'warning')}
   {info?.conflict&&notice(t.conflict,'warning')}
   {(info?.restartRequired||s.enabled&&!info?.loaded&&!info?.guardDisabled&&!info?.error)&&notice(t.restart)}
   <section className="switches">{toggle('enabled','enabled','enabledHint')}{toggle('streamOnly','streamOnly','streamHint')}{toggle('showSplit','showSplit','splitHint')}</section>
   <nav role="tablist" aria-label={t.title}>{(['quality','experimental','steamvr','about'] as const).map(key=><button id={'tab-'+key} key={key} role="tab" aria-selected={tab===key} aria-controls={'panel-'+key} onClick={()=>setTab(key)}>{t[key]}</button>)}</nav>
   <div role="tabpanel" id={'panel-'+tab} aria-labelledby={'tab-'+tab}>
    {tab==='quality'&&<>
     <section><h2>{t.presets}</h2><div className="presets">{(['gentle','balanced','strong'] as const).map(name=><button disabled={disabled} key={name} onClick={()=>void action('preset',{name})}>{t[name]}</button>)}</div><small>{t.presetHint}</small></section>
     <section>{slider('sharpenAmount','sharpenAmount',0,2,.05,'sharpenHint')}{slider('sharpness','sharpness',0,1,.05,'sharpnessHint',100,'%')}</section>
     <section><h2>{t.weighting}</h2>{slider('centerRadius','centerRadius',0,1,.05,'centerHint',100,'%')}{slider('edgeAmount','edgeAmount',0,1,.05,'edgeHint',100,'%')}</section>
     <details className="advanced"><summary>{t.method}</summary>{toggle('casCross','casCross','crossHint')}{toggle('casLuma','casLuma','lumaHint')}{slider('cornerSkip','cornerSkip',0,2,.05,'cornerHint')}{toggle('splitEyes','splitEyes','eyesHint')}</details>
    </>}
    {tab==='experimental'&&<>
     {notice(t.experimentsHint)}
     <section>{slider('detailBoost','detailBoost',0,1,.05,'detailHint',100,'%')}</section>
     <section><h2>{t.deband}</h2>{notice(t.debandHint,'warning')}{slider('debandAmount','debandAmount',0,1,.05,undefined,100,'%')}{slider('debandRange','debandRange',1,32,1)}{slider('debandThreshold','debandThreshold',.5,8,.5)}</section>
     <section><h2>{t.grain}</h2>{slider('grainAmount','grainAmount',0,1,.05,'grainHint',100,'%')}{slider('grainSize','grainSize',1,4,.25)}{toggle('grainAnimate','grainAnimate')}</section>
    </>}
    {tab==='steamvr'&&<section><h2>{t.gazeTitle}</h2><p>{t.gazeHint}</p><button disabled={disabled||!info?.running} onClick={()=>void action('gaze.get')}>{t.gazeRead}</button>
     {info?.gaze?<>{(['gazeDepReprojectEnable','gazeDepEyeToHeadEnable'] as const).map(key=><label key={key} className="toggle-row"><strong>{t[key]}</strong><input type="checkbox" role="switch" checked={info.gaze?.[key]??false} disabled={disabled||!info.running||info.gaze?.[key]===undefined} onChange={event=>void action('gaze.set',{key,value:event.target.checked})}/></label>)}</>:<p>{t.gazeUnknown}</p>}
     <button disabled={disabled||!info?.running||!info.gazeModified} onClick={()=>void action('gaze.restore')}>{t.gazeRestore}</button><p><small>{t.gazeRestart}</small></p></section>}
    {tab==='about'&&<>
     <section><h2>{t.help}</h2><p>{t.pipeline}</p><p>{t.limitation}</p>{notice(t.stutter,'warning')}<p>{t.power}</p></section>
     <section><h2>{t.import}</h2><p>{t.importHint}</p><button disabled={disabled} onClick={()=>void action('settings.importOriginal')}>{t.import}</button></section>
     <section><h2>{t.reset}</h2><p>{t.resetHint}</p><button disabled={disabled} onClick={()=>void action('reset')}>{t.reset}</button></section>
     <p>{t.updates}</p>
    </>}
   </div>
   <section className="performance"><h2>{t.performance}</h2>{info?.stats?<dl>{([
    ['gpu',info.stats.gpuMsAvg,'ms',info.stats.gpuMsMax],['cpu',info.stats.cpuUsAvg,'µs',info.stats.cpuUsMax],
    ['fps',info.stats.fps,'',undefined],['gap',info.stats.gapMsP99,'ms',undefined],
   ] as [Message,number,string,number|undefined][]).map(([label,value,unit,peak])=><div key={label}><dt>{t[label]}</dt><dd>{Number.isFinite(value)&&value>=0?value.toFixed(label==='fps'?1:2):'—'} <span>{unit}</span></dd>{peak!==undefined&&peak>=0&&<small>{t.max} {peak.toFixed(2)} {unit}</small>}</div>)}</dl>:<p>{t.noStats}</p>}</section>
  </>}
  <footer><span role="status">{saving?t.saving:s?t.saved:''}</span><button disabled={busy} onClick={()=>void refresh(true)}>{t.refresh}</button><button disabled={busy} onClick={()=>void framely.windows.open('main').catch(error=>setWindowError(String(error)))}>{t.open}</button></footer>
 </main>;
}

const style=document.createElement('style');style.textContent=css;document.head.append(style);
registerPlugin({QuickPage:App,windows:{main:App}});
