"""Independent offline audit of saved pages; never changes collection acceptance."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import hashlib
import json

from observer.core import Study, digest, read_json, read_jsonl, ts, write_csv
from observer import small


def nodes(value):
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            if item.get('rpid_str') or item.get('rpid'):
                yield item
            stack.extend(x for x in item.values() if isinstance(x, (dict, list)))


def cid(node):
    value = node.get('rpid_str') or node.get('rpid')
    if isinstance(value, (float, bool)) or not str(value).isdigit():
        raise ValueError('unsafe_comment_ID')
    if node.get('rpid_str') and node.get('rpid') and str(node['rpid_str']) != str(node['rpid']):
        raise ValueError('inconsistent_comment_ID')
    return str(value)


def audit_source(video, state, rows, observations, envelopes, metadata, config):
    errors, evidence, expected_obs, preview_ids = [], [], [], set()
    bv, aid = video['bvid'], str(video['aid'])
    byid = {r['id']: r for r in rows}
    roots = {r['id']: r for r in rows if r['level'] == 'root'}
    replies = {r['id']: r for r in rows if r['level'] == 'reply'}

    def require(ok, code):
        if not ok and code not in errors:
            errors.append(code)

    require(len(rows) == len(byid), 'duplicate_saved_ID')
    require((len(rows), len(roots), len(replies)) ==
            (state['unique_count'], state['root_count'], state['reply_count']), 'saved_counts_disagree')

    def page_env(page, route, root=None):
        matches = [e for e in envelopes.get((page['response_hash'], page['captured_at']), [])
                   if e['route'] == route and str(e['params'].get('oid')) == aid
                   and (root is None or str(e['params'].get('root')) == root)]
        require(bool(matches), 'page_cache_missing_or_wrong_source')
        if not matches:
            return None
        env = matches[0]
        require(digest(env['response']) == env['response_hash'], 'cache_response_hash_invalid')
        require(env['response'].get('code') == 0, 'page_not_success')
        evidence.append(dict(path=env['_path'], response_hash=env['response_hash'],
                             captured_at=env['captured_at']))
        return env

    def body(raw, root, pinned, env, pn, rank):
        ident = cid(raw)
        require(ident in byid, 'page_ID_missing_from_saved_rows')
        expected_obs.append((ident, root, pinned, pn, rank, env['captured_at'], env['response_hash']))
        if ident not in byid:
            return
        row = byid[ident]
        raw_root, raw_parent = str(raw.get('root_str') or raw.get('root', 0)), str(raw.get('parent_str') or raw.get('parent', 0))
        expected = (bv, root or ident, raw_parent, raw.get('ctime'),
                    (raw.get('content') or {}).get('message'), raw.get('author_id'))
        actual = tuple(row[k] for k in ('bvid', 'root_id', 'parent_id', 'ctime', 'text', 'author_id'))
        require(actual == expected, 'saved_body_or_identity_disagrees_with_cache')
        require(raw_root == (root or '0'), 'raw_root_relation_invalid')
        require(row['level'] == ('reply' if root else 'root'), 'saved_level_invalid')
        if not root:
            require(row['reply_count'] == raw.get('rcount'), 'saved_root_declared_count_changed')
        for child in nodes(raw.get('replies') or []):
            preview_ids.add(cid(child))

    paging = state.get('root_paging') or {}
    pages = paging.get('pages') or []
    require(paging.get('normal_end') is True and bool(pages), 'root_terminal_missing')
    root_ids, previous, totals = [], None, set()
    for pn, page in enumerate(pages, 1):
        require(page['pn'] == pn, 'root_page_number_gap')
        env = page_env(page, 'roots_web')
        if env is None:
            continue
        data, params = env['response']['data'], env['params']
        cursor = data.get('cursor') or {}
        require(cursor == page.get('cursor'), 'root_cursor_disagrees_with_cache')
        regular = data.get('replies') or []
        current_ids = [cid(x) for x in regular]
        require(current_ids == page['ids'], 'root_page_IDs_disagree')
        require(len(current_ids) == len(set(current_ids)), 'duplicate_root_within_page')
        require(not set(current_ids) & set(root_ids), 'root_pages_overlap')
        root_ids.extend(current_ids)
        require(cursor.get('is_end') is (pn == len(pages)), 'root_end_flag_invalid')
        if previous is not None:
            offset = (previous.get('pagination_reply') or {}).get('next_offset')
            require(str(params.get('next')) == str(previous.get('next')), 'root_next_cursor_not_followed')
            supplied = json.loads(params.get('pagination_str', '{}')).get('offset')
            require(supplied == offset, 'root_offset_not_followed')
        if 'all_count' in cursor:
            totals.add(cursor['all_count'])
        elif not (pn == 1 and len(pages) == 1 and not regular and cursor.get('is_begin') is True
                  and cursor.get('is_end') is True and cursor.get('prev') == cursor.get('next') == 0
                  and cursor.get('pagination_reply') == {}):
            require(False, 'empty_cursor_contract_not_met')
        for rank, raw in enumerate(regular, 1):
            body(raw, None, False, env, pn, rank)
        pinned = list((data.get('top') or {}).values()) + (data.get('top_replies') or [])
        for rank, raw in enumerate(pinned, 1):
            if isinstance(raw, dict) and (raw.get('rpid_str') or raw.get('rpid')):
                body(raw, None, True, env, pn, rank)
        previous = cursor
    require(set(root_ids) <= set(roots), 'root_inventory_invalid')
    require(len(set(root_ids)) == paging.get('unique_count'), 'root_regular_count_disagrees')
    require(len(totals) <= 1, 'server_total_changed_during_capture')
    if totals:
        require(totals == {len(rows)}, 'global_server_total_disagrees')
    else:
        require(not rows, 'nonempty_source_without_server_total')
        zeros = [m for m in metadata if m['reply_count'] == 0]
        require(bool(zeros), 'zero_count_needs_independent_metadata')
        evidence.extend(zeros)

    require(set(roots) == set(state.get('threads', {})), 'thread_inventory_incomplete')
    for root_id, root in roots.items():
        thread = state.get('threads', {}).get(root_id)
        if thread is None:
            continue
        children = {i for i, r in replies.items() if r['root_id'] == root_id}
        require(thread.get('normal_end') is True, 'reply_terminal_missing')
        require(root['reply_count'] == thread.get('reported_count') == thread.get('unique_count') == len(children),
                'thread_declared_count_disagrees')
        reply_pages = thread.get('pages') or []
        if not reply_pages:
            require(not children and root['reply_count'] == 0
                    and thread.get('status') == 'zero_declared_by_root_response', 'zero_thread_without_evidence')
        got, reported = [], set()
        for pn, page in enumerate(reply_pages, 1):
            require(page['pn'] == pn, 'reply_page_number_gap')
            env = page_env(page, 'replies_web', root_id)
            if env is None:
                continue
            data = env['response']['data']
            declaration = data.get('page') or {}
            require(declaration.get('num') == pn and declaration.get('size') == 20, 'reply_number_or_size_invalid')
            reported.add(declaration.get('count'))
            regular = data.get('replies') or []
            page_ids = [cid(x) for x in regular]
            require(page_ids == page['ids'], 'reply_page_IDs_disagree')
            require(not set(got) & set(page_ids) and len(page_ids) == len(set(page_ids)), 'reply_pages_overlap')
            got.extend(page_ids)
            require(bool(regular) is (pn != len(reply_pages)), 'reply_empty_terminal_invalid')
            for rank, raw in enumerate(regular, 1):
                body(raw, root_id, False, env, pn, rank)
        require(not reply_pages or reported == {len(children)}, 'reply_page_count_disagrees')
        require(set(got) == children, 'reply_inventory_disagrees')

    observed = Counter((o['id'], o['root_id'], o['pinned'], o['pn'], o['rank'], o['captured_at'], o['response_hash'])
                       for o in observations)
    require(observed == Counter(expected_obs), 'observation_provenance_disagrees')
    missing = [dict(child=r['id'], root=r['root_id'], parent=r['parent_id']) for r in rows
               if r['parent_id'] != '0' and r['parent_id'] not in byid]
    affected_descendants = []
    for row in rows:
        require(isinstance(row['id'], str) and row['id'].isdigit(), 'saved_ID_type_invalid')
        require(isinstance(row['ctime'], int) and row['ctime'] > 0, 'comment_time_invalid')
        require(hashlib.sha256(row['text'].encode()).hexdigest() == row['text_hash'], 'comment_text_hash_invalid')
        require(datetime.fromisoformat(row['ctime_bjt']).timestamp() == row['ctime'], 'comment_local_time_disagrees')
        parent, seen = row['parent_id'], {row['id']}
        while parent != '0':
            if parent not in byid:
                affected_descendants.append(row['id'])
                require(False, 'missing_ancestor')
                break
            if parent in seen:
                require(False, 'cyclic_ancestor')
                break
            require(byid[parent]['root_id'] == row['root_id'], 'cross_thread_ancestor')
            seen.add(parent)
            parent = byid[parent]['parent_id']
    require(not preview_ids - set(byid), 'cached_preview_IDs_not_in_inventory')
    window = {}
    for mode in video.get('domains', [video['mode']]):
        window[mode] = sum(ts(config['periods'][mode]['start']) <= r['ctime'] <= ts(config['t0']) for r in rows)
    return dict(bvid=bv, original_status=state['status'], original_reason=state.get('reason'),
                audit_status='verified' if not errors else 'held', errors=errors,
                roots=len(roots), replies=len(replies), unique_IDs=len(rows), server_total=next(iter(totals), None),
                zero_metadata_evidence=metadata if not rows else [], missing_relations=missing,
                missing_parent_IDs=sorted({x['parent'] for x in missing}), window_counts_unfrozen=window,
                ancestor_affected_descendant_IDs=sorted(affected_descendants),
                root_pages=len(pages), reply_pages=sum(len(t.get('pages') or []) for t in state.get('threads', {}).values()),
                cache_evidence=evidence)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--study', default='正式采集_小样本v1_20261018')
    ap.add_argument('--output', default='small_integrity_audit_010.json')
    args = ap.parse_args()
    s = Study(args.study)
    if (s.path / args.output).exists():
        old = s.frozen(args.output)
        print(json.dumps(old['summary'], ensure_ascii=False))
        return
    selection = s.frozen('small_video_selection.json')
    collection = read_json(s.path / 'small_collection.json')
    rows, obs = read_jsonl(s.path / 'small_comments.jsonl'), read_jsonl(s.path / 'small_observations.jsonl')
    assert collection['selection_hash'] == digest(selection)
    assert collection['config_hash'] == s.config_hash
    assert collection['comments_hash'] == digest(rows) and collection['observations_hash'] == digest(obs)
    assert len({r['id'] for r in rows}) == len(rows)
    assert [v['bvid'] for v in selection['videos']] == [v['bvid'] for v in collection['videos']]
    envelopes, metadata = defaultdict(list), defaultdict(list)
    cache_files, bad_hashes = 0, []
    for folder in (s.path / 'cache', s.path / 'cache_captures'):
        for p in folder.rglob('*.json'):
            env = read_json(p)
            cache_files += 1
            if digest(env['response']) != env['response_hash']:
                bad_hashes.append(str(p.relative_to(s.path)))
                continue
            env['_path'] = str(p.relative_to(s.path))
            envelopes[(env['response_hash'], env['captured_at'])].append(env)
            data = env['response'].get('data') or {}
            if env.get('route') in ('view', 'view_web') and data.get('bvid'):
                metadata[data['bvid']].append(dict(path=env['_path'], captured_at=env['captured_at'],
                                                 response_hash=env['response_hash'], reply_count=(data.get('stat') or {}).get('reply')))
    by_source, obs_by_source = defaultdict(list), defaultdict(list)
    for r in rows:
        by_source[r['bvid']].append(r)
    for o in obs:
        obs_by_source[o['bvid']].append(o)
    results = [audit_source(v, st, by_source[v['bvid']], obs_by_source[v['bvid']], envelopes,
                            metadata[v['bvid']], s.config) for v, st in zip(selection['videos'], collection['videos'])]
    summary = dict(sources=len(results), verified=sum(r['audit_status'] == 'verified' for r in results),
                   held=sum(r['audit_status'] != 'verified' for r in results), raw_unique_IDs=len(rows),
                   roots=sum(r['level'] == 'root' for r in rows), replies=sum(r['level'] == 'reply' for r in rows),
                   zero_sources=sum(r['unique_IDs'] == 0 for r in results),
                   missing_child_relations=sum(len(r['missing_relations']) for r in results),
                   missing_unique_parent_IDs=len({i for r in results for i in r['missing_parent_IDs']}),
                   ancestor_affected_descendants=sum(len(r['ancestor_affected_descendant_IDs']) for r in results),
                   cache_files_checked=cache_files, corrupt_cache_files=bad_hashes,
                   formal_comment_sample_generated=False)
    report = dict(selection_hash=digest(selection), collection_hash=digest(collection), comments_hash=digest(rows),
                  observations_hash=digest(obs), summary=summary, sources=results,
                  method='independent offline reconstruction from saved GET responses; no collector replay, no credential reads',
                  supersedes='small_integrity_audit_009.json: distinguish 27 direct missing-parent relations from 53 transitively affected descendants',
                  limitation='Metadata and comment pages have different capture times. Counts describe accessible captures, not T0 visibility or deletion history.')
    small.seal(s, args.output, report)
    write_csv(s.path / args.output.replace('.json', '.csv'), [dict(
        bvid=r['bvid'], audit_status=r['audit_status'], errors=';'.join(r['errors']),
        unique_IDs=r['unique_IDs'], roots=r['roots'], replies=r['replies'], server_total=r['server_total'],
        missing_parent_IDs=';'.join(r['missing_parent_IDs']), window_counts_unfrozen=json.dumps(r['window_counts_unfrozen']))
        for r in results], ['bvid', 'audit_status', 'errors', 'unique_IDs', 'roots', 'replies', 'server_total', 'missing_parent_IDs', 'window_counts_unfrozen'])
    print(json.dumps(summary, ensure_ascii=False))
    print(json.dumps([dict(bvid=r['bvid'], errors=r['errors']) for r in results if r['errors']], ensure_ascii=False))


if __name__ == '__main__':
    main()
