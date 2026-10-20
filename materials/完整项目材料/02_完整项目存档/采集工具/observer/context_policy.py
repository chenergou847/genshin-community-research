"""Explicit missing-context amendment; enumeration and provenance stay strict."""
from .core import GateError, digest, read_json


RULE_FILE = 'small_context_rule_decision_002.json'
RULE = 'retain_readable_replies_mark_unknown'


def load_rule(s, selection, collection):
    if not (s.path / RULE_FILE).exists():
        return None
    rule = s.frozen(RULE_FILE)
    if (rule.get('policy') != RULE or rule.get('strict_missing_parent_required') is not False
            or rule.get('selection_hash') != digest(selection)
            or not rule.get('human_reply') or rule.get('source') != 'direct_user_reply_in_current_chat'
            or rule.get('count_paging_provenance_gates_unchanged') is not True):
        raise GateError('缺父语境修订登记无效')
    pointer = read_json(s.path / 'small_context_integrity_current.json')
    name = pointer.get('file', '')
    if not name.endswith('.json') or '/' in name or '\\' in name:
        raise GateError('语境修订审计引用无效')
    audit = s.frozen(name)
    if (pointer.get('hash') != digest(audit)
            or audit.get('collection_hash') != digest(collection)
            or audit.get('selection_hash') != digest(selection)
            or audit.get('comments_hash') != collection['comments_hash']
            or audit.get('observations_hash') != collection['observations_hash']):
        raise GateError('语境修订审计与当前正文、来源或观测不一致')
    sources = {r['bvid']: r for r in audit['sources']}
    if (len(sources) != len(audit['sources'])
            or set(sources) != {v['bvid'] for v in selection['videos']}
            or audit['summary'].get('corrupt_cache_files')):
        raise GateError('语境修订审计来源不全或缓存损坏')
    return dict(rule=rule, audit=audit, audit_file=name, sources=sources)


def source_eligible(context, state):
    """Only a missing-ancestor finding is waivable, never a count/page finding."""
    if context is None:
        return state['status'] == 'enumerated_pending_review'
    findings = context['sources'][state['bvid']]
    if set(findings['errors']) - {'missing_ancestor'}:
        return False
    return (state['status'] == 'enumerated_pending_review'
            or (state['status'] == 'incomplete' and state.get('reason') == 'missing_ancestor'
                and set(findings['errors']) == {'missing_ancestor'}))


def ancestry_annotations(rows, allow_missing=False):
    byid = {r['id']: r for r in rows}
    if len(byid) != len(rows):
        raise GateError('语境核验出现重复ID')
    annotations = {}
    for row in rows:
        ancestor, seen = row['parent_id'], {row['id']}
        while ancestor != '0':
            parent = byid.get(ancestor)
            if parent is None:
                if not allow_missing:
                    raise GateError('缺失祖先正文')
                annotations[row['id']] = dict(status='ancestor_body_unavailable',
                    first_missing_ancestor_id=ancestor, root_id=row['root_id'], bvid=row['bvid'],
                    deletion_confirmed=False, coding_pending=True)
                break
            if parent['bvid'] != row['bvid'] or ancestor in seen:
                raise GateError('跨视频或循环祖先')
            if parent['root_id'] != row['root_id']:
                raise GateError('跨楼层祖先')
            seen.add(ancestor)
            ancestor = parent['parent_id']
    return annotations
