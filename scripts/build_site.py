"""只组合冻结报告网页；标准库实现，无网络，无采集或编码。"""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parent.parent
def main():
    config=json.loads((ROOT/'project.json').read_text(encoding='utf-8'))
    template=(ROOT/'web/page.template.html').read_text(encoding='utf-8')
    html=template.replace('{{REPORT_STYLES}}',(ROOT/'web/report.css').read_text(encoding='utf-8'))
    html=html.replace('{{REPORT_SCRIPT}}',(ROOT/'web/report.js').read_text(encoding='utf-8'))
    html=html.replace('{{REPO_BLOB}}',f'https://github.com/{config["owner"]}/{config["repository"]}/blob/main')
    assert '{{REPORT_' not in html and '{{REPO_BLOB}}' not in html
    data=json.loads(re.search(r'<script type="application/json" id="report-data">(.*?)</script>',html,re.S)[1])
    assert data['markdown']==(ROOT/'report/报告.md').read_text(encoding='utf-8')
    assert len(data['evidence'])==26
    out=ROOT/'docs/index.html';out.parent.mkdir(exist_ok=True);out.write_text(html,encoding='utf-8',newline='\n')
    print(json.dumps({'status':'built','html_bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()},ensure_ascii=False))
if __name__=='__main__':main()
