// Browser fixture only. No device, SteamVR, or systemd access.
const settings={enabled:false,language:'auto',streamOnly:true,showSplit:false,sharpenAmount:1.2,sharpness:.7,centerRadius:.55,edgeAmount:.4,debandAmount:0,debandRange:12,debandThreshold:2.5,detailBoost:0,grainAmount:0,grainSize:1,grainAnimate:true,casCross:true,casLuma:true,cornerSkip:1.15,splitEyes:true};
const subscribers=new Set();
window.__mock={
 state:{settings,loaded:false,configured:false,running:true,restartRequired:false,outdated:false,guardDisabled:false,conflict:false,stats:null,error:'',gaze:null,gazeModified:false},
 calls:[],host:'zh-CN',failure:'',delay:20,
 language(language){this.host=language;for(const callback of subscribers)callback({type:'language.changed',data:{language}});},
};
window.__framelyBridge={
 subscribe(callback){subscribers.add(callback);return()=>subscribers.delete(callback);},
 async request(op,params){
  const mock=window.__mock;
  if(op==='language.get')return {preference:'auto',language:mock.host};
  if(op==='window.open'){mock.calls.push({op,...params});return {};}
  if(op!=='call')throw new Error('Unknown mock bridge operation');
  mock.calls.push(structuredClone(params));
  await new Promise(resolve=>setTimeout(resolve,mock.delay));
  if(mock.failure&&params.method!=='status')throw new Error(mock.failure);
  const s=mock.state;
  switch(params.method){
   case 'status':break;
   case 'settings.update':Object.assign(s.settings,params.params);break;
   case 'enable':s.settings.enabled=params.params.enabled;s.configured=params.params.enabled;s.restartRequired=true;break;
   case 'preset':Object.assign(s.settings,{sharpenAmount:{gentle:.6,balanced:1.2,strong:1.6}[params.params.name],debandAmount:0,grainAmount:0});break;
   case 'gaze.get':s.gaze={gazeDepReprojectEnable:true,gazeDepEyeToHeadEnable:false};break;
   case 'gaze.set':s.gaze[params.params.key]=params.params.value;s.gazeModified=true;break;
   case 'gaze.restore':s.gazeModified=false;break;
   case 'reset':s.settings.sharpenAmount=1.2;break;
   case 'settings.importOriginal':s.settings.sharpenAmount=.9;break;
   default:throw new Error('Unknown mock backend method');
  }
  return structuredClone(s);
 }
};
