"""Promote a verified recapture of the same locked source, retaining every old ID."""
from observer.core import Study, GateError, digest, read_json, read_jsonl, write_json, write_jsonl
from observer.collect import collect_video
from observer.web_api import NormalWebAPI
from observer import small
from execute_locked_collection import summarize


def validate_replacement(old_rows, new_rows, old_status, new_status):
    if old_status['bvid'] != new_status['bvid'] or new_status['status'] != 'enumerated_pending_review':
        raise GateError('replacement_not_same_complete_source')
    before = {r['id']: r for r in old_rows}
    after = {r['id']: r for r in new_rows}
    if len(after) != len(new_rows) or not set(before) <= set(after):
        raise GateError('replacement_drops_or_duplicates_saved_IDs')
    for i, old in before.items():
        if any(old[k] != after[i][k] for k in ('bvid', 'root_id', 'parent_id', 'ctime', 'text', 'author_id')):
            raise GateError('replacement_changes_saved_comment_identity_or_body')
    bv = old_status['bvid']
    if any(r['bvid'] != bv for r in new_rows):
        raise GateError('replacement_cross_source_row')
    if new_status['unique_count'] != len(after):
        raise GateError('replacement_total_mismatch')
    for row in new_rows:
        parent, seen = row['parent_id'], {row['id']}
        while parent != '0':
            if parent not in after or parent in seen:
                raise GateError('replacement_missing_or_cyclic_ancestor')
            seen.add(parent)
            parent = after[parent]['parent_id']
    roots = {i: r for i, r in after.items() if r['level'] == 'root'}
    if set(roots) != set(new_status['threads']):
        raise GateError('replacement_thread_inventory_mismatch')
    for i, root in roots.items():
        thread = new_status['threads'][i]
        children = {j for j, r in after.items() if r['level'] == 'reply' and r['root_id'] == i}
        if (not thread.get('normal_end') or len(children) != root['reply_count']
            or len(children) != thread['unique_count'] or len(children) != thread['reported_count']):
            raise GateError('replacement_thread_count_mismatch')
        if children != {j for p in thread['pages'] for j in p['ids']}:
            raise GateError('replacement_thread_page_ID_mismatch')
    paging = new_status['root_paging']
    if not paging.get('normal_end') or paging.get('all_count') != len(after):
        raise GateError('replacement_server_total_mismatch')
    return sorted(set(after) - set(before))


def main():
    s = Study('正式采集_小样本v1_20261018')
    small.check(s)
    if (s.path / 'small_comment_frame.json').exists() or (s.path / 'small_comment_draw.json').exists():
        raise GateError('cannot_change_frozen_comment_frame')
    if (s.path / 'small_repair_004_promotion.json').exists():
        s.frozen('small_repair_004_promotion.json')
        print('Already promoted; no duplicate write or request.')
        return
    selection = s.frozen('small_video_selection.json')
    capture = s.frozen('small_repair_004_recapture.json')
    if capture['selection_hash'] != digest(selection):
        raise GateError('recapture_selection_changed')
    bv = 'BV1AQJU6hE93'
    video = next(v for v in selection['videos'] if v['bvid'] == bv)
    collection = read_json(s.path / 'small_collection.json')
    old_rows = read_jsonl(s.path / 'small_comments.jsonl')
    old_obs = read_jsonl(s.path / 'small_observations.jsonl')
    archive = s.frozen('small_collection_attempt_003_failed.json')
    if (digest(collection) != digest(archive['collection']) or digest(old_rows) != collection['comments_hash']
        or digest(old_obs) != collection['observations_hash']):
        raise GateError('original_collection_changed_since_archive')
    # Replay every cached root and reply page through the unchanged strict
    # collector. A successful flag alone never promotes an incomplete source.
    api = NormalWebAPI(s, capture_namespace=capture['capture_namespace'])
    status, rows, observations = collect_video(s, api, video)
    if digest(rows) != digest(capture['comments']) or digest(observations) != digest(capture['observations']):
        raise GateError('recapture_replay_disagrees_with_saved_evidence')
    prior = next(v for v in collection['videos'] if v['bvid'] == bv)
    added = validate_replacement([r for r in old_rows if r['bvid'] == bv], rows, prior, status)
    small.seal(s, 'small_active_capture_overrides.json', dict(selection_hash=digest(selection), captures=[dict(
        bvid=bv, namespace=capture['capture_namespace'], capture_file='small_repair_004_recapture.json',
        capture_hash=digest(capture))], purpose='Same selected video, fresh capture; strict collection gates replayed.'))
    values = sorted([r for r in old_rows if r['bvid'] != bv] + rows, key=lambda r: r['id'])
    # Retain original observations as well as the new capture provenance.
    combined_obs = old_obs + observations
    collection['videos'] = [status if v['bvid'] == bv else v for v in collection['videos']]
    collection['comments_hash'] = digest(values)
    collection['observations_hash'] = digest(combined_obs)
    write_jsonl(s.path / 'small_comments.jsonl', values)
    write_jsonl(s.path / 'small_observations.jsonl', combined_obs)
    write_json(s.path / 'small_collection.json', collection)
    small.seal(s, 'small_repair_004_promotion.json', dict(
        selection_hash=digest(selection), before_collection_hash=digest(archive['collection']),
        after_collection_hash=digest(collection), bvid=bv, added_IDs=added,
        old_IDs_dropped=0, new_status=status,
        remaining_gate='The six missing parents in the other source still block statistical freezing.'))
    summarize(s, selection, 'Targeted count repair complete; missing ancestors still unresolved; remaining sources not resumed.')
    print(dict(repaired_source=bv, unique_count=status['unique_count'], added_IDs=len(added),
               formal_comment_sample_generated=False), flush=True)


if __name__ == '__main__':
    main()
