"""Read-only targeted diagnosis; never promotes or rewrites collection results."""
from observer.core import Study, GateError, digest, now, read_json, read_jsonl, write_json
from observer.collect import payload, rid, normalize
from observer.web_api import NormalWebAPI
from observer import small


def find_reply(data, target):
    """An adjacent comment in a jump response is not the requested comment."""
    stack = list(data.get('replies') or [])
    if isinstance(data.get('root'), dict):
        stack.append(data['root'])
    found = []
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            raise GateError('lookup_comment_schema_changed')
        if node.get('rpid_str') or node.get('rpid'):
            if rid(node) == target:
                found.append(node)
        stack.extend(node.get('replies') or [])
    if not found:
        return None
    identity = lambda r: (str(r.get('root_str') or r.get('root', 0)),
                          str(r.get('parent_str') or r.get('parent', 0)),
                          r.get('ctime'), (r.get('content') or {}).get('message'), r.get('author_id'))
    if any(identity(r) != identity(found[0]) for r in found[1:]):
        raise GateError('conflicting_exact_lookup_results')
    return found[0]


def main():
    s = Study('正式采集_小样本v1_20261018')
    small.check(s)
    final_name = 'small_repair_001_diagnosis.json'
    if (s.path / final_name).exists():
        done = s.frozen(final_name)
        print({'status': 'already_sealed_no_network', 'parents_found': sum(x['target_found'] for x in done['lookups'])})
        return
    selection = s.frozen('small_video_selection.json')
    collection = read_json(s.path / 'small_collection.json')
    rows = read_jsonl(s.path / 'small_comments.jsonl')
    observations = read_jsonl(s.path / 'small_observations.jsonl')
    assert collection['selection_hash'] == digest(selection)
    assert collection['comments_hash'] == digest(rows) and collection['observations_hash'] == digest(observations)
    if not (s.path / 'small_collection_attempt_003_failed.json').exists():
        small.seal(s, 'small_collection_attempt_003_failed.json', dict(
            collection=collection, comments=rows, observations=observations,
            execution=read_json(s.path / 'small_collection_execution_latest.json'),
            note='Archive of existing stopped run before targeted diagnosis; does not claim current code produced the historical run.'))
    ids = {r['id'] for r in rows}
    missing = [dict(bvid=r['bvid'], root_id=r['root_id'], parent_id=r['parent_id'])
               for r in rows if r['parent_id'] != '0' and r['parent_id'] not in ids]
    assert len(missing) == 6 and len({r['parent_id'] for r in missing}) == 6
    videos = {r['bvid']: r for r in selection['videos']}
    plan = dict(selection_hash=digest(selection), original_collection_hash=digest(collection),
                capture_namespace='repair_001', missing_relations=missing,
                mismatch_root_id='317186872241', mismatch_bvid='BV1AQJU6hE93',
                purpose='Targeted normal GET lookups; no identity changes, source replacement or statistical gate relaxation.')
    reg_name = 'small_repair_001_registration.json'
    if (s.path / reg_name).exists():
        reg = s.frozen(reg_name)
        for k, v in plan.items():
            assert reg[k] == v
    else:
        small.seal(s, reg_name, plan)
    ignore = s.path / '.gitignore'
    text = ignore.read_text('utf-8') if ignore.exists() else ''
    if 'cache_captures/' not in text.splitlines():
        ignore.write_text(text.rstrip() + '\ncache_captures/\n', encoding='utf-8')
    api = NormalWebAPI(s, capture_namespace='repair_001')
    result = dict(selection_hash=digest(selection), original_collection_hash=digest(collection),
                  capture_namespace='repair_001', lookups=[], mismatched_thread={})
    try:
        for item in missing:
            env = api.get('reply_jump_web', dict(oid=videos[item['bvid']]['aid'], type=1, rpid=item['parent_id']))
            response = env['response']
            target = find_reply(response.get('data') or {}, item['parent_id']) if response['code'] == 0 else None
            row = dict(**item, api_code=response['code'], message=response.get('message'),
                       target_found=target is not None, response_hash=env['response_hash'], captured_at=env['captured_at'])
            if target is not None:
                row['recovered_comment'] = normalize(target, item['bvid'], root=item['root_id'])
                row['source_comment'] = target
            result['lookups'].append(row)
            write_json(s.path / 'small_repair_001_progress.json', dict(at=now(), **result))
            print(dict(parent_id=item['parent_id'], target_found=row['target_found'], api_code=row['api_code']), flush=True)
        bv, root = plan['mismatch_bvid'], plan['mismatch_root_id']
        env = api.get('replies', dict(oid=videos[bv]['aid'], type=1, root=root, pn=1, ps=20))
        data = payload(env)
        result['mismatched_thread'] = dict(bvid=bv, root_id=root, captured_at=env['captured_at'],
            response_hash=env['response_hash'], page=data.get('page'),
            current_root_reply_count=(data.get('root') or {}).get('rcount'),
            returned_IDs_and_times=[dict(id=rid(r), ctime=r.get('ctime')) for r in data.get('replies') or []])
        small.seal(s, final_name, result)
    except GateError as exc:
        write_json(s.path / 'small_repair_001_FAILED.json', dict(at=now(), reason=str(exc), **result))
        raise
    print({'status': 'diagnosis_saved_no_collection_promotion',
           'parents_found': sum(r['target_found'] for r in result['lookups']),
           'parents_requested': len(result['lookups']),
           'current_thread_count': result['mismatched_thread']['current_root_reply_count']})


if __name__ == '__main__':
    main()
