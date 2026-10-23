import {build} from 'esbuild';
import {createRequire} from 'node:module';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
const dir=await mkdtemp(path.join(tmpdir(),'betterframe-i18n-'));
try{
 const file=path.join(dir,'i18n.cjs');
 await build({entryPoints:['src/i18n.ts'],outfile:file,bundle:true,platform:'node',format:'cjs'});
 const {messages,resolveLocale,errorMessage}=createRequire(import.meta.url)(file);
 for(const locale of ['zh','ja','en']){
  assert.deepEqual(Object.keys(messages[locale]).sort(),Object.keys(messages.en).sort());
  for(const [key,value] of Object.entries(messages[locale]))assert.ok(value.trim(),`${locale}.${key}`);
  assert.equal(errorMessage(locale,'Error: invalid_settings'),messages[locale].invalid_settings);
  assert.equal(errorMessage(locale,'some native diagnostic'),messages[locale].generic_error);
 }
 for(const [input,expected] of [['zh-CN','zh'],['zh_Hant','zh'],['ja-JP','ja'],['JA_jp','ja'],['en-US','en'],['fr','en'],[undefined,'en']])assert.equal(resolveLocale(input),expected);
 const source=await readFile('src/page.tsx','utf8');
 for(const match of source.matchAll(/\bt\.([a-zA-Z_]+)/g))assert.ok(messages.en[match[1]],`Missing UI translation: ${match[1]}`);
 const backend=await readFile('src/backend.py','utf8');
 for(const match of backend.matchAll(/(?:RuntimeError|ValueError)\('([a-z_]+)'\)/g))assert.ok(messages.en[match[1]],`Missing error translation: ${match[1]}`);
 console.log(`Three-language parity, locale resolution and backend error coverage passed (${Object.keys(messages.en).length} messages per language).`);
}finally{await rm(dir,{recursive:true,force:true});}
