import fs from 'node:fs/promises';
import {Workbook} from '@oai/artifact-tool';
const out=new URL('./',import.meta.url);
const files=['全量编码明细.csv','分副本主题与关注度.csv'];
const authoritative=JSON.parse(await fs.readFile(new URL('编码分析数据.json',out),'utf8'));
const sourceById=new Map(authoritative.rows.map(r=>[r.id,r]));
const results=[];
for(const name of files){
 const path=new URL(name,out);const text=await fs.readFile(path,'utf8');
 const wb=await Workbook.fromCSV(text.replace(/^\uFEFF/,''),{sheetName:'数据'});
 const sheet=wb.worksheets.getItemAt(0);let values=sheet.getUsedRange().values;
 const header=values[0];
 if(name==='全量编码明细.csv'){
   const idCol=header.indexOf('id');const lookup=new Map(authoritative.rows.map(r=>[r.id,r]));
   for(const key of ['ctime_bjt','like_snapshot_at']){
     const j=header.indexOf(key);
     sheet.getRangeByIndexes(1,j,values.length-1,1).format.numberFormat='@';
     sheet.getRangeByIndexes(1,j,values.length-1,1).values=values.slice(1).map(row=>[lookup.get(row[idCol])[key]]);
   }
 }
 const numeric=new Set(['like','unit_weight','attention_weight','n','related_denominator','all_denominator','equal_share_related','equal_share_all','attention_share','raw_likes','raw_likes_share','sources','authors','ambiguity_lower_all','ambiguity_upper_all']);
 for(let j=0;j<header.length;j++)if(numeric.has(header[j])){
  const col=values.slice(1).map(row=>[row[j]===''?null:Number(row[j])]);
  if(col.some(v=>v[0]!==null&&!Number.isFinite(v[0])))throw Error('Invalid number '+header[j]);
  sheet.getRangeByIndexes(1,j,col.length,1).values=col;
 }
 wb.recalculate();values=sheet.getUsedRange().values;
 if(name==='全量编码明细.csv'){
  if(values.length!==6527)throw Error('Wrong number of comments');
  const key=header.indexOf('id');if(new Set(values.slice(1).map(r=>r[key])).size!==6526)throw Error('Duplicate IDs');
 }
 // Flat CSV has no visual layout or live formulas. Values are re-exported after engine validation.
 const escape=v=>'"'+String(v??'').replaceAll('"','""')+'"';
 const safe=values.map((row,i)=>row.map((v,j)=>{
   if(i&&name==='全量编码明细.csv'&&['ctime_bjt','like_snapshot_at'].includes(header[j])){
     const source=sourceById.get(row[header.indexOf('id')]);
     return source[header[j]];
   }
   if(i&&typeof v==='string'&&/^[=+@-]/.test(v)&&['text','evidence'].includes(header[j]))return "'"+v;
   return v;
 }));
 await fs.writeFile(path,'\uFEFF'+safe.map(row=>row.map(escape).join(',')).join('\r\n')+'\r\n','utf8');
 results.push({file:name,rows:values.length-1,columns:header.length});
 console.log((await wb.inspect({kind:'table',range:'数据!A1:F3',include:'values',tableMaxRows:3,tableMaxCols:6,maxChars:900})).ndjson);
}
await fs.writeFile(new URL('表格导出校验.json',out),JSON.stringify({artifact_tool:true,files:results,CSV_formula_escape:'literal leading apostrophe in text/evidence; original text retained in frozen JSON'},null,2),'utf8');
console.log(JSON.stringify(results));
