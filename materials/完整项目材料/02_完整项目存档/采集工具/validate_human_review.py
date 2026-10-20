"""Validate an explicitly exported human review without modifying canonical data."""
import argparse
from collections import Counter
import json
from pathlib import Path
from observer.core import read_json, digest
from continue_snapshot_coding import S, public_text
from observer.snapshot_sample import master_hashes


def validate(path):
    obj=read_json(Path(path))
    manifest=read_json(S.path/'small_snapshot_human_review_portal_manifest_001.json')
    assert obj.get('schema')==manifest['schema'],'审核格式不匹配'
    kind=obj.get('kind');assert kind in manifest['packages'],'未知审核类型'
    package=manifest['packages'][kind]
    assert obj.get('package_id')==package['package_id'],'审核包身份不匹配'
    assert obj.get('sample_draw_hash')==manifest['draw_hash'],'原样本版本不匹配'
    lookup={(r['id']):r for r in S.frozen('small_snapshot_frame_001.json')['comments']}
    assert master_hashes(S)==manifest['raw_master_hashes'],'主档已变更'
    rows=obj.get('rows');assert isinstance(rows,list),'rows 必须是数组'
    keys=[]
    for r in rows:
        key=r.get('mode','')+':'+r.get('id','');keys.append(key)
        assert key in package['expected_keys'],'未知 ID 或副本'
        for field in ['themes','self_experience_themes','problem_themes']:
            assert isinstance(r.get(field),list) and len(set(r[field]))==len(r[field]),'主题必须是无重复数组'
            assert set(r[field])<=set(manifest['themes']),'主题无效'
        assert r.get('relevance') in ['related','irrelevant','unknown'],'相关性无效'
        assert r.get('problem_status') in ['current_reported','none_explicit','retrospective_only','unknown'],'受阻状态无效'
        assert r.get('theme_status') in ['known','unknown'],'主题状态无效'
        assert r.get('experience_kind') in manifest['kinds'],'发言类型无效'
        assert r.get('sentiment') in ['positive','negative','mixed','neutral','unknown'],'倾向值无效'
        assert set(r['problem_themes'])<=set(r['self_experience_themes'])<=set(r['themes']),'主题层级无效'
        if r['relevance']!='related':
            assert not r['themes'] and not r['self_experience_themes'] and not r['problem_themes'],'非相关项不得带主题'
            assert r['problem_status']!='current_reported','非相关项不得标本期受阻'
        elif r['theme_status']=='known':
            assert r['themes'],'可判主题的相关项缺主题'
        assert bool(r['problem_themes'])==(r['problem_status']=='current_reported'),'受阻主题与状态不一致'
        assert isinstance(r.get('evidence'),str) and r['evidence'].strip() and r['evidence'].strip() in public_text(lookup[r['id']]['text']),'证据不是当前正文片段'
        assert isinstance(r.get('notes'),str) and r['notes'].strip(),'缺判断理由'
        assert isinstance(r.get('reviewer'),str) and r['reviewer'].strip(),'缺人工署名'
        assert r.get('context_checked') is True and r.get('confirmed') is True,'未确认'
        assert isinstance(r.get('confirmed_at'),str) and r['confirmed_at'],'缺确认时间'
    assert len(keys)==len(set(keys)),'重复 ID'
    assert obj.get('human_confirmed_n')==len(rows),'汇总数量不符'
    result=dict(kind=kind,validated_confirmations=len(rows),expected_n=len(package['expected_keys']),
        all_rows_complete=set(keys)==set(package['expected_keys']),
        by_mode=dict(Counter(r['mode'] for r in rows)),input_hash=digest(obj),
        identity='self_declared_human_not_independently_authenticated',
        formal_gate_passed=False,
        note='只核验数据结构、证据与样本身份；未做分歧裁决或认证审核者身份，未改研究标签及状态。')
    return result,obj


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('exported_json');args=p.parse_args()
    try:
        result,_=validate(args.exported_json)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (AssertionError,KeyError,TypeError,ValueError) as exc:
        raise SystemExit('审核结果未通过校验：'+str(exc))
