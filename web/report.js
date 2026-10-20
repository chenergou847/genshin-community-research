(() => {
  'use strict';
  const data=JSON.parse(document.getElementById('report-data').textContent);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const menu=document.getElementById('menu-toggle');
  function closeNav(){document.body.classList.remove('nav-open');menu.setAttribute('aria-expanded','false');}
  menu.addEventListener('click',()=>{const open=document.body.classList.toggle('nav-open');menu.setAttribute('aria-expanded',String(open));});
  document.getElementById('nav-backdrop').addEventListener('click',closeNav);
  document.querySelectorAll('.sidebar nav a').forEach(a=>a.addEventListener('click',closeNav));
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeNav();});
  document.getElementById('focus-toggle').addEventListener('click',e=>{const focus=document.body.classList.toggle('focus-reading');e.currentTarget.setAttribute('aria-pressed',String(focus));e.currentTarget.textContent=focus?'显示目录':'聚焦阅读';});
  document.getElementById('print-button').addEventListener('click',()=>window.print());
  function download(){const blob=new Blob([data.markdown],{type:'text/markdown;charset=utf-8'});const a=document.createElement('a');const url=URL.createObjectURL(blob);a.href=url;a.download='B站高难副本社区观察报告_20261020.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  document.getElementById('download-markdown').addEventListener('click',download);
  document.getElementById('download-markdown-footer').addEventListener('click',download);
  const topButton=document.getElementById('back-to-top');
  topButton.addEventListener('click',()=>window.scrollTo({top:0,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'}));
  const sections=[...document.querySelectorAll('section.report-section')];
  const navs=[...document.querySelectorAll('.sidebar nav a')];
  let scheduled=false;
  function onScroll(){scheduled=false;const y=window.scrollY;const end=document.documentElement.scrollHeight-window.innerHeight;document.getElementById('reading-progress').style.width=(end?Math.min(100,100*y/end):0)+'%';topButton.classList.toggle('visible',y>700);let current=sections.findLast(s=>s.getBoundingClientRect().top<180);navs.forEach(a=>{const selected=!!current&&a.dataset.section===current.id;a.classList.toggle('active',selected);if(selected)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current');});}
  window.addEventListener('scroll',()=>{if(!scheduled){requestAnimationFrame(onScroll);scheduled=true;}},{passive:true});window.addEventListener('resize',onScroll);onScroll();
  document.querySelectorAll('.topic-chart').forEach(chart=>{
    chart.querySelectorAll('[data-metric]').forEach(button=>button.addEventListener('click',()=>{
      const kind=button.dataset.metric;chart.querySelectorAll('[data-metric]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
      const themes=chart.dataset.themes.split(',');
      chart.querySelector('.bars').innerHTML=themes.map(t=>{const m=data.metrics.find(x=>x.mode===chart.dataset.mode&&x.theme===t&&x.metric_type===kind);return `<div class="bar-row"><div class="bar-heading"><span>${esc(m.theme_label)}</span><span><strong>${(100*m.equal_share_related).toFixed(1)}%</strong><small>${m.n.toLocaleString('en-US')} 条</small></span></div><div class="bar-track"><div class="bar-fill" style="width:${m.equal_share_related*100}%"></div></div></div>`;}).join('');
    }));
  });
  const dialog=document.getElementById('evidence-dialog');
  function showEvidence(index){const e=data.evidence.find(x=>x.index===Number(index));if(!e)return;const r=e.row;document.getElementById('evidence-title').textContent=`证据 ${e.index} · ${e.mode}`;const ancestors=e.ancestors.slice().reverse();document.getElementById('evidence-content').innerHTML=`<div class="evidence-facts"><span>评论 ID：${esc(r.id)}</span><span>${esc(r.ctime_bjt.replace('T',' '))}</span><span>采集快照 ${esc(r.like)} 赞</span><span>${r.level==='root'?'根评论':'楼中楼回复'}</span></div><div class="full-quote">${esc(r.text)}</div><p class="dialog-source"><a href="https://www.bilibili.com/video/${encodeURIComponent(r.bvid)}/" target="_blank" rel="noopener noreferrer">打开原视频 ${esc(r.bvid)} ↗</a></p><h3 class="context-heading">${ancestors.length?'已保存的可读上文 · 按根评论至直接父评论排列':'此条为根评论，无祖先上文'}</h3>${ancestors.map(a=>`<article class="context-item"><small>${a.level==='root'?'根评论':'上文回复'} · ${esc(a.id)} · ${esc((a.ctime_bjt||'').replace('T',' '))}</small><p>${esc(a.text)}</p></article>`).join('')}<p class="dialog-note">原文及上文均来自既有标准化保存档；未补写缺失内容。赞数为采集快照，不等于赞同人数。此处展示个案，不代表多来源共识或玩家占比。</p>`;if(!dialog.open)dialog.showModal();}
  document.addEventListener('click',e=>{const button=e.target.closest('[data-evidence]');if(button)showEvidence(button.dataset.evidence);});
  document.getElementById('dialog-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
})();
