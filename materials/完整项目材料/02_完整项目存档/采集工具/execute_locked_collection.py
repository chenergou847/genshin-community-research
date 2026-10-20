"""Resume the locked source collection; retain strict context/statistical gates."""
import argparse
import json
from collections import Counter

from observer import small
from observer.core import Study, GateError, digest, now, read_json, read_jsonl, write_json
from observer.web_api import NormalWebAPI


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', required=True)
    parser.add_argument('--resume-checkpoint', help='Immutable prefix snapshot; known failures stay failed.')
    parser.add_argument('--continue-source-count-failures', action='store_true',
                        help='Keep source count failures incomplete and continue other locked videos.')
    args = parser.parse_args()
    s = Study(args.study)
    small.check(s)
    if (s.path / 'small_comment_frame.json').exists() or (s.path / 'small_comment_draw.json').exists():
        raise GateError('评论框或样本已冻结，不能用本次续采入口覆盖')
    selection = s.frozen('small_video_selection.json')
    decision = s.frozen('small_context_rule_decision_001.json')
    if decision['rule'] != 'strict_missing_ancestor_blocks_statistical_frame':
        raise GateError('Runner requires the confirmed strict context rule')
    if args.resume_checkpoint:
        small.load_collection_resume(s, selection, args.resume_checkpoint)
    if args.continue_source_count_failures:
        if (not args.resume_checkpoint or s.frozen(args.resume_checkpoint).get('execution_policy', {}).get(
                'continue_independent_sources_after_count_mismatch') is not True):
            raise GateError('source_count_continuation_policy_not_registered')
    state = read_json(s.path / '执行状态.json')
    state.update(at=now(), status='COLLECTING',
                 stage='COMMENT_ENUMERATION_CONTINUES_STATISTICS_HELD_FOR_MISSING_PARENTS',
                 selection_hash=digest(selection), strict_missing_parent_required=True)
    if args.continue_source_count_failures:
        state['stage'] = 'COLLECTING_REMAINING_SOURCES_STATISTICS_HELD_FOR_INTEGRITY'
        state['continue_source_count_failures'] = True
    if args.resume_checkpoint:
        state['resume_checkpoint'] = args.resume_checkpoint
        state['latest_user_instruction'] = '继续任务'
    write_json(s.path / '执行状态.json', state)
    reason = None
    try:
        captures = load_capture_overrides(s, selection)
        small.collect_selected(s, NormalWebAPI(s, source_captures=captures),
                               resume_checkpoint=args.resume_checkpoint,
                               continue_source_count_failures=args.continue_source_count_failures)
    except GateError as exc:
        reason = str(exc)
    except (OSError, ValueError) as exc:
        reason = 'local_or_data_error_' + type(exc).__name__

    return summarize(s, selection, reason, state)


def load_capture_overrides(s, selection):
    name = 'small_active_capture_overrides.json'
    if not (s.path / name).exists():
        return {}
    plan = s.frozen(name)
    if plan['selection_hash'] != digest(selection):
        raise GateError('capture_override_selection_changed')
    selected = {v['bvid'] for v in selection['videos']}
    captures = {}
    for item in plan['captures']:
        if item['bvid'] not in selected or item['bvid'] in captures:
            raise GateError('capture_override_invalid_source')
        proof = s.frozen(item['capture_file'])
        if (digest(proof) != item['capture_hash'] or proof['selection_hash'] != digest(selection)
            or proof['status']['bvid'] != item['bvid']
            or proof['status']['status'] != 'enumerated_pending_review'
            or proof['capture_namespace'] != item['namespace']):
            raise GateError('capture_override_proof_invalid')
        captures[item['bvid']] = item['namespace']
    return captures


def summarize(s, selection, reason, state=None):
    """Report the saved collection, including a targeted source repair."""
    if state is None:
        state = read_json(s.path / '执行状态.json')

    collection = read_json(s.path / 'small_collection.json')
    rows = read_jsonl(s.path / 'small_comments.jsonl')
    observations = read_jsonl(s.path / 'small_observations.jsonl')
    if collection['selection_hash'] != digest(selection):
        raise GateError('collection_selection_hash_changed')
    if collection['comments_hash'] != digest(rows) or collection['observations_hash'] != digest(observations):
        raise GateError('collection_files_hash_mismatch')
    ids = {r['id']: r for r in rows}
    missing = [dict(id=r['id'], bvid=r['bvid'], root_id=r['root_id'], parent_id=r['parent_id'])
               for r in rows if r['parent_id'] != '0' and r['parent_id'] not in ids]
    statuses = Counter(v['status'] for v in collection['videos'])
    failures = [dict(bvid=v['bvid'], reason=v.get('reason', 'unknown'))
                for v in collection['videos'] if v['status'] != 'enumerated_pending_review']
    all_attempted = len(collection['videos']) == len(selection['videos'])
    held = bool(missing) or bool(failures) or reason is not None
    result_status = ('STATISTICS_HELD_MISSING_ANCESTORS' if all_attempted and failures
                     and all(v['reason'] == 'missing_ancestor' for v in failures)
                     else 'ENUMERATION_RUN_ENDED_WITH_INTEGRITY_HOLDS' if all_attempted and failures
                     else 'STOPPED_WITH_PARTIAL_COLLECTION' if held
                     else 'ENUMERATED_PENDING_INDEPENDENT_COUNT_REVIEW')
    summary = dict(videos_attempted=len(collection['videos']), videos_selected=len(selection['videos']),
                   all_sources_attempted=all_attempted, statuses=dict(statuses),
                   raw_unique_IDs_saved=len(rows), roots=sum(r['level']=='root' for r in rows),
                   replies=sum(r['level']=='reply' for r in rows),
                   missing_parent_rows=len(missing), sources_with_missing_parents=len({r['bvid'] for r in missing}),
                   failures=failures, reason=reason, formal_random_comments_drawn=0)
    write_json(s.path / 'small_collection_execution_latest.json',
               dict(at=now(), status=result_status, selection_hash=digest(selection),
                    summary=summary, missing_parent_relations=missing,
                    note='Raw saved IDs are not a frozen window frame or a formal random comment sample.'))
    state.update(at=now(), status=result_status, stage=result_status, collection_progress=summary,
                 strict_missing_parent_required=True, formal_random_raw_comments_drawn=0)
    write_json(s.path / '执行状态.json', state)
    lines = ['# 评论采集最新执行状态', '', '更新时间：' + now(), '',
             '执行状态：' + result_status, '',
             f'已处理{summary["videos_attempted"]}/{summary["videos_selected"]}条锁定来源，'
             f'保存{summary["raw_unique_IDs_saved"]}个实际评论ID：'
             f'{summary["roots"]}条根评论、{summary["replies"]}条回复。', '',
             f'缺失父节点的回复{summary["missing_parent_rows"]}条，涉及'
             f'{summary["sources_with_missing_parents"]}条来源。', '',
             '以上是采集原始清单数量，不是正式抽样评论数。代码本、统计清单和评论随机样本尚未冻结。', '',
             '用户选择保持原门槛。存在缺失父评论或其他未通过来源时，不冻结统计、不剔除来源、'
             '不删除子回复、不替换或重抽。已取得资料、缓存与首次失败快照继续保留。', '',
             '具体状态、缺失关系及采集哈希见研究目录small_collection_execution_latest.json和small_collection.json。', '']
    if failures:
        lines += ['| 来源 | 尚未通过的原因 |', '| --- | --- |']
        lines += [f'| [{v["bvid"]}](https://www.bilibili.com/video/{v["bvid"]}/) | {v["reason"]} |' for v in failures]
    (s.path.parent.parent / '31_评论采集最新状态_20261018.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=result_status, summary=summary), ensure_ascii=False))
    return 2 if held else 0


if __name__ == '__main__':
    raise SystemExit(main())
