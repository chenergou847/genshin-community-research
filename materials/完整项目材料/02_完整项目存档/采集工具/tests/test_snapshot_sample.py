"""Saved-corpus inference has a narrower target, not fake enumeration success."""
import copy
import hashlib

from observer.core import GateError, MODES, Study, digest, read_csv, read_json, write_csv, write_json, write_jsonl
from observer.context_policy import RULE_FILE
from observer import small
from observer.snapshot_sample import build_frame, draw_from_frame, run, verify_draw
from test_observer import Base
import test_integrity_audit as fixtures


class SnapshotTests(Base):
    def inputs(self):
        args=fixtures.IndependentAuditTests().fixture(('999',))
        video,state,rows,obs,envelopes,metadata,config=args
        for r in rows:r['author_role']='audience'
        for o in obs:o['bvid']=video['bvid']
        result=fixtures.audit_source(*args)
        state['status']='incomplete';state['reason']='missing_ancestor';state['bvid']=video['bvid']
        selection=dict(videos=[video],domains={m:dict(selected=[video] if m=='abyss' else []) for m in MODES})
        collection=dict(selection_hash=digest(selection),comments_hash=digest(rows),observations_hash=digest(obs),videos=[state])
        audit=dict(selection_hash=digest(selection),collection_hash=digest(collection),comments_hash=digest(rows),
            observations_hash=digest(obs),sources=[result],summary=dict(corrupt_cache_files=[]))
        return [config,selection,collection,rows,obs,audit]

    def test_count_or_context_findings_are_retained_without_claiming_complete_capture(self):
        args=self.inputs();args[-1]['sources'][0]['errors'].append('global_server_total_disagrees')
        frame=build_frame(*args)
        self.assertFalse(frame['broader_video_domain_inference_allowed'])
        self.assertEqual(len(frame['comments']),2)
        self.assertFalse(frame['source_dispositions'][0]['complete_accessible_enumeration_claimed'])
        self.assertIn('global_server_total_disagrees',frame['source_dispositions'][0]['original_audit_findings'])
        self.assertEqual(len(frame['context_annotations']),1)

    def test_body_provenance_or_cache_failures_still_block(self):
        for finding in ('saved_body_or_identity_disagrees_with_cache','page_cache_missing_or_wrong_source',
                        'observation_provenance_disagrees','cache_response_hash_invalid'):
            args=self.inputs();args[-1]['sources'][0]['errors'].append(finding)
            with self.assertRaisesRegex(GateError,'provenance_failure'):build_frame(*args)

    def test_changed_saved_body_cannot_reuse_original_audit(self):
        args=self.inputs();args[3][0]['text']='changed'
        with self.assertRaisesRegex(GateError,'hash_mismatch'):build_frame(*args)

    def test_forged_text_with_rebound_outer_hash_still_fails_body_digest(self):
        args=self.inputs();args[3][0]['text']='changed'
        args[2]['comments_hash']=digest(args[3]);args[-1]['comments_hash']=digest(args[3]);args[-1]['collection_hash']=digest(args[2])
        with self.assertRaisesRegex(GateError,'invalid_body'):build_frame(*args)

    def test_unexplained_foreign_source_cannot_enter_saved_frame(self):
        args=self.inputs();args[-1]['sources']=[]
        with self.assertRaisesRegex(GateError,'source_inventory'):build_frame(*args)

    def test_zero_and_small_sources_kept_and_sampling_replays(self):
        frame=build_frame(*self.inputs());frame['frames']['abyss']['zero_source']=[]
        draw=draw_from_frame(frame,'01'*32);verify_draw(frame,draw)
        source=next(v for k,v in draw['samples']['abyss'].items() if k!='zero_source')
        self.assertEqual((source['N'],source['m'],source['relative_weight']),(2,2,1.))
        self.assertEqual(draw['samples']['abyss']['zero_source']['m'],0)
        self.assertFalse(draw['replacements_allowed'])
        altered=copy.deepcopy(draw);source_id=next(k for k in draw['samples']['abyss'] if k!='zero_source')
        altered['samples']['abyss'][source_id]['ids'].pop()
        with self.assertRaisesRegex(GateError,'not_replayable'):verify_draw(frame,altered)

    def test_large_source_samples_exactly_ten_without_replacement(self):
        frame=dict(frames={m:({'v':[str(i) for i in range(101)]} if m=='abyss' else {}) for m in MODES},scope='synthetic')
        draw=draw_from_frame(frame,'02'*32);x=draw['samples']['abyss']['v']
        self.assertEqual(len(set(x['ids'])),10)
        self.assertEqual(x['relative_weight'],10.1)
        self.assertAlmostEqual(x['inclusion_probability'],10/101)
        self.assertEqual(draw,draw_from_frame(frame,'02'*32))

    def test_time_boundaries_are_inclusive_and_raw_context_not_deleted(self):
        args=self.inputs();stamp=args[3][0]['ctime']
        from datetime import datetime,timezone
        args[0]['periods']['abyss']['start']=datetime.fromtimestamp(stamp,timezone.utc).isoformat()
        args[0]['t0']=datetime.fromtimestamp(stamp,timezone.utc).isoformat()
        frame=build_frame(*args)
        self.assertEqual(len(next(iter(frame['frames']['abyss'].values()))),2)
        args[0]['t0']=datetime.fromtimestamp(stamp-1,timezone.utc).isoformat()
        frame=build_frame(*args)
        self.assertEqual(len(next(iter(frame['frames']['abyss'].values()))),0)
        self.assertEqual(len(frame['comments']),2)

    def test_execution_is_idempotent_keeps_master_and_does_not_reset_coding(self):
        config,selection,collection,rows,obs,audit=self.inputs()
        c=self.s.config
        c.update(protocol=small.PROTOCOL,targets=dict(videos=20,comments_per_video=10,coding_review=30),
            bounded_search=dict(main=3,audit_a=1,audit_b=1,page_size=20),video_publish_start='2019-01-01T00:00:00+00:00',
            t0=config['t0'])
        for m in MODES:c['periods'][m]['start']=config['periods']['abyss']['start']
        write_json(self.s.path/'config.json',c);self.s=Study(self.s.path)
        self.s.immutable('registration.json',dict(config_hash=self.s.config_hash,purpose='SYNTHETIC_ONLY'))
        selection['videos'][0]['title']='synthetic'
        selection=small.seal(self.s,'small_video_selection.json',selection)
        collection.update(config_hash=self.s.config_hash,selection_hash=digest(selection))
        audit.update(selection_hash=digest(selection),collection_hash=digest(collection))
        small.seal(self.s,'small_integrity_audit_010.json',audit)
        small.seal(self.s,RULE_FILE,dict(purpose='SYNTHETIC_ONLY'))
        write_json(self.s.path/'small_collection.json',collection)
        write_jsonl(self.s.path/'small_comments.jsonl',rows);write_jsonl(self.s.path/'small_observations.jsonl',obs)
        before=(self.s.path/'small_comments.jsonl').read_bytes()
        first=run(self.s);coding=read_csv(self.s.path/'small_snapshot_coding.csv')
        coding[0]['notes']='human work must survive rerun'
        write_csv(self.s.path/'small_snapshot_coding.csv',coding,small.CFIELDS)
        second=run(self.s)
        self.assertEqual(first,second)
        self.assertEqual(read_csv(self.s.path/'small_snapshot_coding.csv')[0]['notes'],'human work must survive rerun')
        self.assertEqual((self.s.path/'small_comments.jsonl').read_bytes(),before)
        self.assertFalse((self.s.path/'small_comment_draw.json').exists())
        self.assertEqual(first['raw_sample_rows'],2)
