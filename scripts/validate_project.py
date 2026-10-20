"""检查公开材料完整性、去标识、页面结构及附件链接，不测编码语义准确率。"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import csv,hashlib,json,re
ROOT=Path(__file__).resolve().parent.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Page(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.links=[];self.tables=0;self.quotes=0;self.src=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='a':self.links.append(a.get('href',''))
        if 'src' in a:self.src.append(a['src'])
        if tag=='table':self.tables+=1
        if tag=='blockquote':self.quotes+=1
def main():
    provenance=json.loads((ROOT/'publication/materials-provenance.json').read_text(encoding='utf-8'))
    assert len(provenance['files'])==4642
    for r in provenance['files']:
        p=ROOT/r['path'];assert p.is_file(),r['path'];assert sha(p)==r['published_sha256'],r['path']
    paths=[p for p in (ROOT/'materials').rglob('*') if p.is_file()]
    assert len(paths)==4642,len(paths)
    for p in ROOT.rglob('*'):
        if not p.is_file() or '.git' in p.parts:continue
        if p.name in {'.private.json','.env','cookies.txt','cookie.txt'}:raise AssertionError('凭据文件')
        if p.suffix.lower() in {'.md','.json','.jsonl','.csv','.txt','.py','.js','.mjs','.html','.ndjson','.yml'}:
            try:t=p.read_text(encoding='utf-8-sig')
            except UnicodeError:continue
            assert not re.search(r'[A-Za-z]:[\\/]+Users[\\/]+',t),p.relative_to(ROOT)
            assert not re.search(r'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}',t),p.relative_to(ROOT)
            # GitHub提交隐私地址允许；其余邮箱不得进入公开内容。
            emails=re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',t)
            assert all(e.endswith('@users.noreply.github.com') for e in emails),p.relative_to(ROOT)
    html=(ROOT/'docs/index.html').read_text(encoding='utf-8');page=Page();page.feed(html)
    assert len(page.ids)==len(set(page.ids));assert page.tables==12 and page.quotes==18;assert not page.src
    for href in page.links:
        if href.startswith('#'):assert href[1:] in page.ids
        elif href.startswith('https://github.com/') and '/blob/main/' in href:
            rel=unquote(href.split('/blob/main/',1)[1]);assert (ROOT/rel).is_file(),rel
    data=json.loads(re.search(r'<script type="application/json" id="report-data">(.*?)</script>',html,re.S)[1])
    assert data['markdown']==(ROOT/'report/报告.md').read_text(encoding='utf-8')
    assert len(data['evidence'])==26
    analysis=json.loads((ROOT/'materials/完整项目材料/01_当前交付/编码分析数据.json').read_text(encoding='utf-8-sig'))
    assert len(analysis['rows'])==6526 and sum(bool(r['problem_themes']) for r in analysis['rows'])==706
    manifest=ROOT/'publication/public-files-sha256.csv'
    if manifest.exists():
        with manifest.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({'status':'PASS','materials_files':len(paths),'privacy_transformed_files':provenance['transformed_files'],
        'tables':page.tables,'quotes':page.quotes,'embedded_evidence':len(data['evidence']),'coded_rows':6526,
        'raw_data_relabelled':False,'browser_visual_validation':'原展示版未完成浏览器视觉验收；此处仅结构和静态检查'},ensure_ascii=False))
if __name__=='__main__':main()
