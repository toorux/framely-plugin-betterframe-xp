import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('..',import.meta.url));
export async function createPreview(port=0){
 const bridge=await readFile(path.join(root,'tests/preview-bridge.js'),'utf8');
 const html=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>BetterFrame XP preview</title><body><div id="root"></div><script>${bridge}</script><script src="/page.js"></script></body></html>`;
 const server=http.createServer(async(req,res)=>{try{if(req.url?.split('?')[0]==='/page.js'){res.setHeader('Content-Type','text/javascript; charset=utf-8');res.end(await readFile(path.join(root,'payload/page.js')));}else{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);}}catch(error){res.statusCode=500;res.end(String(error));}});
 await new Promise(resolve=>server.listen(port,'127.0.0.1',resolve));
 return {server,url:`http://127.0.0.1:${server.address().port}/quick`};
}
if(process.argv[1]&&pathToFileURL(path.resolve(process.argv[1])).href===import.meta.url){const {url}=await createPreview(Number(process.env.PORT??4319));console.log(`Mock preview only; no SteamVR changes: ${url}`);}
