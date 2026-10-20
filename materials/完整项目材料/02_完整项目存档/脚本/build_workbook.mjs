import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const records=JSON.parse(await fs.readFile(path.join(root,'编码','反馈证据.json'),'utf8'));
const findings=JSON.parse(await fs.readFile(path.join(root,'编码','问题归纳.json'),'utf8'));
const capture=JSON.parse(await fs.readFile(path.join(root,'数据','采集摘要.json'),'utf8'));
const replies=JSON.parse(await fs.readFile(path.join(root,'数据','定向回查回复.json'),'utf8')).replies;
const out=path.join(root,'outputs','01a14881-cb95-79a0-9a50-a2b336beeb9d');
await fs.mkdir(out,{recursive:true});
const wb=Workbook.create();
const main=wb.worksheets.add('问题归纳');
const evidence=wb.worksheets.add('反馈证据');
const followup=wb.worksheets.add('定向回复');
const navy='#24374E',muted='#64748B',amber='#FFF4D4';
function prepare(sheet,lastCol,lastRow){
  sheet.showGridLines=false;
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.font={name:'Arial',size:11,color:'#202B3B'};
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.verticalAlignment='top';
}
function header(sheet,range){
  sheet.getRange(range).format={fill:navy,font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:30};
}
function title(sheet,text){sheet.getRange('A2').values=[[text]];sheet.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:navy};sheet.getRange('A2').format.rowHeight=27;}
function widths(sheet,colWidths){for(let i=0;i<colWidths.length;i++)sheet.getRangeByIndexes(0,i,1,1).format.columnWidth=colWidths[i];}

prepare(main,'H',12);title(main,'原神高难副本体验观察');
main.tabColor=navy;
main.getRange('A3:H3').values=[['暂合并记录',null,'待本人复核',null,'页面记录',capture.page_observations,'视频数',capture.source_count]];
main.getRange('B3').formulas=[[`=COUNTA('反馈证据'!A7:A${records.length+6})`]];
main.getRange('D3').formulas=[[`=COUNTIFS('反馈证据'!K7:K${records.length+6},"待本人复核")`]];
main.getRange('A4').values=[['2026-10-17　便利样本；五项待验证问题；机制与效果尚未实机核验']];
main.getRange('A4').format.font={name:'Arial',size:10,color:muted};
const fHeaders=['编号','副本','体验问题','证据编号','待验证解释','下一步核验','当前状态','本人意见'];
const fRows=findings.map(f=>[f.id,f.mode,f.title,f.supports.join('\n'),f.hypothesis,f.action,f.status,'']);
main.getRange(`A6:H${fRows.length+6}`).values=[fHeaders,...fRows];
widths(main,[12,18,39,27,45,52,36,28]);
main.getRange('A7:H11').format.wrapText=true;
main.getRange('A7:H11').format.rowHeight=125;
main.getRange('H7:H11').format.fill=amber;
main.tables.add('A6:H11',true,'FindingsTable');header(main,'A6:H6');
main.getRange('A6:H6').format.borders={insideVertical:{style:'thin',color:'#FFFFFF'}};

const headers=['证据编号','副本','评论时间（页面原样）','AI初判类别','体验环节','玩家结果自述','问题标签','脱敏原文','可支持判断','证据缺口','本人复核','本人意见','来源视频','读取排序','采集时间（北京时间）','含图（未审阅）'];
const rows=records.map(r=>[r.record_id,r.mode,r.date_display,r.reading_type,r.stage,r.stated_outcome,r.finding_ids,r.text,r.supported_reading,r.evidence_gap,r.review_status,r.review_note,r.url,r.sorts,new Date(new Date(r.captured_at).getTime()+8*3600000),r.has_picture?'是':'否']);
const last=rows.length+6;
prepare(evidence,'P',last);title(evidence,'反馈证据与逐条复核');
evidence.getRange('A4').values=[['保留166条暂合并记录（含3条置顶）；原文未因编码改写；平台评论ID未取得，按视频、日期和原文定位。']];
evidence.getRange('A4').format.font={name:'Arial',size:10,color:muted};
evidence.getRange(`A6:P${last}`).values=[headers,...rows];
widths(evidence,[22,20,25,25,26,42,16,80,64,62,20,54,66,15,26,18]);
evidence.getRange(`A7:P${last}`).format.wrapText=true;
evidence.getRange(`A7:P${last}`).format.rowHeight=75;
evidence.getRange(`O7:O${last}`).setNumberFormat('yyyy-mm-dd hh:mm:ss');
evidence.getRange(`K7:L${last}`).format.fill=amber;
evidence.getRange(`K7:K${last}`).dataValidation={rule:{type:'list',values:['待本人复核','认可','需修改','排除']}};
evidence.tables.add(`A6:P${last}`,true,'FeedbackTable');header(evidence,'A6:P6');
evidence.getRange(`A7:P${last}`).format.autofitRows();
evidence.freezePanes.freezeRows(6);
evidence.freezePanes.freezeColumns(2);

prepare(followup,'G',13);title(followup,'定向回复与结果更新');
followup.getRange('A4').values=[['按用户选择回查两条聚怪反馈；7条回复单列，不加入初始根评论样本分母。']];
followup.getRange('A4').format.font={name:'Arial',size:10,color:muted};
const replyRows=replies.map(r=>[r.reply_id,r.parent_id,r.author_relation,r.date_display,r.text,r.reading,'https://www.bilibili.com/video/BV1saaz6iEE6/']);
followup.getRange('A6:G13').values=[['回复编号','根评论编号','与根评作者关系','页面时间','脱敏原文','对分析的影响','视频来源'],...replyRows];
widths(followup,[27,24,24,25,80,68,64]);
followup.getRange('A7:G13').format.wrapText=true;
followup.getRange('A7:G13').format.rowHeight=80;
followup.getRange('A7:G13').format.autofitRows();
followup.tables.add('A6:G13',true,'FollowupTable');header(followup,'A6:G6');
followup.freezePanes.freezeRows(6);
followup.freezePanes.freezeColumns(2);

wb.recalculate();
const original=main.getRange('D3').values[0][0];
if(original!==records.length)throw new Error(`Expected ${records.length} pending rows, got ${original}`);
evidence.getRange('K7').values=[['认可']];wb.recalculate();
if(main.getRange('D3').values[0][0]!==records.length-1)throw new Error('Review count did not update');
evidence.getRange('K7').values=[['待本人复核']];wb.recalculate();
if(main.getRange('D3').values[0][0]!==records.length)throw new Error('Review test was not restored');
const inspection=await wb.inspect({kind:'region',sheetId:'问题归纳',range:'A3:H3',maxChars:2000,tableMaxRows:1,tableMaxCols:8});
await fs.writeFile(path.join(out,'verification.json'),JSON.stringify({records:records.length,replies:replies.length,reviewCounterChangeRestored:true,inspection},null,2));
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:30},maxChars:2000});
await fs.writeFile(path.join(out,'formula_error_scan.json'),JSON.stringify(errors,null,2));
for(const [sheetName,range,name] of [['问题归纳','A1:H11','问题归纳预览'],['反馈证据','A6:H10','反馈证据预览'],['定向回复','A6:F10','定向回复预览']]){
  const blob=await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(out,name+'.png'),new Uint8Array(await blob.arrayBuffer()));
}
const output=await SpreadsheetFile.exportXlsx(wb);
await output.save(path.join(out,'原神高难副本_反馈证据.xlsx'));
console.log(JSON.stringify({output:path.join(out,'原神高难副本_反馈证据.xlsx'),records:records.length,replies:replies.length,reviewCounterChangeRestored:true}));
