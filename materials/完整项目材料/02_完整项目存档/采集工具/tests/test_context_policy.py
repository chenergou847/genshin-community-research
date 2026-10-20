"""Missing context is not missing enumeration; synthetic records only."""
from unittest.mock import patch

from observer import small
from observer.context_policy import RULE, RULE_FILE, ancestry_annotations, source_eligible
from observer.core import GateError, digest, read_csv, read_json, read_jsonl, write_csv, write_json, write_jsonl
from observer.collect import normalize
from test_observer import Base, comment
import test_small as fixtures


class ContextPolicyTests(Base):
    def setUp(self):
        super().setUp()
        c=self.s.config
        c.update(protocol=small.PROTOCOL,targets=dict(videos=20,comments_per_video=10,coding_review=30),
                 bounded_search=dict(main=3,audit_a=1,audit_b=1,page_size=20),video_publish_start='2019-01-01T00:00:00+00:00')
        write_json(self.s.path/'config.json',c)
        from observer.core import Study
        self.s=Study(self.s.path)
        self.s.immutable('registration.json',dict(config_hash=self.s.config_hash,purpose='SYNTHETIC_ONLY'))

    candidates = fixtures.SmallTests.candidates
    reviewed = fixtures.SmallTests.reviewed
    prepared_frame = fixtures.SmallTests.prepared_frame
    codebook = fixtures.SmallTests.codebook
    pipeline = fixtures.SmallTests.pipeline

    def revised_capture(self, count_error=False):
        self.candidates(); self.reviewed(); selection=small.lock_videos(self.s)
        states=[]; rows=[]
        for v in selection['videos']:
            bv=v['bvid']
            ident=str(len(rows)+100)
            root=normalize(comment(ident,count=1),bv)
            child=normalize(comment(str(int(ident)+1),root=ident,parent='999'),bv,root=ident)
            root['author_role']=child['author_role']='audience'
            rows.extend([root,child])
            states.append(dict(bvid=bv,status='incomplete',reason='missing_ancestor',unique_count=2,root_count=1,reply_count=1))
        collection=dict(config_hash=self.s.config_hash,selection_hash=digest(selection),videos=states,
            comments_hash=digest(rows),observations_hash=digest([]))
        write_json(self.s.path/'small_collection.json',collection)
        write_jsonl(self.s.path/'small_comments.jsonl',rows)
        write_jsonl(self.s.path/'small_observations.jsonl',[])
        reviews=[dict(bvid=v['bvid'],status='accepted',final='yes',count_semantics_evidence='synthetic',
            reconciliation='synthetic',pagination_evidence='synthetic',reviewer='synthetic') for v in states]
        write_csv(self.s.path/'small_collection_review.csv',reviews,small.RFIELDS)
        audit=small.seal(self.s,'audit_fixture.json',dict(selection_hash=digest(selection),collection_hash=digest(collection),
            comments_hash=digest(rows),observations_hash=digest([]),summary=dict(corrupt_cache_files=[]),
            sources=[dict(bvid=v['bvid'],errors=['missing_ancestor']+(['global_server_total_disagrees'] if count_error else []),
                ancestor_affected_descendant_IDs=[r['id'] for r in rows if r['bvid']==v['bvid'] and r['level']=='reply']) for v in states]))
        small.seal(self.s,RULE_FILE,dict(policy=RULE,strict_missing_parent_required=False,selection_hash=digest(selection),
            human_reply='synthetic authorization',source='direct_user_reply_in_current_chat',count_paging_provenance_gates_unchanged=True))
        write_json(self.s.path/'small_context_integrity_current.json',dict(file='audit_fixture.json',hash=digest(audit)))
        return selection,collection,rows

    def test_opt_in_retains_every_readable_child_and_raw_archive(self):
        selection,collection,rows=self.revised_capture()
        frame=small.freeze_comments(self.s)
        self.assertEqual(frame['comments'],rows)
        self.assertEqual(len(frame['context_annotations']),3)
        self.assertEqual(sum(len(ids) for vs in frame['frames'].values() for ids in vs.values()),6)
        self.assertEqual(read_json(self.s.path/'small_collection.json'),collection)
        self.assertNotIn('999',{r['id'] for r in frame['comments']})

    def test_parent_exception_does_not_waive_count_findings(self):
        self.revised_capture(count_error=True)
        with self.assertRaisesRegex(GateError,'尚未全部采集完整'):
            small.freeze_comments(self.s)

    def test_context_rule_cannot_waive_pending_independent_review(self):
        self.revised_capture()
        reviews=read_csv(self.s.path/'small_collection_review.csv')
        reviews[0]['final']='no'
        write_csv(self.s.path/'small_collection_review.csv',reviews,small.RFIELDS)
        with self.assertRaisesRegex(GateError,'逐视频核验'):
            small.freeze_comments(self.s)

    def test_changed_collection_cannot_reuse_an_old_context_audit(self):
        self.revised_capture()
        collection=read_json(self.s.path/'small_collection.json');collection['changed']=True
        write_json(self.s.path/'small_collection.json',collection)
        with self.assertRaisesRegex(GateError,'审计与当前'):
            small.freeze_comments(self.s)

    def test_access_error_is_never_context_only(self):
        context=dict(sources={'x':dict(errors=['missing_ancestor'])})
        self.assertFalse(source_eligible(context,dict(bvid='x',status='incomplete',reason='http_412')))

    def test_missing_parent_exception_never_permits_cycles_or_cross_thread_edges(self):
        rows=[dict(id='1',bvid='x',root_id='1',parent_id='2'),dict(id='2',bvid='x',root_id='1',parent_id='1')]
        with self.assertRaisesRegex(GateError,'循环'):
            ancestry_annotations(rows,True)
        rows[1].update(root_id='2',parent_id='0')
        with self.assertRaisesRegex(GateError,'跨楼层'):
            ancestry_annotations(rows,True)
        rows[1]['bvid']='y'
        with self.assertRaisesRegex(GateError,'跨视频'):
            ancestry_annotations(rows,True)

    def test_self_contained_reply_is_flagged_but_not_automatically_unknown(self):
        self.revised_capture(); frame=small.freeze_comments(self.s)
        cb=dict(version='synthetic',relevance_rules='synthetic',context_rules='synthetic',examples='synthetic',reviewer='synthetic',
            uncertainty_rules='synthetic',themes=[dict(id='other_current_experience',definition='synthetic',include='synthetic',exclude='synthetic')],
            exploration_review=dict(status='limited',evidence='synthetic',reviewer='synthetic'))
        write_json(self.s.path/'codebook.json',cb);small.freeze_codebook(self.s);small.draw_comments(self.s)
        rows=read_csv(self.s.path/'small_coding.csv')
        for r in rows:
            r.update(relevance='related',theme_status='known',final='yes',reason='self contained',evidence='own text',
                reviewer='synthetic',review_kind='human_final',context_status='checked_with_limits')
        write_csv(self.s.path/'small_coding.csv',rows,small.CFIELDS)
        self.assertEqual(len(small.codes(self.s)),6)
        child=next(r for r in rows if r['id'] in frame['context_annotations'])
        child['context_status']='checked'
        with self.assertRaisesRegex(GateError,'语境限制'):
            small.codes(self.s,rows)

    def test_known_relevant_theme_unknown_is_not_counted_as_no_problem(self):
        rows=self.pipeline(); target=rows[0];mode=target['mode']
        target.update(relevance='related',theme_status='unknown',themes='',self_experience_themes='')
        other=next(r for r in rows if r['mode']==mode and r['id']!=target['id'])
        other['themes']='problem'
        write_csv(self.s.path/'small_coding.csv',rows,small.CFIELDS)
        result=small.estimates(self.s,True)['domains'][mode]
        metric=result['metrics']['themes']['problem']
        self.assertEqual(metric['proportion'],1.)
        self.assertEqual(metric['unknown_content_bounds'],[.5,1.])
        self.assertEqual(result['theme_unknown_sample_n'],1)
        self.assertEqual(result['weighted_unknown_share'],.5)
        target['themes']='problem'
        with self.assertRaisesRegex(GateError,'主题不明'):
            small.codes(self.s,rows)

    def test_unknown_sample_is_retained_and_bounds_cover_both_extremes(self):
        rows=self.pipeline();target=rows[0];mode=target['mode']
        target.update(relevance='unknown',themes='',theme_status='unknown')
        other=next(r for r in rows if r['mode']==mode and r['id']!=target['id']);other['themes']='problem'
        write_csv(self.s.path/'small_coding.csv',rows,small.CFIELDS)
        result=small.estimates(self.s,True)['domains'][mode]
        self.assertEqual(result['raw_sample_n'],2)
        self.assertEqual(result['metrics']['themes']['problem']['unknown_content_bounds'],[.5,1.])
