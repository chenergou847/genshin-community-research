// 将正文、内容统计和原文证据写入网页模板；不采集、不生成语义判断。
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(process.env.MARKED_BASE || import.meta.url);
const { marked } = await import(pathToFileURL(require.resolve('marked')));
const read = rel => fs.readFileSync(path.join(root,rel),'utf8').replace(/^\uFEFF/,'');
const project=JSON.parse(read('project.json'));
const repoBlob=`https://github.com/${project.owner}/${project.repository}/blob/main`;
const stats = JSON.parse(read('analysis/content-20261024/statistics.json'));
const book = JSON.parse(read('analysis/content-20261024/codebook.json'));
const coded = JSON.parse(read('analysis/content-20261024/coded-statements.json')).rows;
const frame = JSON.parse(read('materials/完整项目材料/02_完整项目存档/采集工具/正式采集_小样本v1_20261018/small_snapshot_frame_001.json'));
const comments = new Map(frame.comments.map(r=>[r.id,r]));
const md=read('report/报告.md');
const evidenceIds=[...new Set([...md.matchAll(/证据(\d+)｜原视频/g)].map(x=>Number(x[1])))];
const names={abyss:'深境螺旋',theater:'幻想真境剧诗',stygian:'幽境危战'};
const evidence=evidenceIds.map(index=>{
 const row=coded[index-1];assert.equal(row.seq,index);
 const ancestors=[];let parent=row.parent_id;const seen=new Set();
 while(parent && parent!=='0' && !seen.has(parent)) {
  seen.add(parent);const p=comments.get(parent);if(!p)break;ancestors.push(p);parent=p.parent_id;
 }
 return {index,mode:names[row.target_mode],row,ancestors};
});
const data={markdown:md,content:stats,codebook:book,evidence};
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
marked.use({walkTokens(token){
 if(token.type==='link'&&!/^(https?:|#)/.test(token.href)){
  const absolute=path.resolve(root,'report',token.href);assert.ok(fs.existsSync(absolute),token.href);
  const relative=path.relative(root,absolute).replaceAll('\\','/');assert.ok(!relative.startsWith('../'));
  token.href=`${repoBlob}/${relative}`;
 }
}});
let tables=0;
function render(text,section){
 let html=marked.parse(text,{gfm:true});let sub=0;
 html=html.replace(/<h3>/g,()=>`<h3 id="${section}-sub-${++sub}">`);
 html=html.replace(/<table>/g,()=>`<div class="table-scroll" role="region" aria-label="报告表格 ${++tables}" tabindex="0"><table>`).replaceAll('</table>','</table></div>');
 html=html.replace(/<a href="((?:https?:|\{\{REPO_BLOB\}\})[^"]*)">/g,'<a href="$1" target="_blank" rel="noopener noreferrer">');
 html=html.replace(/<p>(<a[^>]+>证据(\d+)｜原视频<\/a>[\s\S]*?)<\/p>/g,(_,content,n)=>`<p class="evidence-meta">${content}<button class="evidence-open" data-evidence="${n}">原文与上文 ↗</button></p>`);
 if(section==='section-b')html=html.replace(/<tr>\s*<td>(\d+)<\/td>/g,(_,n)=>`<tr><td><button class="inline-evidence" data-evidence="${n}">${n} ↗</button></td>`);
 return html;
}
const chartKeys={abyss:['easy','easy_good','easy_bad','enemy_bad'],theater:['opener_trial_bad','random_bad','retry_bad','fun'],stygian:['roster','shared_support','hidden_cost','understand']};
function chart(mode){
 const s=stats.modes[mode],keys=chartKeys[mode];
 const bars=keys.map(code=>{const m=s.claims[code];return `<div class="bar-row"><div class="bar-heading"><span>${esc(m.label)}</span><span><strong>${(100*m.share).toFixed(1)}%</strong><small>${m.n} 条 · ${m.authors} 位作者</small></span></div><div class="bar-track"><div class="bar-fill" style="width:${m.share*100}%"></div></div></div>`;}).join('');
 return `<figure class="topic-chart" data-mode="${mode}" data-codes="${keys.join(',')}"><div class="chart-top"><figcaption><span class="overline">具体观点分布</span><strong>说了什么，涉及多少位作者</strong></figcaption><div class="chart-switch" role="group" aria-label="选择统计单位"><button type="button" data-unit="statements" aria-pressed="true">按发言</button><button type="button" data-unit="authors" aria-pressed="false">按作者</button></div></div><div class="bars">${bars}</div><p class="chart-note">分母：${s.denominator.toLocaleString('en-US')} 条相关发言；观点可重叠。</p></figure>`;
}
const config=[['section-1','主要发现','FINDINGS'],['section-4','深境螺旋','SPIRAL ABYSS','abyss'],['section-5','幻想真境剧诗','IMAGINARIUM THEATER','theater'],['section-6','幽境危战','STYGIAN ONSLAUGHT','stygian'],['section-7','改进重点','IMPLICATIONS'],['section-3','方法与统计口径','METHODS'],['section-8','来源与数据限制','SCOPE'],['section-a','检索关键词','SEARCH TERMS'],['section-b','原文与数据','EVIDENCE']];
const pieces=md.split(/^## (.+)$/m);assert.equal(pieces.length,19);
const intro=pieces[0].trim().split(/\n\n+/);
const sections=config.map(([id,short,english,mode],n)=>({id,short,english,mode,number:n<7?String(n+1).padStart(2,'0'):n===7?'A':'B',heading:pieces[2*n+1],body:pieces[2*n+2]}));
let template=read('web/page.template.html');
template=template.replace(/<nav>[\s\S]*?<\/nav>/,`<nav>${sections.map(s=>`<a href="#${s.id}" data-section="${s.id}"><span class="nav-num">${s.number}</span><span>${s.short}</span></a>`).join('')}</nav>`);
template=template.replace(/<meta name="description" content="[^"]*">/,'<meta name="description" content="6,526条发言的内容分析：具体观点、去重作者、来源分布与原文证据。">');
template=template.replace(/2026 年 10 月 \d+ 日修订/g,'2026 年 10 月 25 日修订');
template=template.replace(/<div class="hero-stats">[\s\S]*?<\/div><\/div>/,'<div class="hero-stats"><div><strong>60</strong><span>固定视频来源</span></div><div><strong>6,526</strong><span>全量复读发言</span></div><div><strong>4,469</strong><span>匿名发言作者</span></div><div><strong>5,163</strong><span>纳入内容分析</span></div></div>');
template=template.replace(/<div class="hero-meta">[\s\S]*?<\/div>/,`<div class="hero-meta">${esc(intro[1])}</div>`);
template=template.replace(/<div class="hero-intro prose">[\s\S]*?<\/div>/,`<div class="hero-intro prose">${render(intro.slice(2).join('\n\n'),'intro')}</div>`);
template=template.replace(/查看 \d+ 条原文证据/g,`查看 ${evidence.length} 条原文证据`);
const start=template.indexOf('<section class="report-section');const end=template.indexOf('<footer class="report-footer">');assert.ok(start>0&&end>start);
const content=sections.map(s=>`<section class="report-section" id="${s.id}" aria-labelledby="${s.id}-title">${s.id==='section-3'?'<span id="section-2" class="legacy-anchor" aria-hidden="true"></span>':''}<div class="section-kicker"><span>${s.number}</span><span>${s.english}</span></div><h2 id="${s.id}-title">${esc(s.heading)}</h2>${s.mode?chart(s.mode):''}<div class="prose">${render(s.body,s.id)}</div></section>`).join('\n');
template=template.slice(0,start)+content+'\n'+template.slice(end);
template=template.replace(/<footer class="report-footer">[\s\S]*?<\/footer>/,`<footer class="report-footer"><div><strong>研究数据与原文</strong><p>6,526条逐条编码、观点与作者分布，以及${evidence.length}条原文证据。</p></div><div><a href="data/content-coded.csv" download>下载逐条编码 CSV ↓</a><a href="data/content-statistics.csv" download>下载观点统计 CSV ↓</a><a href="data/author-valence.csv" download>下载作者评价 CSV ↓</a><button class="button-text" id="download-markdown-footer">下载报告原文 ↓</button></div><small>采集：2026年10月18日 · 内容分析修订：2026年10月25日</small></footer>`);
const json=JSON.stringify(data).replaceAll('<','\\u003c').replaceAll('>','\\u003e').replaceAll('&','\\u0026');
template=template.replace(/<script type="application\/json" id="report-data">[\s\S]*?<\/script>/,`<script type="application/json" id="report-data">${json}</script>`);
fs.writeFileSync(path.join(root,'web/page.template.html'),template);
console.log(JSON.stringify({sections:9,tables,evidence:evidence.length,quotes:(template.match(/<blockquote>/g)||[]).length}));
