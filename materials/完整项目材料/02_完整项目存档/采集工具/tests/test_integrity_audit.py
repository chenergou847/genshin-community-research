import unittest

from audit_collection_integrity import audit_source
from observer.core import digest


class IndependentAuditTests(unittest.TestCase):
    def fixture(self, parents=('100',)):
        stamp = 1791000000
        bv = 'BV1234567890'
        root = dict(rpid_str='100', root_str='0', parent_str='0', ctime=stamp,
                    content={'message': 'root'}, author_id='U_a', rcount=len(parents))
        children = [dict(rpid_str=str(200 + i * 100), root_str='100', parent_str=p,
                         ctime=stamp, content={'message': 'child'}, author_id='U_b', rcount=0)
                    for i, p in enumerate(parents)]
        cursor = dict(is_begin=True, is_end=True, prev=0, next=0, pagination_reply={}, all_count=1 + len(parents))
        responses = [dict(code=0, data=dict(cursor=cursor, replies=[root])),
                     dict(code=0, data=dict(page={'num': 1, 'size': 20, 'count': len(parents)}, replies=children)),
                     dict(code=0, data=dict(page={'num': 2, 'size': 20, 'count': len(parents)}, replies=[]))]
        envelopes = {}
        refs = []
        for i, response in enumerate(responses):
            h = digest(response)
            cap = f'2026-10-18T00:00:0{i}+00:00'
            params = {'oid': '1'} if not i else {'oid': '1', 'root': '100'}
            env = dict(response=response, response_hash=h, captured_at=cap, params=params,
                       route='roots_web' if not i else 'replies_web', _path=f'memory/{i}.json')
            envelopes[h, cap] = [env]
            refs.append(dict(pn=1 if i < 2 else 2, ids=['100'] if not i else [x['rpid_str'] for x in children] if i == 1 else [],
                             response_hash=h, captured_at=cap, cursor=cursor if not i else None))
        rows, observations = [], []
        from observer.collect import normalize
        for raw, root_id, ref in [(root, None, refs[0])] + [(ch, '100', refs[1]) for ch in children]:
            rows.append(normalize(raw, bv, root=root_id))
            observations.append(dict(id=raw['rpid_str'], root_id=root_id, pinned=False, pn=1,
                                     rank=1 if not root_id else children.index(raw) + 1,
                                     captured_at=ref['captured_at'], response_hash=ref['response_hash']))
        state = dict(status='enumerated_pending_review', unique_count=len(rows), root_count=1, reply_count=len(parents),
                     root_paging=dict(normal_end=True, unique_count=1, pages=[refs[0]]),
                     threads={'100': dict(normal_end=True, unique_count=len(parents), reported_count=len(parents), pages=refs[1:])})
        video = dict(bvid=bv, aid='1', mode='abyss')
        config = dict(periods={'abyss': {'start': '2026-10-01T00:00:00+08:00'}}, t0='2026-10-17T23:09:00+08:00')
        return [video, state, rows, observations, envelopes, [], config]

    def test_valid_capture_is_independently_verified(self):
        result = audit_source(*self.fixture())
        self.assertEqual(result['errors'], [])

    def test_success_label_does_not_override_count_discrepancy(self):
        args = self.fixture()
        args[1]['threads']['100']['reported_count'] = 9
        self.assertIn('thread_declared_count_disagrees', audit_source(*args)['errors'])

    def test_direct_missing_parents_and_affected_descendants_are_distinct(self):
        result = audit_source(*self.fixture(('999', '200')))
        self.assertEqual(len(result['missing_relations']), 1)
        self.assertEqual(len(result['ancestor_affected_descendant_IDs']), 2)
        self.assertEqual(result['missing_parent_IDs'], ['999'])

    def test_changed_cached_body_is_not_accepted(self):
        args = self.fixture()
        env = next(iter(args[4].values()))[0]
        env['response']['data']['replies'][0]['content']['message'] = 'changed'
        errors = audit_source(*args)['errors']
        self.assertIn('cache_response_hash_invalid', errors)
        self.assertIn('saved_body_or_identity_disagrees_with_cache', errors)

    def test_another_sources_page_cannot_supply_provenance(self):
        args = self.fixture()
        next(iter(args[4].values()))[0]['params']['oid'] = '2'
        self.assertIn('page_cache_missing_or_wrong_source', audit_source(*args)['errors'])

    def test_missing_empty_reply_terminal_is_rejected(self):
        args = self.fixture()
        args[1]['threads']['100']['pages'].pop()
        self.assertIn('reply_empty_terminal_invalid', audit_source(*args)['errors'])

    def test_cyclic_parent_chain_is_rejected(self):
        result = audit_source(*self.fixture(('300', '200')))
        self.assertIn('cyclic_ancestor', result['errors'])

    def test_observation_rank_cannot_be_silently_changed(self):
        args = self.fixture()
        args[3][-1]['rank'] = 99
        self.assertIn('observation_provenance_disagrees', audit_source(*args)['errors'])

    def zero_fixture(self):
        args = self.fixture()
        cursor = dict(is_begin=True, is_end=True, prev=0, next=0, pagination_reply={})
        response = dict(code=0, data=dict(cursor=cursor, replies=[]))
        h, cap = digest(response), '2026-10-18T00:00:00+00:00'
        page = dict(pn=1, ids=[], response_hash=h, captured_at=cap, cursor=cursor)
        args[1] = dict(status='enumerated_pending_review', unique_count=0, root_count=0, reply_count=0,
                       root_paging=dict(normal_end=True, unique_count=0, pages=[page]), threads={})
        args[2], args[3] = [], []
        args[4] = {(h, cap): [dict(route='roots_web', params={'oid': '1'}, response=response,
                                   response_hash=h, captured_at=cap, _path='memory/zero.json')]}
        return args

    def test_empty_cursor_without_independent_count_is_held(self):
        self.assertIn('zero_count_needs_independent_metadata', audit_source(*self.zero_fixture())['errors'])

    def test_empty_cursor_and_explicit_metadata_zero_agree(self):
        args = self.zero_fixture()
        args[5] = [dict(reply_count=0, path='memory/view.json', captured_at='2026-10-18T00:00:00+00:00')]
        self.assertEqual(audit_source(*args)['errors'], [])


if __name__ == '__main__':
    unittest.main()
