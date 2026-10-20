import unittest
from copy import deepcopy
from observer.core import GateError
from diagnose_comment_repair import find_reply
from finalize_targeted_repair import validate_replacement


def row(i, **updates):
    return dict(rpid_str=i, root='1', parent='1', ctime=1,
                content=dict(message='fixture'), author_id='U_fixture', **updates)


class ExactLookupTests(unittest.TestCase):
    def test_adjacent_reply_cannot_fill_missing_parent(self):
        self.assertIsNone(find_reply(dict(root=row('1', replies=[row('3')])), '2'))

    def test_exact_nested_ID_is_recovered_without_number_conversion(self):
        target=row('9007199254740993')
        self.assertEqual(find_reply(dict(replies=[row('1', replies=[target])]), target['rpid_str']), target)

    def test_conflicting_versions_of_same_ID_are_rejected(self):
        one=row('2');two=row('2');two['content']['message']='different'
        with self.assertRaises(GateError):find_reply(dict(replies=[one,two]), '2')


class CapturePromotionTests(unittest.TestCase):
    def setUp(self):
        base=dict(bvid='BV0000000001',ctime=1,text='fixture',author_id='U_fixture')
        self.rows=[dict(base,id='1',root_id='1',parent_id='0',level='root',reply_count=1),
                   dict(base,id='2',root_id='1',parent_id='1',level='reply',reply_count=0)]
        self.status=dict(bvid='BV0000000001',status='enumerated_pending_review',unique_count=2,
            threads={'1':dict(normal_end=True,unique_count=1,reported_count=1,pages=[dict(ids=['2']),dict(ids=[])])},
            root_paging=dict(normal_end=True,all_count=2))
        self.old=dict(bvid='BV0000000001',status='incomplete')

    def test_verified_append_preserves_old_body_and_accepts_refreshed_count(self):
        previous=deepcopy(self.rows[:1]);previous[0]['reply_count']=0
        self.assertEqual(validate_replacement(previous,self.rows,self.old,self.status),['2'])

    def test_missing_parent_is_not_fixed_by_success_status(self):
        changed=deepcopy(self.rows);changed[1]['parent_id']='6'
        with self.assertRaisesRegex(GateError,'ancestor'):
            validate_replacement([],changed,self.old,self.status)

    def test_cannot_delete_old_ID_to_reconcile_count(self):
        with self.assertRaisesRegex(GateError,'drops_or_duplicates'):
            validate_replacement(self.rows,self.rows[:1],self.old,self.status)

    def test_thread_count_difference_remains_a_hard_gate(self):
        changed=deepcopy(self.rows);changed[0]['reply_count']=16
        with self.assertRaisesRegex(GateError,'thread_count'):
            validate_replacement([],changed,self.old,self.status)

    def test_cannot_replace_original_body_with_inferred_context(self):
        changed=deepcopy(self.rows);changed[1]['text']='inferred body'
        with self.assertRaisesRegex(GateError,'identity_or_body'):
            validate_replacement(self.rows,changed,self.old,self.status)
