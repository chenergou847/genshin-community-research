"""离线检查HTML结构、链接、原文嵌入与数据一致性；不替代浏览器视觉验收。"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'B站社区观察_全链条证明材料_20261020/完整项目材料/01_当前交付/04_社区观察分析报告.md'


class Inspect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[];self.links=[];self.src=[];self.tables=0;self.quotes=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='a':self.links.append(a.get('href',''))
        if 'src' in a:self.src.append(a['src'])
        if tag=='table':self.tables+=1
        if tag=='blockquote':self.quotes+=1


def main():
    h=(ROOT/'index.html').read_text(encoding='utf-8')
    p=Inspect();p.feed(h)
    assert h.startswith('<!DOCTYPE html>') and h.endswith('</html>')
    assert len(p.ids)==len(set(p.ids))
    assert not p.src,p.src
    assert '<link rel="stylesheet"' not in h
    for link in p.links:
        if link.startswith('#'):assert link[1:] in p.ids,link
        elif not link.startswith(('https:','http:')):
            assert (ROOT/unquote(link)).is_file(),link
    blob=re.search(r'<script type="application/json" id="report-data">(.*?)</script>',h,re.S).group(1)
    data=json.loads(blob)
    assert data['markdown']==SOURCE.read_text(encoding='utf-8')
    assert len(data['evidence'])==26
    assert p.quotes==18 and p.tables==12
    build=json.loads((ROOT/'生成与内容核对.json').read_text(encoding='utf-8'))
    assert build['html_sha256']==hashlib.sha256(h.encode('utf-8')).hexdigest()
    assert build['source_sha256']==hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert not build['missing_visible_source_units']
    result={'status':'PASS','tables':p.tables,'quote_blocks':p.quotes,'embedded_evidence':len(data['evidence']),
        'unique_ids':len(p.ids),'links_checked':len(p.links),'external_render_dependencies':p.src,
        'embedded_markdown_equals_source':True,'visible_source_units_checked':build['visible_source_units_checked'],
        'browser_visual_review':'未完成：本机HTTP预览连接超时，file协议被浏览器URL策略禁止；未绕过策略',
        'interaction_checks':'JavaScript语法已单独检查；没有声称通过真实浏览器交互验收'}
    (ROOT/'静态校验结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
