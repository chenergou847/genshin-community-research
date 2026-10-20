"""One bounded, read-only verification pass of the seven saved integrity holds."""
from collections import defaultdict
import argparse
import json

from observer.core import Study, GateError, digest, now, read_json, read_jsonl, write_json
from observer.collect import collect_video, normalize, payload
from observer.web_api import NormalWebAPI
from observer import small
from audit_collection_integrity import nodes, cid
from finalize_targeted_repair import validate_replacement


NAME = 'small_gap_verification_010'
NAMESPACE = 'integrity_010_20261019'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--study', default='正式采集_小样本v1_20261018')
    args = ap.parse_args()
    s = Study(args.study)
    final_name = NAME + '_result.json'
    if (s.path / final_name).exists():
        result = s.frozen(final_name)
        print(json.dumps(result['summary'], ensure_ascii=False))
        return
    selection = s.frozen('small_video_selection.json')
    collection = read_json(s.path / 'small_collection.json')
    rows = read_jsonl(s.path / 'small_comments.jsonl')
    observations = read_jsonl(s.path / 'small_observations.jsonl')
    assert collection['selection_hash'] == digest(selection)
    assert collection['comments_hash'] == digest(rows) and collection['observations_hash'] == digest(observations)
    assert not (s.path / 'small_comment_frame.json').exists()
    videos = {v['bvid']: v for v in selection['videos']}
    byid = {r['id']: r for r in rows}
    missing = defaultdict(list)
    for row in rows:
        if row['parent_id'] != '0' and row['parent_id'] not in byid:
            missing[(row['bvid'], row['parent_id'])].append(row)
    held = [v for v in collection['videos'] if v['status'] != 'enumerated_pending_review']
    zero = [v['bvid'] for v in collection['videos'] if v['unique_count'] == 0]
    plan = dict(selection_hash=digest(selection), collection_hash=digest(collection),
                namespace=NAMESPACE, sources_held=[v['bvid'] for v in held],
                zero_count_sources=zero,
                unique_parent_targets=[dict(bvid=b, parent_id=p, root_id=children[0]['root_id'])
                                       for (b, p), children in sorted(missing.items())],
                small_count_recaptures=['BV1zLJv6mE8T', 'BV1k6pK6UE9i'],
                limits=dict(one_metadata_read_per_zero_or_held_source=True, one_fresh_first_root_page_per_hold=True,
                            one_positive_control_per_parent_missing_source=True, one_seek_per_parent=True,
                            max_detail_pages_per_affected_root=5, max_diagnostic_requests=180,
                            full_recapture_limit=2),
                rules='Stop on access/rate/schema/paging anomaly; no promotion, no master-data changes, no window extension.')
    reg_name = NAME + '_registration.json'
    if (s.path / reg_name).exists():
        reg = s.frozen(reg_name)
        assert all(reg[k] == v for k, v in plan.items())
    else:
        small.seal(s, reg_name, plan)
    archive_name = 'small_collection_before_integrity_010.json'
    if not (s.path / archive_name).exists():
        small.seal(s, archive_name, dict(collection=collection, comments=rows, observations=observations,
                                        reason='Immutable full 60-source archive before independent verification.'))
    result = dict(started_at=now(), selection_hash=digest(selection), collection_hash=digest(collection),
                  namespace=NAMESPACE, metadata=[], first_roots=[], positive_controls=[], parent_lookups=[],
                  detail_threads=[], recaptures=[], requests=0, status='RUNNING')

    def progress():
        write_json(s.path / (NAME + '_progress.json'), dict(at=now(), **result))

    progress()
    try:
        api = NormalWebAPI(s, capture_namespace=NAMESPACE)

        def get(route, params):
            result['requests'] += 1
            if result['requests'] > plan['limits']['max_diagnostic_requests']:
                raise GateError('registered_diagnostic_request_budget_reached')
            return api.get(route, params)

        def ref(env):
            return dict(captured_at=env['captured_at'], response_hash=env['response_hash'])

        def exact(env, target):
            matches = [n for n in nodes(payload(env)) if cid(n) == target]
            if not matches:
                return None
            identities = {(str(n.get('root_str') or n.get('root', 0)),
                           str(n.get('parent_str') or n.get('parent', 0)), n.get('ctime'),
                           (n.get('content') or {}).get('message'), n.get('author_id')) for n in matches}
            if len(identities) != 1:
                raise GateError('conflicting_exact_ID_lookup')
            return matches[0]

        for bv in dict.fromkeys(zero + [v['bvid'] for v in held]):
            env = get('view', dict(bvid=bv))
            data = payload(env)
            if data.get('bvid') != bv or str(data.get('aid')) != str(videos[bv]['aid']):
                raise GateError('metadata_source_identity_changed')
            result['metadata'].append(dict(bvid=bv, reply_count=(data.get('stat') or {}).get('reply'), **ref(env)))
            progress()
        print(json.dumps(dict(stage='metadata_checked', sources=len(result['metadata'])), ensure_ascii=False), flush=True)

        for st in held:
            bv = st['bvid']
            env = get('roots_web', dict(oid=videos[bv]['aid'], type=1, mode=2, next=0, ps=20, plat=1, web_location=1315875))
            d = payload(env)
            c = d.get('cursor')
            if not isinstance(c, dict) or type(c.get('is_end')) is not bool or not isinstance(c.get('all_count'), int):
                raise GateError('diagnostic_root_cursor_schema_changed')
            result['first_roots'].append(dict(bvid=bv, server_total=c['all_count'],
                regular_IDs=[cid(n) for n in d.get('replies') or []],
                newly_seen_preview_IDs=sorted({cid(n) for n in nodes(d)} - set(byid)), **ref(env)))
            progress()

        controls = {}
        for (bv, parent), children in sorted(missing.items()):
            if bv not in controls:
                control = children[0]['id']
                env = get('roots_web', dict(oid=videos[bv]['aid'], type=1, mode=2, next=0, ps=20, plat=1, seek_rpid=control))
                passed = exact(env, control) is not None
                controls[bv] = passed
                result['positive_controls'].append(dict(bvid=bv, target=control, exact_ID_found=passed, **ref(env)))
            env = get('roots_web', dict(oid=videos[bv]['aid'], type=1, mode=2, next=0, ps=20, plat=1, seek_rpid=parent))
            found = exact(env, parent)
            entry = dict(bvid=bv, parent_id=parent, root_id=children[0]['root_id'],
                         exact_ID_found=found is not None, positive_control_passed=controls[bv], **ref(env))
            if found is not None:
                entry['candidate_comment'] = normalize(found, bv, root=children[0]['root_id'])
            result['parent_lookups'].append(entry)
            progress()
        print(json.dumps(dict(stage='parent_IDs_checked', targets=len(result['parent_lookups']),
                              found=sum(x['exact_ID_found'] for x in result['parent_lookups'])), ensure_ascii=False), flush=True)

        affected = sorted({(bv, children[0]['root_id']) for (bv, parent), children in missing.items()})
        targets = {p for bv, p in missing}
        for bv, root in affected:
            thread = dict(bvid=bv, root_id=root, pages=[], normal_end=False, budget_exhausted=False)
            seen, next_value = set(), 1
            for pn in range(1, plan['limits']['max_detail_pages_per_affected_root'] + 1):
                if str(next_value) in seen:
                    raise GateError('diagnostic_detail_cursor_loop')
                seen.add(str(next_value))
                env = get('reply_detail_web', dict(oid=videos[bv]['aid'], type=1, root=root, ps=20, next=next_value))
                d = payload(env)
                cursor = d.get('cursor')
                if not isinstance(cursor, dict) or type(cursor.get('is_end')) is not bool:
                    raise GateError('diagnostic_detail_cursor_schema_changed')
                found = []
                for node in nodes(d):
                    ident = cid(node)
                    if ident in targets:
                        found.append(normalize(node, bv, root=root))
                thread['pages'].append(dict(pn=pn, cursor=cursor, IDs=[cid(n) for n in d.get('replies') or []],
                                           folded_IDs=d.get('FoldRpids'), candidates=found, **ref(env)))
                if cursor['is_end']:
                    thread['normal_end'] = True
                    break
                next_value = cursor.get('next')
                if next_value is None:
                    raise GateError('diagnostic_detail_next_missing')
            else:
                thread['budget_exhausted'] = True
            result['detail_threads'].append(thread)
            progress()

        for bv in plan['small_count_recaptures']:
            status, fresh_rows, fresh_obs = collect_video(s, api, videos[bv])
            capture = dict(status=status, comments=fresh_rows, observations=fresh_obs,
                           namespace=NAMESPACE, selection_hash=digest(selection))
            filename = NAME + '_' + bv + '_recapture.json'
            if not (s.path / filename).exists():
                small.seal(s, filename, capture)
            entry = dict(bvid=bv, status=status['status'], reason=status.get('reason'),
                         unique_IDs=len(fresh_rows), server_total=(status.get('root_paging') or {}).get('all_count'),
                         capture_file=filename, promotable=False)
            try:
                old_status = next(st for st in held if st['bvid'] == bv)
                added = validate_replacement([r for r in rows if r['bvid'] == bv], fresh_rows, old_status, status)
                entry.update(promotable=True, added_IDs=added)
            except GateError as exc:
                entry['promotion_gate'] = str(exc)
            result['recaptures'].append(entry)
            progress()
            if status['status'] != 'enumerated_pending_review' and not (
                status.get('reason') == 'missing_ancestor' or small.source_count_mismatch(status.get('reason', ''))):
                raise GateError('fresh_source_access_paging_or_schema_failure:' + status.get('reason', 'unknown'))
        result['status'] = 'BOUNDED_VERIFICATION_ENDED'
    except GateError as exc:
        result['status'] = 'STOPPED_ON_ACCESS_OR_DIAGNOSTIC_ANOMALY'
        result['reason'] = str(exc)
    result['finished_at'] = now()
    recovered = {x['parent_id'] for x in result['parent_lookups'] if x['exact_ID_found']}
    for t in result['detail_threads']:
        for p in t['pages']:
            recovered.update(c['id'] for c in p['candidates'])
    result['summary'] = dict(status=result['status'], diagnostic_requests=result['requests'],
        zero_sources_checked=sum(m['bvid'] in zero for m in result['metadata']),
        zero_sources_still_zero=sum(m['bvid'] in zero and m['reply_count'] == 0 for m in result['metadata']),
        parent_targets=len(missing), parent_bodies_recovered=len(recovered), recovered_IDs=sorted(recovered),
        detail_threads_checked=len(result['detail_threads']),
        promotable_recaptures=sum(r['promotable'] for r in result['recaptures']),
        master_collection_unchanged=read_json(s.path / 'small_collection.json') == collection,
        formal_comment_sample_generated=False)
    small.seal(s, final_name, result)
    progress()
    print(json.dumps(result['summary'], ensure_ascii=False), flush=True)
    if result.get('reason'):
        print(json.dumps(dict(reason=result['reason']), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
