"""Synthetic fixtures only; these are never real study data."""
from unittest.mock import patch
from observer.core import Study,GateError,MODES,VIDEO_FIELDS,digest,read_csv,read_json,read_jsonl,write_csv,write_json,write_jsonl
from observer.collect import AccessError,normalize
from observer import small
from test_observer import Base,FakeAPI,comment,envelope,T


class Search:
    def __init__(self,fail=None,zero=False,bad_date=False):self.calls=[];self.fail=fail;self.zero=zero;self.bad_date=bad_date
    def get(self,route,p):
        self.calls.append(p)
        if self.fail and len(self.calls)==self.fail:raise AccessError('access_challenge_voucher_present')
        pn=p['page'];rows=[] if self.zero else [dict(bvid='BV'+str(1000+pn*20+i).zfill(10),aid=123,pubdate=0 if self.bad_date else T-1,title='synthetic') for i in range(20)]
        d=dict(page=pn,pagesize=20,numPages=0 if self.zero else 50,numResults=0 if self.zero else 1000)
        if not self.zero:d['result']=rows
        return envelope(d)


class SmallTests(Base):
    def setUp(self):
        super().setUp();c=self.s.config
        c.update(protocol=small.PROTOCOL,targets=dict(videos=20,comments_per_video=10,coding_review=30),
                 bounded_search=dict(main=3,audit_a=1,audit_b=1,page_size=20),video_publish_start='2019-01-01T00:00:00+00:00')
        write_json(self.s.path/'config.json',c);self.s=Study(self.s.path)
        self.s.immutable('registration.json',dict(config_hash=self.s.config_hash,purpose='SYNTHETIC_ONLY'))

    def test_changed_scope_rejected_against_preregistration(self):
        c=self.s.config;c['video_publish_start']='2019-02-01T00:00:00+00:00'
        write_json(self.s.path/'config.json',c)
        with self.assertRaises(GateError):small.check(Study(self.s.path))

    def test_missing_ancestor_preserved_while_other_sources_collected_but_frame_blocked(self):
        self.candidates();self.reviewed();selection=small.lock_videos(self.s)
        first=selection['videos'][0]['bvid']
        def result(study,api,video):
            bad=video['bvid']==first
            return dict(bvid=video['bvid'],status='incomplete' if bad else 'enumerated_pending_review',
                        reason='missing_ancestor' if bad else '',root_count=0,reply_count=0,unique_count=0),[],[]
        with patch('observer.small.collect_video',side_effect=result) as collect:
            with self.assertRaisesRegex(GateError,'缺失父评论'):
                small.collect_selected(self.s,object())
        self.assertEqual(collect.call_count,len(selection['videos']))
        saved=read_json(self.s.path/'small_collection.json')
        self.assertEqual(len(saved['videos']),len(selection['videos']))
        self.assertEqual(saved['videos'][0]['reason'],'missing_ancestor')
        with self.assertRaises(GateError):small.freeze_comments(self.s)
        self.assertFalse((self.s.path/'small_comment_frame.json').exists())

    def test_access_failure_still_stops_before_independent_sources(self):
        self.candidates();self.reviewed();selection=small.lock_videos(self.s)
        failure=dict(bvid=selection['videos'][0]['bvid'],status='incomplete',reason='http_412')
        with patch('observer.small.collect_video',return_value=(failure,[],[])) as collect:
            with self.assertRaises(GateError):small.collect_selected(self.s,object())
        self.assertEqual(collect.call_count,1)

    def test_capture_override_reenumerates_same_locked_video_without_skipping_gates(self):
        self.candidates();self.reviewed();selection=small.lock_videos(self.s)
        original, replacement = object(), object()
        first=selection['videos'][0]['bvid']
        class PerSource:
            def for_video(self,video):
                return replacement if video['bvid']==first else original
        def result(study,api,video):
            self.assertIs(api,replacement if video['bvid']==first else original)
            return dict(bvid=video['bvid'],status='incomplete',reason='missing_ancestor'),[],[]
        with patch('observer.small.collect_video',side_effect=result) as collect:
            with self.assertRaisesRegex(GateError,'缺失父评论'):
                small.collect_selected(self.s,PerSource())
        self.assertEqual([call.args[2]['bvid'] for call in collect.call_args_list],
                         [v['bvid'] for v in selection['videos']])
        self.assertFalse((self.s.path/'small_comment_frame.json').exists())

    def test_unresolved_capture_cannot_be_registered_for_replay(self):
        from execute_locked_collection import load_capture_overrides
        self.candidates();self.reviewed();selection=small.lock_videos(self.s)
        bv=selection['videos'][0]['bvid']
        proof=small.seal(self.s,'capture_fixture.json',dict(selection_hash=digest(selection),
            status=dict(bvid=bv,status='incomplete',reason='missing_ancestor'),capture_namespace='fixture'))
        small.seal(self.s,'small_active_capture_overrides.json',dict(selection_hash=digest(selection),
            captures=[dict(bvid=bv,namespace='fixture',capture_file='capture_fixture.json',capture_hash=digest(proof))]))
        with self.assertRaisesRegex(GateError,'proof_invalid'):
            load_capture_overrides(self.s,selection)

    def resume_inputs(self, reason='missing_ancestor'):
        self.candidates(n=2);self.reviewed();selection=small.lock_videos(self.s)
        first=selection['videos'][0]['bvid']
        rows=[normalize(comment('1',count=1),first),
              normalize(comment('2',root='1',parent='999'),first,root='1')]
        observations=[dict(id=r['id'],bvid=first) for r in rows]
        states=[dict(bvid=first,status='incomplete',reason=reason,unique_count=2,root_count=1,reply_count=1),
                dict(bvid=selection['videos'][1]['bvid'],status='enumerated_pending_review',unique_count=0,root_count=0,reply_count=0)]
        collection=dict(config_hash=self.s.config_hash,selection_hash=digest(selection),videos=states,
                        comments_hash=digest(rows),observations_hash=digest(observations))
        write_json(self.s.path/'small_collection.json',collection)
        write_jsonl(self.s.path/'small_comments.jsonl',rows)
        write_jsonl(self.s.path/'small_observations.jsonl',observations)
        saved=small.seal(self.s,'resume_fixture.json',dict(collection=collection,comments=rows,observations=observations,
                         known_holds=[dict(bvid=first,state_hash=digest(states[0]))]))
        return selection,saved

    def empty_enumeration(self,study,api,video):
        return dict(bvid=video['bvid'],status='enumerated_pending_review',unique_count=0,root_count=0,reply_count=0),[],[]

    def test_resume_retains_failed_source_and_orphan_but_collects_original_suffix(self):
        selection,saved=self.resume_inputs()
        with patch('observer.small.collect_video',side_effect=self.empty_enumeration) as collect:
            with self.assertRaisesRegex(GateError,'不能冻结统计清单'):
                small.collect_selected(self.s,object(),resume_checkpoint='resume_fixture.json')
        self.assertEqual([x.args[2]['bvid'] for x in collect.call_args_list],
                         [v['bvid'] for v in selection['videos'][2:]])
        result=read_json(self.s.path/'small_collection.json')
        self.assertEqual(result['videos'][:2],saved['collection']['videos'])
        self.assertEqual(read_jsonl(self.s.path/'small_comments.jsonl'),saved['comments'])
        self.assertEqual(result['selection_hash'],digest(selection))
        with self.assertRaises(GateError):small.freeze_comments(self.s)

    def test_resume_rejects_changed_live_rows_before_requesting_sources(self):
        self.resume_inputs();write_jsonl(self.s.path/'small_comments.jsonl',[])
        with patch('observer.small.collect_video') as collect:
            with self.assertRaisesRegex(GateError,'resume_live_files_changed'):
                small.collect_selected(self.s,object(),resume_checkpoint='resume_fixture.json')
        collect.assert_not_called()

    def test_resume_cannot_jump_over_unattempted_video(self):
        selection,saved=self.resume_inputs()
        saved['collection']['videos'].reverse()
        write_json(self.s.path/'small_collection.json',saved['collection'])
        small.seal(self.s,'bad_prefix_fixture.json',dict(collection=saved['collection'],comments=saved['comments'],
                   observations=saved['observations'],known_holds=saved['known_holds']))
        with self.assertRaisesRegex(GateError,'original_locked_prefix'):
            small.load_collection_resume(self.s,selection,'bad_prefix_fixture.json')

    def test_resume_cannot_skip_an_access_failure_even_if_listed_as_known(self):
        selection,saved=self.resume_inputs('http_412')
        with self.assertRaisesRegex(GateError,'cannot_skip_access'):
            small.load_collection_resume(self.s,selection,'resume_fixture.json')

    def test_new_count_failure_still_stops_resumed_suffix_immediately(self):
        selection,saved=self.resume_inputs()
        status=dict(bvid=selection['videos'][2]['bvid'],status='incomplete',reason='root_plus_reply_count_mismatch:1!=2',
                    root_count=0,reply_count=0,unique_count=0)
        with patch('observer.small.collect_video',return_value=(status,[],[])) as collect:
            with self.assertRaises(GateError):small.collect_selected(self.s,object(),resume_checkpoint='resume_fixture.json')
        self.assertEqual(collect.call_count,1)
        self.assertEqual(read_json(self.s.path/'small_collection.json')['videos'][:2],saved['collection']['videos'])

    def test_new_access_failure_still_stops_resumed_suffix_immediately(self):
        selection,saved=self.resume_inputs()
        status=dict(bvid=selection['videos'][2]['bvid'],status='incomplete',reason='api_code_-412',
                    root_count=0,reply_count=0,unique_count=0)
        with patch('observer.small.collect_video',return_value=(status,[],[])) as collect:
            with self.assertRaises(GateError):small.collect_selected(self.s,object(),resume_checkpoint='resume_fixture.json')
        self.assertEqual(collect.call_count,1)

    def test_explicit_count_policy_preserves_failure_and_collects_all_other_sources(self):
        selection,saved=self.resume_inputs()
        bad=selection['videos'][2]['bvid']
        def result(study,api,video):
            state,rows,obs=self.empty_enumeration(study,api,video)
            if video['bvid']==bad:
                state.update(status='incomplete',reason='root_plus_reply_count_mismatch:0!=1')
            return state,rows,obs
        with patch('observer.small.collect_video',side_effect=result) as collect:
            with self.assertRaisesRegex(GateError,'不能冻结统计清单'):
                small.collect_selected(self.s,object(),resume_checkpoint='resume_fixture.json',continue_source_count_failures=True)
        self.assertEqual(collect.call_count,len(selection['videos'])-2)
        actual=read_json(self.s.path/'small_collection.json')
        self.assertEqual([v['bvid'] for v in actual['videos']],[v['bvid'] for v in selection['videos']])
        self.assertEqual(actual['videos'][:2],saved['collection']['videos'])
        self.assertEqual(actual['videos'][2]['status'],'incomplete')
        self.assertEqual(actual['videos'][2]['reason'],'root_plus_reply_count_mismatch:0!=1')
        self.assertEqual(read_jsonl(self.s.path/'small_comments.jsonl'),saved['comments'])
        with self.assertRaises(GateError):small.freeze_comments(self.s)

    def test_explicit_count_policy_does_not_ignore_later_access_failure(self):
        selection,saved=self.resume_inputs()
        count_state=dict(bvid=selection['videos'][2]['bvid'],status='incomplete',reason='root_rcount_vs_reply_count_mismatch',
                         root_count=0,reply_count=0,unique_count=0)
        denied=dict(bvid=selection['videos'][3]['bvid'],status='incomplete',reason='api_code_-412',
                    root_count=0,reply_count=0,unique_count=0)
        with patch('observer.small.collect_video',side_effect=[(count_state,[],[]),(denied,[],[])]) as collect:
            with self.assertRaises(GateError):
                small.collect_selected(self.s,object(),resume_checkpoint='resume_fixture.json',continue_source_count_failures=True)
        self.assertEqual(collect.call_count,2)

    def test_explicit_count_policy_still_stops_on_paging_failure(self):
        selection,saved=self.resume_inputs()
        failure=dict(bvid=selection['videos'][2]['bvid'],status='incomplete',reason='terminal_count_mismatch:0!=1',
                     root_count=0,reply_count=0,unique_count=0)
        with patch('observer.small.collect_video',return_value=(failure,[],[])) as collect:
            with self.assertRaises(GateError):
                small.collect_selected(self.s,object(),resume_checkpoint='resume_fixture.json',continue_source_count_failures=True)
        self.assertEqual(collect.call_count,1)

    def test_source_count_policy_does_not_match_unknown_or_access_errors(self):
        self.assertTrue(small.source_count_mismatch('root_plus_reply_count_mismatch:154!=155'))
        self.assertFalse(small.source_count_mismatch('root_plus_reply_count_mismatch:api_code_-412'))
        self.assertFalse(small.source_count_mismatch('count_changed_during_capture'))
        self.assertFalse(small.source_count_mismatch('cursor_schema_changed'))

    def candidates(self,n=1):
        records=[]
        for mi,m in enumerate(MODES):
            for i in range(n):
                r=dict.fromkeys(VIDEO_FIELDS,'');r.update(bvid='BV'+str(1000*(mi+1)+i).zfill(10),mode=m,aid=str(123+mi*n+i),
                  primary_up=str(456+mi*n+i),published_at=str(T-1),title='fixture',decision='pending',tags='<none>',content_type='record')
                records.append(r)
        small.seal(self.s,'small_candidate_frame.json',dict(records=records))
        write_csv(self.s.path/'small_video_review.csv',[dict(r,final='no') for r in records],small.VFIELDS)
        small.draw_videos(self.s)
        return records

    def reviewed(self):
        rows=read_csv(self.s.path/'small_video_review.csv')
        for r in rows:r.update(decision='include',final='yes',reviewer='human_fixture',review_kind='human_final',reason='fixture',period_evidence='fixture content frame')
        write_csv(self.s.path/'small_video_review.csv',rows,small.VFIELDS)
        return rows

    def codebook(self):
        write_json(self.s.path/'codebook.json',dict(version='fixture',relevance_rules='fixture',context_rules='fixture',examples='fixture',reviewer='human_fixture',
          themes=[dict(id=t,definition='fixture',include='fixture',exclude='fixture') for t in ['problem','other_current_experience']],
          exploration_review=dict(status='limited',reviewer='human_fixture',evidence='synthetic only')))
        small.freeze_codebook(self.s)

    def prepared_frame(self,n=2,N=11):
        self.candidates(n);self.reviewed();selection=small.lock_videos(self.s)
        frames={m:{} for m in MODES};comments=[]
        for mi,(m,domain) in enumerate(selection['domains'].items()):
            for vi,v in enumerate(domain['selected']):
                ids=[str(9007199254740993+mi*100000+vi*100+i) for i in range(N)]
                frames[m][v['bvid']]=ids
                for i in ids:comments.append(dict(id=i,bvid=v['bvid'],root_id=i,parent_id='0',level='root',text='synthetic',ctime=T,author_role='audience'))
        small.seal(self.s,'small_comment_frame.json',dict(comments=comments,frames=frames))
        return selection

    def pipeline(self):
        self.candidates();self.reviewed();selection=small.lock_videos(self.s)
        class PerVideo:
            def actor(self,mid):return 'UP_'+str(mid)
            def get(self,route,p):
                aid=int(p['oid']);roots=[comment(str(aid*100+1)),comment(str(aid*100+2))]
                return FakeAPI(roots=roots).get(route,p)
        small.collect_selected(self.s,PerVideo())
        rows=read_csv(self.s.path/'small_collection_review.csv')
        for r in rows:r.update(status='accepted',final='yes',count_semantics_evidence='fixture',reconciliation='fixture',pagination_evidence='fixture',reviewer='human_fixture')
        write_csv(self.s.path/'small_collection_review.csv',rows,small.RFIELDS)
        small.freeze_comments(self.s);self.codebook();small.draw_comments(self.s)
        codes=read_csv(self.s.path/'small_coding.csv')
        for i,r in enumerate(codes):r.update(relevance='related',themes='problem' if i%2 else '',final='yes',reason='fixture',evidence='fixture',reviewer='human_fixture',review_kind='human_final',context_status='checked')
        write_csv(self.s.path/'small_coding.csv',codes,small.CFIELDS)
        return codes

    def audit(self):
        small.lock_coding(self.s);codes=small.codes(self.s)
        p=self.s.path/'small_blind_review_001.csv';rows=read_csv(p)
        for r in rows:
            code=codes[(r['mode'],r['id'])]
            r.update(relevance=code['relevance'],themes=code['themes'],self_experience_themes=code['self_experience_themes'],
                     reviewer='human_fixture',review_kind='same_person_blind_recode',final='yes',date_checked='yes',role_checked='yes',context_status='checked',resolution='agreed fixture')
        write_csv(p,rows,small.AFIELDS)

    def test_bounded_search_stops_at_registered_depth_despite_1000_cap(self):
        api=Search();result=small.discover(self.s,api,'main')
        self.assertEqual(len(api.calls),54*3)
        self.assertTrue(all(x['status']=='bounded_complete' and not x['full_search_enumerated'] for x in result['queries']))
        self.assertTrue(all(p['pubtime_begin_s']>0 and p['page_size']==20 and p['page']<=3 for p in api.calls))

    def test_audit_is_sealed_after_main_without_classifying_all_candidates(self):
        for group in small.GROUPS:small.discover(self.s,Search(),group)
        f=small.freeze_candidates(self.s)
        self.assertEqual(len(f['records']),180)
        self.assertEqual(f['coverage_sufficiency'],'not_proven')

    def test_challenge_stops_without_sealing_partial_discovery(self):
        api=Search(fail=2)
        with self.assertRaises(GateError):small.discover(self.s,api,'main')
        self.assertEqual(len(api.calls),2)
        self.assertFalse((self.s.path/'small_discovery_main.json').exists())

    def test_status_counts_completed_queries_without_calling_group_sealed(self):
        with self.assertRaises(GateError):small.discover(self.s,Search(fail=4),'main')
        state=small.status(self.s)
        self.assertEqual(state['bounded_queries_completed']['main'],1)
        self.assertFalse(state['discovery_groups_sealed']['main'])

    def test_true_zero_without_result_is_not_a_missing_page(self):
        api=Search(zero=True);small.discover(self.s,api,'main')
        self.assertEqual(len(api.calls),54)

    def test_date_filter_outside_window_fails(self):
        with self.assertRaises(GateError):small.discover(self.s,Search(bad_date=True),'main')

    def test_pending_random_prefix_cannot_be_skipped(self):
        self.candidates(2);rows=self.reviewed()
        first=self.s.frozen('small_video_draw.json')['orders']['abyss'][0]
        for r in rows:
            if r['mode']=='abyss' and r['bvid']==first:r['final']='no'
        write_csv(self.s.path/'small_video_review.csv',rows,small.VFIELDS)
        self.assertEqual(small.video_progress(self.s)['abyss']['selected'],[])
        with self.assertRaises(GateError):small.lock_videos(self.s)

    def test_ai_video_decision_does_not_pass_as_human(self):
        self.candidates();rows=self.reviewed();rows[0]['review_kind']='AI_only'
        write_csv(self.s.path/'small_video_review.csv',rows,small.VFIELDS)
        with self.assertRaises(GateError):small.lock_videos(self.s)

    def test_fewer_than_20_eligible_is_video_census(self):
        self.candidates(2);self.reviewed();r=small.lock_videos(self.s)
        self.assertTrue(all(v['census'] and len(v['selected'])==2 for v in r['domains'].values()))

    def test_20_eligible_stops_without_reviewing_remaining_candidate(self):
        self.candidates(21);rows=self.reviewed();d=self.s.frozen('small_video_draw.json')
        for r in rows:
            if r['bvid']==d['orders'][r['mode']][-1]:r['final']='no'
        write_csv(self.s.path/'small_video_review.csv',rows,small.VFIELDS)
        r=small.lock_videos(self.s)
        self.assertTrue(all(len(v['selected'])==20 and not v['census'] for v in r['domains'].values()))

    def test_video_seed_cannot_be_rerolled(self):
        self.candidates();old=self.s.frozen('small_video_draw.json')
        with self.assertRaises(GateError):small.draw_videos(self.s)
        self.assertEqual(old,self.s.frozen('small_video_draw.json'))

    def test_end_to_end_census_with_blind_audit(self):
        self.pipeline();self.audit();out=small.estimates(self.s)
        self.assertEqual(out['status'],'AUDITED_FINITE_FRAME_ESTIMATES')
        for m in MODES:
            self.assertEqual(out['domains'][m]['raw_sample_n'],2)
            x=out['domains'][m]['metrics']['themes']['problem']
            self.assertAlmostEqual(x['proportion'],.5)
            self.assertEqual(x['reason'],'finite_frame_census_no_sampling_error')

    def test_missing_blind_audit_cannot_publish(self):
        self.pipeline();small.lock_coding(self.s)
        with self.assertRaises(GateError):small.estimates(self.s)
        self.assertEqual(small.estimates(self.s,True)['status'],'DRAFT')

    def test_unrelated_random_item_is_kept_not_replaced(self):
        codes=self.pipeline();codes[0].update(relevance='irrelevant',themes='')
        write_csv(self.s.path/'small_coding.csv',codes,small.CFIELDS)
        out=small.estimates(self.s,True)
        self.assertEqual(out['domains'][codes[0]['mode']]['raw_sample_n'],2)
        self.assertEqual(out['domains'][codes[0]['mode']]['related_sample_n'],1)

    def test_changed_locked_labels_require_reasoned_revision(self):
        rows=self.pipeline();self.audit();rows[0]['themes']='problem' if not rows[0]['themes'] else ''
        write_csv(self.s.path/'small_coding.csv',rows,small.CFIELDS)
        with self.assertRaises(GateError):small.estimates(self.s)
        small.lock_coding(self.s,'fixture correction')
        self.assertTrue((self.s.path/'small_coding_locked_001.json').exists())
        self.assertTrue((self.s.path/'small_blind_review_002.csv').exists())

    def test_qual_source_cannot_be_reused_for_validation(self):
        self.prepared_frame();bv=next(iter(self.s.frozen('small_comment_frame.json')['frames']['abyss']))
        small.qual_queue(self.s,'abyss',bv,'development')
        with self.assertRaisesRegex(GateError,'重复UP'):small.qual_queue(self.s,'abyss',bv,'validation')

    def test_600_raw_domain_rows_limit_and_seed_replay(self):
        self.prepared_frame(21);self.codebook();draw=small.draw_comments(self.s)
        self.assertEqual(sum(v['m'] for vs in draw['samples'].values() for v in vs.values()),600)
        self.assertTrue(all(v['N']==11 and v['relative_weight']==1.1 for vs in draw['samples'].values() for v in vs.values()))
        small.load_comments(self.s)
        with self.assertRaises(GateError):small.draw_comments(self.s)
        self.assertEqual(small.status(self.s)['random_raw_sample_rows'],{m:200 for m in MODES})

    def test_qual_selection_cannot_be_silently_removed(self):
        self.prepared_frame();bv=next(iter(self.s.frozen('small_comment_frame.json')['frames']['abyss']))
        small.qual_queue(self.s,'abyss',bv,'development')
        write_json(self.s.path/'small_qual_registry.json',dict(items=[]))
        with self.assertRaises(GateError):small.qual_status(self.s)

    def test_enrich_reads_only_next_prefix_and_rotates_three_modes(self):
        self.candidates(3)
        class View:
            def __init__(self):self.calls=[]
            def get(self,route,p):
                self.calls.append(p['bvid'])
                return envelope(dict(aid=123,owner=dict(mid=456),pubdate=T-1,title='fixture',desc='fixture'))
        api=View();small.enrich_next(self.s,api,6)
        self.assertEqual(len(api.calls),6)
        orders=self.s.frozen('small_video_draw.json')['orders']
        self.assertEqual(api.calls[:3],[orders[m][0] for m in MODES])

    def test_disagreement_resolved_as_original_is_not_counted_as_correction(self):
        self.prepared_frame(21);self.codebook();small.draw_comments(self.s)
        rows=read_csv(self.s.path/'small_coding.csv')
        for i,r in enumerate(rows):r.update(relevance='related',themes='problem' if i%2 else '',final='yes',reason='fixture',evidence='fixture',reviewer='human_fixture',review_kind='human_final',context_status='checked')
        write_csv(self.s.path/'small_coding.csv',rows,small.CFIELDS);self.audit()
        rows=read_csv(self.s.path/'small_blind_review_001.csv');original=small.codes(self.s)
        used={m:0 for m in MODES}
        for r in rows:
            if used[r['mode']]<2:
                o=original[(r['mode'],r['id'])]
                r.update(themes='' if o['themes'] else 'problem',resolved_relevance=o['relevance'],resolved_themes=o['themes'],resolved_self_experience_themes=o['self_experience_themes'])
                used[r['mode']]+=1
        write_csv(self.s.path/'small_blind_review_001.csv',rows,small.AFIELDS)
        mapping,audit=small.adjudicated(self.s)
        for x in audit['domains'].values():
            self.assertEqual(x['n'],30);self.assertEqual(x['disagreements'],2);self.assertEqual(x['corrections'],0);self.assertTrue(x['pass'])

    def test_legacy_command_rejects_small_study(self):
        from observer.cli import main
        with patch('builtins.print'):
            self.assertEqual(main(['--study',str(self.s.path),'draw']),2)
        self.assertFalse((self.s.path/'draw.json').exists())

    def test_pending_context_cannot_be_marked_final(self):
        rows=self.pipeline();rows[0]['context_status']='pending'
        write_csv(self.s.path/'small_coding.csv',rows,small.CFIELDS)
        with self.assertRaises(GateError):small.lock_coding(self.s)

    def test_old_coding_pointer_cannot_hide_a_new_revision(self):
        self.pipeline();self.audit();old=read_json(self.s.path/'small_coding_current.json')
        small.lock_coding(self.s,'new fixture review')
        write_json(self.s.path/'small_coding_current.json',old)
        with self.assertRaises(GateError):small.adjudicated(self.s)


class RatioTests(Base):
    def test_big_and_small_comment_areas_are_not_equal_weight(self):
        r=small.ratio_estimate([dict(N=100,values=[dict(y=1,r=1)]*10),dict(N=10,values=[dict(y=0,r=1)]*10)])
        self.assertAlmostEqual(r['proportion'],100/110)
        self.assertNotEqual(r['proportion'],.5)

    def test_cluster_heterogeneity_prevents_false_precision(self):
        r=small.ratio_estimate([dict(N=100,values=[dict(y=i%2,r=1)]*10) for i in range(20)])
        self.assertAlmostEqual(r['proportion'],.5)
        self.assertFalse(r['precision_target_met'])
        self.assertEqual(r['df'],19)

    def test_zero_observed_theme_not_zero_uncertainty(self):
        r=small.ratio_estimate([dict(N=100,values=[dict(y=0,r=1)]*10) for i in range(20)])
        self.assertEqual(r['interval95'],[0.,1.])
        self.assertFalse(r['precision_target_met'])

    def test_all_video_census_keeps_within_video_sampling_error(self):
        r=small.ratio_estimate([dict(N=100,values=[dict(y=i%2,r=1) for i in range(10)])],True)
        self.assertGreater(r['sampling_variance'],0)
        self.assertAlmostEqual(r['sampling_variance'],.025)

    def test_zero_comment_video_retained_as_cluster(self):
        r=small.ratio_estimate([dict(N=0,values=[]),dict(N=100,values=[dict(y=i%2,r=1) for i in range(10)])])
        self.assertEqual(r['interval95'],[0.,1.])

    def test_actual_two_stage_census_has_no_sampling_error(self):
        r=small.ratio_estimate([dict(N=2,values=[dict(y=1,r=1),dict(y=0,r=1)])],True)
        self.assertTrue(r['precision_target_met'])
        self.assertIsNone(r['interval95'])
