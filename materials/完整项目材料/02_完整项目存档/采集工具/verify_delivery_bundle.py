"""Offline content, JavaScript syntax and import validation. No human codes recorded."""
from collections import Counter
from copy import deepcopy
import json
import re
import subprocess
import tempfile
from pathlib import Path

from build_delivery_bundle import OUT, S, sha
from observer.snapshot_sample import master_hashes
from observer.core import read_json
from validate_human_review import validate


def payload(path):
    text=path.read_text(encoding='utf-8')
    found=re.search(r'<script id="payload" type="application/json">(.*?)</script>',text,re.S)
    assert found,'missing payload'
    obj=json.loads(found[1])
    assert '<' not in found[1],'unescaped markup in embedded data'
    scripts=re.findall(r'<script>(.*?)</script>',text,re.S)
    assert len(scripts)==1 and '__PAYLOAD__' not in text
    return obj,scripts[0]


def fixture(obj):
    rows=[]
    # Test labels are AI prefill copied into an in-memory fixture only.
    for row in obj['rows']:
        rows.append(dict(mode=row['mode'],id=row['id'],**row['ai'],
            reviewer='TEST_FIXTURE_NOT_ACTUAL_HUMAN',context_checked=True,confirmed=True,
            confirmed_at='2026-10-19T00:00:00Z'))
    return dict(schema=obj['schema'],package_id=obj['package_id'],kind=obj['kind'],
        sample_draw_hash=obj['sample_draw_hash'],human_confirmed_n=len(rows),rows=rows)


def validate_fixture(obj):
    name=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',suffix='.json',prefix='genshin-test-',delete=False) as f:
            name=f.name;json.dump(obj,f,ensure_ascii=False)
        return validate(name)[0]
    finally:
        if name:Path(name).unlink(missing_ok=True)


def main():
    main,script=payload(OUT/'01_600条人工核验.html')
    blind,blindscript=payload(OUT/'02_90条盲复核.html')
    assert len(main['rows'])==600 and len(blind['rows'])==90
    assert Counter(r['mode'] for r in blind['rows'])==dict.fromkeys(['abyss','theater','stygian'],30)
    assert all('ai' not in r for r in blind['rows'])
    assert {r['mode']+':'+r['id'] for r in blind['rows']}<={r['mode']+':'+r['id'] for r in main['rows']}
    assert all(re.fullmatch(r'https://www\.bilibili\.com/video/BV[A-Za-z0-9]+/',r['url']) for r in main['rows'])
    manifest=read_json(S.path/'small_snapshot_human_review_portal_manifest_001.json')
    assert master_hashes(S)==manifest['raw_master_hashes']
    assert Counter(r['ai']['relevance'] for r in main['rows'])=={'related':417,'irrelevant':125,'unknown':58}
    # Node checks syntax without opening a browser or accessing UI / networking.
    for source in [script,blindscript]:
        result=subprocess.run(['node','--check','-'],input=source,text=True,encoding='utf-8',capture_output=True)
        assert result.returncode==0,result.stderr
    good=fixture(main)
    assert validate_fixture(good)['validated_confirmations']==600
    partial=deepcopy(good);partial['rows']=partial['rows'][:1];partial['human_confirmed_n']=1
    assert not validate_fixture(partial)['all_rows_complete']
    invalid=[]
    x=deepcopy(partial);x['rows'].append(x['rows'][0]);x['human_confirmed_n']=2;invalid.append(x)
    x=deepcopy(partial);x['rows'][0]['id']='not-a-sample-ID';invalid.append(x)
    x=deepcopy(partial);x['rows'][0]['evidence']='不是当前评论里的证据';invalid.append(x)
    x=deepcopy(partial);x['rows'][0]['context_checked']=False;invalid.append(x)
    x=deepcopy(partial);x['rows'][0]['reviewer']='';invalid.append(x)
    x=deepcopy(partial);x['sample_draw_hash']='wrong';invalid.append(x)
    x=deepcopy(partial);x['rows'][0]['problem_themes']=[];invalid.append(x)
    rejected=0
    for bad in invalid:
        try:validate_fixture(bad)
        except (AssertionError,KeyError,TypeError,ValueError):rejected+=1
        else:raise AssertionError('invalid export accepted')
    # Exercise the same pure label validator used by the form, with real prefills.
    validator=script[script.index('function validLabel'):script.index('function loadEntries')]
    node_code='const DATA='+json.dumps(main,ensure_ascii=False)+';\n'
    node_code+='const themeIds=DATA.themes.map(t=>t.id),relNames={related:1,irrelevant:1,unknown:1},problemNames={current_reported:1,none_explicit:1,retrospective_only:1,unknown:1};\n'
    node_code+=validator+'\nfor(const row of DATA.rows){validLabel({...row.ai,id:row.id,mode:row.mode,reviewer:"TEST",context_checked:true,confirmed:true},row)};process.stdout.write("600 prefills validated");'
    run=subprocess.run(['node','-'],input=node_code,text=True,encoding='utf-8',capture_output=True)
    assert run.returncode==0,run.stderr
    assert master_hashes(S)==manifest['raw_master_hashes']
    qc=read_json(S.path/'small_snapshot_delivery_qc_001.json')
    qc.update(javascript_syntax_checked=True,all_600_AI_prefill_values_validated_not_human_results=True,
        partial_export_remains_incomplete=True,invalid_export_cases_rejected=rejected,
        browser_visual_verification=False,
        browser_visual_verification_note='localhost未连通；内置浏览器拒绝file协议，未尝试绕过',
        human_results_completed=0)
    (S.path/'small_snapshot_delivery_qc_001.json').write_text(json.dumps(qc,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(content_counts='600 main / 90 repeat / 0 actual human results',
        syntax_checked=True,prefill_validation='600 AI test fixtures, not human confirmations',
        invalid_cases_rejected=rejected,partial_status_verified=True,raw_unchanged=True,
        browser_visual_QA=False),ensure_ascii=False))


if __name__=='__main__':
    main()
