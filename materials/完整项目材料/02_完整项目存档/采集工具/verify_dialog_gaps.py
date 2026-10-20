"""Bounded follow-up using dialog IDs observed in saved comment responses."""
from collections import defaultdict
import json

from observer.core import Study, GateError, digest, now, read_json, read_jsonl, write_json
from observer.collect import normalize, payload
from observer.web_api import NormalWebAPI
from observer import small
from audit_collection_integrity import nodes, cid


def main():
    s = Study('正式采集_小样本v1_20261018')
    name = 'small_dialog_verification_012'
    if (s.path / (name + '_result.json')).exists():
        print(json.dumps(s.frozen(name + '_result.json')['summary'], ensure_ascii=False))
        return
    collection = read_json(s.path / 'small_collection.json')
    rows = read_jsonl(s.path / 'small_comments.jsonl')
    selection = s.frozen('small_video_selection.json')
    assert digest(rows) == collection['comments_hash']
    videos = {v['bvid']: v for v in selection['videos']}
    ids = {r['id'] for r in rows}
    children = {r['id']: r for r in rows if r['parent_id'] != '0' and r['parent_id'] not in ids}
    targets = {r['parent_id'] for r in children.values()}
    groups = defaultdict(set)
    for folder in (s.path / 'cache', s.path / 'cache_captures' / 'integrity_010_20261019'):
        for p in folder.glob('*.json'):
            env = read_json(p)
            assert digest(env['response']) == env['response_hash']
            for node in nodes(env['response'].get('data')):
                ident = cid(node)
                if ident in children and str(node.get('dialog') or '0') != '0':
                    child = children[ident]
                    groups[child['bvid'], child['root_id'], str(node['dialog'])].add(ident)
    # This dialog ID was positively observed and enumerated in repair_005.
    prior = s.frozen('small_repair_005_dialog_first.json')
    assert '320979074688' in prior['ids']
    groups['BV12fJe6bEbz', '320978740800', '320979074688'].update(
        r['id'] for r in children.values() if r['bvid'] == 'BV12fJe6bEbz')
    plan = dict(collection_hash=digest(collection), selection_hash=digest(selection),
                groups=[dict(bvid=b, root_id=r, dialog_id=d, known_children=sorted(ch))
                        for (b, r, d), ch in sorted(groups.items())],
                max_pages_per_dialog=4, max_requests=80,
                exact_recheck_source='BV1zLJv6mE8T',
                exact_recheck_IDs=['321024585584', '321050042832'],
                changed_zero_source='BV1jjJY6MEwP',
                purpose='Read only observed dialogs and changed-source evidence; never promote, replace or freeze.')
    small.seal(s, name + '_registration.json', plan)
    result = dict(started_at=now(), collection_hash=digest(collection), requests=0, dialogs=[],
                  exact_rechecks=[], changed_zero_capture=None, status='RUNNING')

    def progress():
        write_json(s.path / (name + '_progress.json'), dict(at=now(), **result))

    progress()
    try:
        api = NormalWebAPI(s, capture_namespace='integrity_012_dialog_20261019')

        def get(route, params):
            result['requests'] += 1
            if result['requests'] > plan['max_requests']:
                raise GateError('registered_request_budget_reached')
            return api.get(route, params)

        for group in plan['groups']:
            record = dict(**group, pages=[], normal_end=False, budget_exhausted=False)
            params = dict(oid=videos[group['bvid']]['aid'], type=1, root=group['root_id'],
                          dialog=group['dialog_id'], size=20)
            seen = set()
            for pn in range(1, plan['max_pages_per_dialog'] + 1):
                token = json.dumps(params, sort_keys=True)
                if token in seen:
                    raise GateError('dialog_cursor_loop')
                seen.add(token)
                env = get('reply_dialog_web', params)
                data = payload(env)
                cursor = data.get('cursor')
                if not isinstance(cursor, dict):
                    raise GateError('dialog_cursor_missing')
                returned = data.get('replies') or []
                found = [normalize(n, group['bvid'], root=group['root_id'])
                         for n in nodes(data) if cid(n) in targets]
                record['pages'].append(dict(pn=pn, ids=[cid(n) for n in returned], cursor=cursor,
                    candidates=found, captured_at=env['captured_at'], response_hash=env['response_hash']))
                if not returned and cursor.get('is_end') is True:
                    record['normal_end'] = True
                    break
                if not returned or cursor.get('next') is None:
                    raise GateError('dialog_terminal_or_next_ambiguous')
                params = dict(params, min_floor=cursor['next'])
            else:
                record['budget_exhausted'] = True
            record['positive_control_found'] = bool(set(group['known_children']) & {
                i for p in record['pages'] for i in p['ids']})
            result['dialogs'].append(record)
            progress()
        for target in plan['exact_recheck_IDs']:
            bv = plan['exact_recheck_source']
            env = get('roots_web', dict(oid=videos[bv]['aid'], type=1, mode=2, next=0, ps=20, plat=1, seek_rpid=target))
            found = [n for n in nodes(payload(env)) if cid(n) == target]
            result['exact_rechecks'].append(dict(bvid=bv, id=target, exact_ID_found=bool(found),
                captured_at=env['captured_at'], response_hash=env['response_hash']))
            progress()
        # The page shows a new post-T0 comment. Save its actual body separately.
        env = get('roots_web', dict(oid=videos[plan['changed_zero_source']]['aid'], type=1,
                                  mode=2, next=0, ps=20, plat=1, web_location=1315875))
        data = payload(env)
        actual = [normalize(n, plan['changed_zero_source']) for n in data.get('replies') or []]
        result['changed_zero_capture'] = dict(bvid=plan['changed_zero_source'], comments=actual,
            cursor=data.get('cursor'), captured_at=env['captured_at'], response_hash=env['response_hash'])
        result['status'] = 'BOUNDED_DIALOG_VERIFICATION_ENDED'
    except GateError as exc:
        result['status'] = 'STOPPED_WITH_DIAGNOSTIC_FAILURE'
        result['reason'] = str(exc)
    result['finished_at'] = now()
    recovered = {c['id'] for d in result['dialogs'] for p in d['pages'] for c in p['candidates']}
    result['summary'] = dict(status=result['status'], requests=result['requests'],
        dialog_groups_attempted=len(result['dialogs']), dialog_groups_planned=len(plan['groups']),
        normal_ends=sum(d['normal_end'] for d in result['dialogs']),
        positive_controls=sum(d['positive_control_found'] for d in result['dialogs']),
        parent_bodies_recovered=len(recovered), recovered_IDs=sorted(recovered),
        master_collection_unchanged=digest(read_json(s.path / 'small_collection.json')) == digest(collection),
        formal_comment_sample_generated=False)
    small.seal(s, name + '_result.json', result)
    progress()
    print(json.dumps(result['summary'], ensure_ascii=False), flush=True)
    if result.get('reason'):
        print(json.dumps({'reason': result['reason']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
