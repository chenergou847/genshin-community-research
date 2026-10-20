import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import crypto from 'node:crypto';

const dir = path.dirname(fileURLToPath(import.meta.url));
const workspace = path.dirname(dir);
const bundle = path.join(workspace, 'B站社区观察_全链条证明材料_20261020', '完整项目材料');
const source = path.join(bundle, '01_当前交付', '04_社区观察分析报告.md');
const revision = path.join(bundle, '04_报告修订_20261019');
const require = createRequire('LOCAL_USER_HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.loader.cjs');
const { marked } = await import(pathToFileURL(require.resolve('marked')));
const md = fs.readFileSync(source, 'utf8');
const analysis = JSON.parse(fs.readFileSync(path.join(bundle, '01_当前交付/编码分析数据.json'), 'utf8'));
const evidence = JSON.parse(fs.readFileSync(path.join(revision, '已核对评论及父链.json'), 'utf8'));
const css = fs.readFileSync(path.join(dir, 'report.css'), 'utf8');
const js = fs.readFileSync(path.join(dir, 'report.js'), 'utf8');
const escape = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sha = s => crypto.createHash('sha256').update(s).digest('hex');
const sections = [];
const pieces = md.split(/^## (.+)$/m);
const intro = pieces[0].trim().split(/\n\n+/);
if (pieces.length !== 21 || evidence.length !== 26) throw new Error('Unexpected report structure');
const title = intro[0].replace(/^# /, '');
const metadata = intro[1];
const summary = intro.slice(2).join('\n\n');
const localLinks = [];
marked.use({ walkTokens(token) {
  if (token.type === 'link' && !/^(https?:|#)/.test(token.href)) {
    const absolute = path.resolve(path.dirname(source), token.href);
    if (!fs.existsSync(absolute)) throw new Error(`Missing local source: ${token.href}`);
    token.href = path.relative(dir, absolute).replaceAll('\\', '/');
    localLinks.push(token.href);
  }
}});
const short = ['主要发现', '收集规则与落实', '统计口径与点赞', '深境螺旋', '幻想真境剧诗', '幽境危战', '玩家的五组期待', '研究边界', '检索关键词', '证据与数据'];
const english = ['FINDINGS', 'RESEARCH PROCESS', 'READING THE DATA', 'SPIRAL ABYSS', 'IMAGINARIUM THEATER', 'STYGIAN ONSLAUGHT', 'PLAYER EXPECTATIONS', 'SCOPE & LIMITS', 'SEARCH TERMS', 'EVIDENCE INDEX'];
const modeMap = {3: 'abyss', 4: 'theater', 5: 'stygian'};
let tables = 0;
function render(text, sectionId) {
  let html = marked.parse(text, {gfm: true, breaks: false});
  let sub = 0;
  html = html.replace(/<h3>/g, () => `<h3 id="${sectionId}-sub-${++sub}">`);
  html = html.replace(/<table>/g, () => `<div class="table-scroll" role="region" aria-label="报告表格 ${++tables}" tabindex="0"><table>`).replaceAll('</table>', '</table></div>');
  html = html.replace(/<a href="(https?:[^\"]*)">/g, '<a href="$1" target="_blank" rel="noopener noreferrer">');
  html = html.replace(/<p>(<a[^>]+>证据(\d+)｜原视频<\/a>[\s\S]*?)<\/p>/g,
    (_, content, n) => `<p class="evidence-meta">${content}<button class="evidence-open" data-evidence="${n}" aria-label="查看证据${n}的原文和上文">原文与上文 <span aria-hidden="true">↗</span></button></p>`);
  // 对普通正文的证据编号增加内嵌阅读入口，不改动已有链接或代码内容。
  let protectedDepth = 0;
  html = html.split(/(<[^>]+>)/g).map(part => {
    if (part.startsWith('<')) {
      if (/^<(a|code|button)\b/.test(part)) protectedDepth++;
      if (/^<\/(a|code|button)>/.test(part)) protectedDepth--;
      return part;
    }
    return protectedDepth ? part : part.replace(/证据(\d{3,4})/g, (all,n) => evidence.some(e => e.semantic_index === Number(n)) ? `<button class="inline-evidence" data-evidence="${n}">${all}</button>` : all);
  }).join('');
  if (sectionId === 'section-b') {
    html = html.replace(/<tr>\s*<td>(\d+)<\/td>/g, (_,n) => `<tr><td><button class="inline-evidence" data-evidence="${n}">${n} ↗</button></td>`);
  }
  return html;
}
function graph(mode) {
  const themes = mode === 'theater' ? ['roster_build','buff_and_route','retry_time_cost'] : ['roster_build','damage_threshold','mechanic_understanding'];
  const bars = themes.map(t => {
    const m = analysis.statistics.metrics.find(x => x.mode === mode && x.theme === t && x.metric_type === '主题');
    return `<div class="bar-row"><div class="bar-heading"><span>${escape(m.theme_label)}</span><span><strong>${(100*m.equal_share_related).toFixed(1)}%</strong><small>${m.n.toLocaleString('en-US')} 条</small></span></div><div class="bar-track"><div class="bar-fill" style="width:${m.equal_share_related*100}%"></div></div></div>`;
  }).join('');
  const related = analysis.statistics.totals.find(x => x.mode === mode).related;
  return `<figure class="topic-chart" data-mode="${mode}" data-themes="${themes.join(',')}"><div class="chart-top"><figcaption><span class="overline">讨论结构</span><strong>同一主题，区分谈及与本人问题</strong></figcaption><div class="chart-switch" role="group" aria-label="选择图表指标"><button type="button" data-metric="主题" aria-pressed="true">谈及主题</button><button type="button" data-metric="本人明确问题" aria-pressed="false">本人问题</button></div></div><div class="bars">${bars}</div><p class="chart-note">分母：本副本 ${related.toLocaleString('en-US')} 条相关发言。主题可重叠；不同副本的窗口与来源不同，不作质量排名。完整主题见下表。</p></figure>`;
}
for (let i=1; i<pieces.length; i+=2) {
  const n = (i-1)/2;
  const id = n < 8 ? `section-${n+1}` : n === 8 ? 'section-a' : 'section-b';
  sections.push({id, heading: pieces[i], short: short[n], english: english[n], number: n < 8 ? String(n+1).padStart(2,'0') : n===8?'A':'B', body:pieces[i+1]});
}
const evidencePayload = evidence.map(e => ({index:e.semantic_index, mode:analysis.modes[e.row.mode], row:{
  id:e.row.id, bvid:e.row.bvid, root_id:e.row.root_id, parent_id:e.row.parent_id,
  like:e.row.like, ctime_bjt:e.row.ctime_bjt, text:e.row.text, level:e.row.level,
}, ancestors:e.ancestors.map(a => ({id:a.id,text:a.text,ctime_bjt:a.ctime_bjt,level:a.level}))}));
const json = value => JSON.stringify(value).replaceAll('<','\\u003c').replaceAll('>','\\u003e').replaceAll('&','\\u0026');
const contents = sections.map((s,n) => `<section class="report-section ${n===6?'expectations':''}" id="${s.id}" aria-labelledby="${s.id}-title"><div class="section-kicker"><span>${s.number}</span><span>${s.english}</span></div><h2 id="${s.id}-title">${escape(s.heading)}</h2>${modeMap[n] ? graph(modeMap[n]) : ''}<div class="prose">${render(s.body,s.id)}</div></section>`).join('\n');
const introHtml = render(summary, 'intro');
const nav = sections.map(s => `<a href="#${s.id}" data-section="${s.id}"><span class="nav-num">${s.number}</span><span>${s.short}</span></a>`).join('');
const archiveLink = path.relative(dir, path.join(path.dirname(bundle),'00_材料总目录.md')).replaceAll('\\','/');
const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>${escape(title)} · 展示版</title><meta name="description" content="以6,526条已存发言观察三种高难副本的社区反馈、态度和玩家期待。完整报告、口径与26条原文证据。"><style>${css}</style></head>
<body>
<a class="skip-link" href="#main">跳到报告正文</a>
<header class="topbar"><a href="#top" class="brand" aria-label="回到报告开头"><svg viewBox="0 0 24 24" width="27" height="27" aria-hidden="true"><path d="M4 4h16v12H9l-5 4V4Z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8 8h8M8 12h5" stroke="currentColor" stroke-width="1.6"/></svg><span>社区观察<span class="brand-en">COMMUNITY STUDY</span></span></a><div class="topbar-note">原神 · 高难副本 / 2026.10</div><div class="toolbar"><button id="focus-toggle" aria-pressed="false" title="收起侧栏，聚焦正文">聚焦阅读</button><button id="print-button">打印 / PDF</button><button class="menu-toggle" id="menu-toggle" aria-expanded="false" aria-controls="sidebar">目录 <span aria-hidden="true">☰</span></button></div><div class="reading-progress" aria-hidden="true"><span id="reading-progress"></span></div></header>
<div class="nav-backdrop" id="nav-backdrop"></div>
<aside class="sidebar" id="sidebar" aria-label="报告目录"><div class="nav-label">报告目录 <span>CONTENTS</span></div><nav>${nav}</nav><div class="nav-bottom"><div class="scope-dot"></div><strong>固定来源 · 已存正文</strong><p>完整研究报告<br>2026 年 10 月 20 日修订</p><button id="download-markdown">下载 Markdown 原文 <span aria-hidden="true">↓</span></button></div></aside>
<main class="page" id="main">
<div class="report-shell">
<section class="hero" id="top" aria-labelledby="report-title"><div class="hero-eyebrow"><span class="edition">研究记录 / 01</span><span>BILIBILI COMMUNITY OBSERVATION</span></div><h1 id="report-title">B站高难副本<br><span>社区观察报告</span></h1><div class="hero-bottom"><p class="hero-question">社区在反馈什么，<br>玩家期待怎样的高难副本？</p><span class="hero-index" aria-hidden="true">2026<br><b>10</b></span></div><p class="hero-subtitle">深境螺旋 <span>·</span> 幻想真境剧诗 <span>·</span> 幽境危战</p><div class="hero-stats"><div><strong>60</strong><span>固定视频来源</span></div><div><strong>6,526</strong><span>已存窗口发言</span></div><div><strong>4,698</strong><span>相关发言</span></div><div><strong>3</strong><span>副本观察场域</span></div></div><div class="hero-meta">${escape(metadata)}</div><div class="hero-intro prose">${introHtml}</div><div class="hero-actions"><a class="button-primary" href="#section-1">开始阅读 <span aria-hidden="true">↓</span></a><a class="button-text" href="#section-b">查看 26 条原文证据 <span aria-hidden="true">↗</span></a></div><p class="scope-note">一条发言计一次，条数不等于玩家人数；本报告描述固定来源中已规范化保存的窗口正文。</p></section>
${contents}
<footer class="report-footer"><div><strong>从发言回到语境，从分歧理解期待。</strong><p>正文、18 处引文和 26 条证据及已存可读上文均在本页中。数据附件链接需保留相邻的完整材料总档。</p></div><div><a href="${escape(archiveLink)}">完整材料总目录 ↗</a><button class="button-text" id="download-markdown-footer">下载报告原文 ↓</button></div><small>本页由 2026 年 10 月 20 日修订稿生成。数据与编码保持冻结；无新增采集或态度比例。</small></footer>
</div></main>
<button class="back-to-top" id="back-to-top" aria-label="回到报告顶部">↑</button>
<dialog id="evidence-dialog" aria-labelledby="evidence-title"><div class="dialog-head"><div><span class="overline">回到原文</span><h2 id="evidence-title">证据原文</h2></div><button id="dialog-close" aria-label="关闭证据窗口">关闭 <span aria-hidden="true">×</span></button></div><div id="evidence-content"></div></dialog>
<script type="application/json" id="report-data">${json({evidence:evidencePayload,metrics:analysis.statistics.metrics,modes:analysis.modes,markdown:md})}</script><script>${js}</script>
</body></html>`;
fs.writeFileSync(path.join(dir, 'index.html'), html);
// 不把内嵌 Markdown 当作可见正文：仅对真实渲染区检查原稿的语义单元。
const strip = text => text.replace(/<[^>]+>/g,'').replace(/&#(\d+);/g,(_,n)=>String.fromCodePoint(Number(n)))
  .replace(/&#x([\da-f]+);/gi,(_,n)=>String.fromCodePoint(parseInt(n,16)))
  .replaceAll('&amp;','&').replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&quot;','"').replaceAll('&#39;',"'")
  .replaceAll('&nbsp;',' ').replace(/\s+/g,'');
const visible = strip(html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi,''));
const originalRendered = marked.parse(md,{gfm:true});
const units = [...originalRendered.matchAll(/<(p|h1|h2|h3|li|th|td)\b[^>]*>([\s\S]*?)<\/\1>/g)].map(m=>strip(m[2])).filter(Boolean);
const missingUnits = units.filter(unit=>!visible.includes(unit));
if(missingUnits.length)throw new Error(`Visible content missing: ${JSON.stringify(missingUnits.slice(0,5))}`);
const check = {source:path.relative(workspace,source).replaceAll('\\','/'), source_sha256:sha(md),html_sha256:sha(html),
  original_sections:sections.length,rendered_sections:sections.length,source_tables:(md.match(/^\|(?: ---|---)/gm)||[]).length,
  rendered_tables:tables,source_quote_blocks:(md.match(/^> /gm)||[]).length,embedded_evidence:evidence.length,
  original_markdown_embedded:true,visible_source_units_checked:units.length,missing_visible_source_units:missingUnits,
  local_attachment_links:localLinks,external_render_dependencies:[],
  raw_data_modified:false,source_markdown_modified:false,output_bytes:Buffer.byteLength(html)};
if (check.source_tables !== check.rendered_tables || check.source_quote_blocks !== 18) throw new Error('Content count mismatch');
fs.writeFileSync(path.join(dir, '生成与内容核对.json'), JSON.stringify(check,null,2));
fs.writeFileSync(path.join(dir, '打开说明.md'), '# 报告 HTML 展示版\n\n双击 `index.html` 即可阅读。页面样式、脚本、完整报告正文和26条证据均已内嵌，无需联网加载字体或图表。\n\n支持章节导航、谈及主题／本人问题切换、点击证据编号查看完整原文和已存可读上文、聚焦阅读、下载原始Markdown、打印／保存PDF。\n\n原视频链接需要网络；CSV／JSON等完整数据附件指向相邻的 `B站社区观察_全链条证明材料_20261020`，分享时如需打开这些附件，应保留该材料目录。本页单独分享仍可读完整报告和26条证据。\n\n原报告、数据、编码及完整材料档案未改动。源报告和HTML哈希、章节与表格核对见 `生成与内容核对.json`。`build_report.mjs`、`report.css`、`report.js`仅用于本地重建，使用网页只需 `index.html`。\n');
console.log(JSON.stringify({status:'built',...check},null,2));
