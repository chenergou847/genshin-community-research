"""合成离线夹具；不包含、也不充当本项目的真实评论。"""
import copy
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from observer.core import (GateError, MODES, SCREEN_FIELDS, Study, digest, identifier,
                           permutation, read_csv, read_json, template, ts, wilson,
                           write_csv, write_json, write_jsonl)
from observer.collect import AccessError, HTTP, collect_video, discover, normalize, paged
from observer.research import (checkpoint, current_selection, draw, estimates, export,
                               freeze_codebook, freeze_comments, freeze_videos, load_draw,
                               lock_selection, main_selection, path_template, qual_init,
                               qual_queue, qualitative_status, reserve_qual, reviewed_videos)

BV = "BV1vSJS6DEEs"
T = 1577923200  # 2020-01-02 UTC，仅供合成测试


def comment(i, root="0", parent="0", ctime=T, count=0, text="过了", actor="U_same"):
    return dict(rpid_str=str(i), root=str(root), parent=str(parent), ctime=ctime,
                content=dict(message=text), rcount=count, author_id=actor, like=0)


def envelope(data):
    response = dict(code=0, data=data)
    return dict(response=response, response_hash=digest(response), captured_at="2020-01-03T00:00:00+00:00")


class FakeAPI:
    def __init__(self, roots=None, replies=None, count_override=None, repeat=False, fail=None):
        self.roots = roots or []
        self.replies = replies or {}
        self.override = count_override
        self.repeat = repeat
        self.fail = fail
        self.calls = []

    def actor(self, mid):
        return "UP_" + str(mid)

    def get(self, route, params):
        self.calls.append((route, params))
        if self.fail and self.fail(route, params):
            raise AccessError("http_412")
        values = self.roots if route == "roots" else self.replies.get(params["root"], [])
        pn, ps = params["pn"], params["ps"]
        items = values[:ps] if self.repeat else values[(pn-1)*ps:pn*ps]
        count = self.override if self.override is not None else len(values)
        return envelope(dict(page=dict(num=pn, size=ps, count=count, acount=len(self.roots)+sum(map(len, self.replies.values()))), replies=items))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="observer_test_", dir=Path(__file__).parent)
        self.addCleanup(self.tmp.cleanup)
        self.s = Study.init(Path(self.tmp.name) / "study")
        c = self.s.config
        c.update(t0="2020-01-03T00:00:00+00:00", confirmed_by="synthetic_test", confirmation_record="TEST_ONLY")
        for m in MODES:
            c["periods"][m] = dict(period_id="TEST_ONLY", start="2020-01-02T00:00:00+00:00", characteristics="fixture", evidence="fixture", verified_by="fixture")
        write_json(self.s.path / "config.json", c)
        self.s = Study(self.s.path)

    def video(self):
        return dict(bvid=BV, aid="123", primary_up="456", coauthors="789", published_at=str(T-1),
                    title="合成视频", tags="<none>", content_type="guide", domains=[dict(mode=m, evidence="fixture", reviewer="fixture", content_type="guide") for m in MODES])

    def frames(self, count=10):
        vf = dict(config_hash=self.s.config_hash, coverage_stable=False, videos=[self.video()])
        self.s.immutable("video_frame.json", vf)
        rows = []
        for i in range(1, count+1):
            row = normalize(comment(str(10000000000000000+i)), BV)
            row.update(first_read_at="2020-01-03T00:00:00+00:00", last_read_at="2020-01-03T00:00:00+00:00", author_role="audience")
            rows.append(row)
        cf = dict(config_hash=self.s.config_hash, comments=rows, domains={m:[r["id"] for r in rows] for m in MODES}, context_ids=[], video_frame_hash=digest(vf))
        self.s.immutable("comment_frame.json", cf)
        cb = dict(version="fixture", relevance_rules="fixture", context_rules="fixture", examples="fixture", reviewer="fixture",
                  exploration_review=dict(status="limited", evidence="synthetic", reviewer="fixture"),
                  themes=[dict(id="problem", definition="fixture", include="fixture", exclude="fixture"),
                          dict(id="other_current_experience", definition="fixture", include="fixture", exclude="fixture")])
        write_json(self.s.path / "codebook.json", cb)
        freeze_codebook(self.s)
        return vf, cf

    def fill_screen(self, related=True):
        rows = read_csv(self.s.path / "screening.csv")
        for r in rows:
            r.update(relevance="related" if related else "irrelevant", final="yes", reviewer="fixture", reason="fixture", evidence="fixture", themes="problem" if int(r["id"])%2 else "", self_experience_themes="", experience_kind="self_report", sentiment="neutral", context_status="checked")
        write_csv(self.s.path / "screening.csv", rows, SCREEN_FIELDS)
        return rows


class ConfigTests(Base):
    def test_candidate_import_preserves_dates_but_not_prior_decisions(self):
        prior=self.s.path/'prior.csv'
        fields=['bvid','mode','published_at','aid','title','decision','reviewer','period_evidence']
        write_csv(prior,[dict(bvid=BV,mode='abyss',published_at=str(T-1),aid='123',title='fixture',decision='include',reviewer='old',period_evidence='old')],fields)
        self.s.import_candidates(prior)
        row=read_csv(self.s.path/'video_review.csv')[0]
        self.assertEqual(row['published_at'],str(T-1))
        self.assertEqual(row['aid'],'123')
        self.assertEqual(row['decision'],'pending')
        self.assertEqual(row['reviewer'],'')
        self.assertEqual(row['period_evidence'],'')

    def test_video_before_registered_publication_start_cannot_pass_review_gate(self):
        self.s.config['video_publish_start']='2020-01-02T00:00:00+00:00'
        self.s.candidate(BV,'abyss',self.video())
        rows=read_csv(self.s.path/'video_review.csv')
        rows[0].update(decision='include',reviewer='fixture',reason='fixture',period_evidence='fixture')
        write_csv(self.s.path/'video_review.csv',rows,list(rows[0]))
        with self.assertRaises(GateError):
            reviewed_videos(self.s)

    def test_template_54_plus_36_queries(self):
        counts = {g:sum(q["group"] == g for q in template()["queries"]) for g in ("main","audit_a","audit_b")}
        self.assertEqual(counts, dict(main=54, audit_a=18, audit_b=18))

    def test_unverified_config_refuses(self):
        c = template()
        write_json(self.s.path/"config.json", c)
        with self.assertRaises(GateError):
            Study(self.s.path).validate()

    def test_valid_config_and_changed_frozen_hash(self):
        self.assertTrue(self.s.validate())
        self.s.immutable("dummy.json", dict(config_hash=self.s.config_hash))
        c = self.s.config
        c["revision"] = "2"
        write_json(self.s.path/"config.json", c)
        with self.assertRaises(GateError):
            Study(self.s.path).frozen("dummy.json")

    def test_future_t0_and_naive_time_refused(self):
        for value in ("2999-01-01T00:00:00+08:00", "2020-01-01T00:00:00"):
            self.s.config["t0"] = value
            with self.assertRaises(GateError):
                self.s.validate()

    def test_remove_query_refused(self):
        self.s.config["queries"].pop()
        with self.assertRaises(GateError):
            self.s.validate()

    def test_ids_reject_precision_loss(self):
        self.assertEqual(identifier(9007199254740993), "9007199254740993")
        for value in (None, 0, True, 9007199254740992.0, "1e18"):
            with self.assertRaises(GateError):
                identifier(value)


class HTTPTests(Base):
    def test_capture_namespace_preserves_old_cache_and_is_not_sent_to_server(self):
        class Response:
            def __init__(self, value): self.value=value
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,*args): return json.dumps(dict(code=0,data=dict(value=self.value))).encode()
        old=HTTP(self.s);fresh=HTTP(self.s,capture_namespace='repair_001')
        with patch.object(old.opener,'open',return_value=Response('old')) as one,patch('observer.collect.time.sleep'):
            original=old.get('view',dict(bvid=BV))
        old_file=next((self.s.path/'cache').glob('*.json'));old_bytes=old_file.read_bytes()
        with patch.object(fresh.opener,'open',return_value=Response('fresh')) as two,patch('observer.collect.time.sleep'):
            newer=fresh.get('view',dict(bvid=BV));again=fresh.get('view',dict(bvid=BV))
        self.assertEqual(original['response']['data']['value'],'old')
        self.assertEqual(newer['response']['data']['value'],'fresh')
        self.assertEqual(newer,again)
        self.assertEqual(old_file.read_bytes(),old_bytes)
        self.assertEqual(one.call_args.args[0].full_url,two.call_args.args[0].full_url)
        self.assertEqual(two.call_count,1)
        self.assertEqual(len(list((self.s.path/'cache_captures/repair_001').glob('*.json'))),1)

    def test_capture_namespace_rejects_path_traversal(self):
        with self.assertRaises(GateError):HTTP(self.s,capture_namespace='../old')

    def test_direct_comment_absence_is_preserved_as_nonzero_not_success(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,*args): return b'{"code":12006,"message":"not found","data":null}'
        api=HTTP(self.s)
        with patch.object(api.opener,'open',return_value=Response()),patch('observer.collect.time.sleep'):
            out=api.get('reply_jump_web',dict(oid='123',type=1,rpid='9007199254740993'))
        self.assertEqual(out['response']['code'],12006)
        self.assertTrue(out['response']['source_data_was_null'])

    def test_direct_lookup_still_stops_on_access_code(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,*args): return b'{"code":-412,"data":null}'
        api=HTTP(self.s)
        with patch.object(api.opener,'open',return_value=Response()) as get,patch('observer.collect.time.sleep'):
            with self.assertRaisesRegex(AccessError,'api_code_-412'):
                api.get('reply_jump_web',dict(oid='123',type=1,rpid='1'))
        self.assertEqual(get.call_count,1)
        self.assertFalse((self.s.path/'cache').exists())

    def test_direct_lookup_minimizes_nested_comment_profiles(self):
        api=HTTP(self.s)
        raw=dict(code=0,data=dict(root=dict(rpid_str='1',mid=123,root=0,parent=0,ctime=T,
            content=dict(message='root'),member=dict(uname='PRIVATE_ROOT'),replies=[dict(
                rpid_str='9007199254740993',mid=456,root=1,parent=1,ctime=T,
                content=dict(message='parent'),member=dict(uname='PRIVATE_PARENT'))])))
        clean=api.sanitize('reply_jump_web',raw)
        self.assertEqual(clean['data']['root']['replies'][0]['rpid_str'],'9007199254740993')
        self.assertNotIn('PRIVATE_',json.dumps(clean))

    def test_folding_and_dialog_evidence_keeps_IDs_but_no_viewer_profile(self):
        raw=dict(code=0,data=dict(FoldRpids=[9007199254740993],Mid=12345,
            dialog=dict(min_floor=0,max_floor=55),control=dict(viewer='PRIVATE',show_fold=True),
            root=dict(rpid_str='1',mid=123,content=dict(message='root'),
                      folder=dict(has_folded=False,is_folded=False,viewer='PRIVATE'))))
        api=HTTP(self.s)
        for route in ('reply_detail_web','reply_dialog_web'):
            clean=api.sanitize(route,raw)
            self.assertEqual(clean['data']['FoldRpids'],['9007199254740993'])
            self.assertNotIn('PRIVATE',json.dumps(clean))
            self.assertNotIn('Mid',clean['data'])
        with self.assertRaises(GateError):
            api.sanitize('reply_detail_web',dict(code=0,data=dict(FoldRpids=[dict(mid=123)])))

    def test_zero_api_code_with_voucher_is_challenge_not_success(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,*args): return b'{"code":0,"data":{"v_voucher":"SYNTHETIC_TEST_ONLY"}}'
        api=HTTP(self.s)
        with patch.object(api.opener,"open",return_value=Response()) as get,patch("observer.collect.time.sleep"):
            with self.assertRaisesRegex(AccessError,"access_challenge_voucher_present"):
                api.get("search",dict(keyword="fixture"))
        self.assertEqual(get.call_count,1)
        self.assertFalse((self.s.path/"cache").exists())

    def test_previously_cached_voucher_is_rejected(self):
        params=dict(keyword="fixture")
        body=dict(code=0,data=dict(v_voucher="SYNTHETIC_TEST_ONLY"))
        write_json(self.s.path/"cache"/(digest(dict(route="search",params=params))+".json"),dict(response=body,response_hash=digest(body)))
        with self.assertRaisesRegex(AccessError,"access_challenge_voucher_present"):
            HTTP(self.s).get("search",params)

    def test_http412_stops_once_without_caching(self):
        api=HTTP(self.s)
        error=urllib.error.HTTPError("https://api.bilibili.com/",412,"blocked",None,None)
        with patch.object(api.opener,"open",side_effect=error) as get, patch("observer.collect.time.sleep"):
            with self.assertRaises(AccessError):
                api.get("view",{"bvid":BV})
        self.assertEqual(get.call_count,1)
        self.assertFalse((self.s.path/"cache").exists())

    def test_non_json_challenge_not_zero_and_no_retry(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,*args): return b"<html>captcha</html>"
        api=HTTP(self.s)
        with patch.object(api.opener,"open",return_value=Response()) as get, patch("observer.collect.time.sleep"):
            with self.assertRaisesRegex(AccessError,"non_json_or_challenge"):
                api.get("view",{"bvid":BV})
        self.assertEqual(get.call_count,1)

    def test_success_cached_minimized_and_large_ids_preserved(self):
        raw=dict(code=0,data=dict(page=dict(num=1,size=20,count=1),replies=[dict(rpid=9007199254740993,mid=321,root=0,parent=0,ctime=T,rcount=0,content=dict(message="过了"),member=dict(uname="PRIVATE_NAME"))]))
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,*args): return json.dumps(raw).encode()
        api=HTTP(self.s)
        with patch.object(api.opener,"open",return_value=Response()) as get, patch("observer.collect.time.sleep"):
            one=api.get("roots",dict(oid="123",pn=1))
            two=api.get("roots",dict(oid="123",pn=1))
        self.assertEqual(get.call_count,1)
        self.assertEqual(one,two)
        normalized=normalize(one["response"]["data"]["replies"][0],BV)
        self.assertEqual(normalized["id"],"9007199254740993")
        text="".join(p.read_text(encoding="utf-8") for p in (self.s.path/"cache").glob("*.json"))
        self.assertNotIn("PRIVATE_NAME",text)

    def test_transient_5xx_has_bounded_retry(self):
        api=HTTP(self.s)
        error=urllib.error.HTTPError("https://api.bilibili.com/",503,"unavailable",None,None)
        with patch.object(api.opener,"open",side_effect=error) as get, patch("observer.collect.time.sleep"):
            with self.assertRaises(AccessError):
                api.get("view",{"bvid":BV})
        self.assertEqual(get.call_count,3)


class PagingTests(Base):
    def test_all_roots_and_old_root_new_reply(self):
        roots = [comment(str(i), ctime=T-100, count=1 if i==1 else 0) for i in range(1,22)]
        child = comment("9007199254740993", root="1", parent="1", ctime=T+20)
        api = FakeAPI(roots, {"1":[child]})
        status, rows, obs = collect_video(self.s, api, self.video())
        self.assertEqual(status["status"], "enumerated_pending_review")
        self.assertEqual(len(rows), 22)
        self.assertEqual(next(r for r in rows if r["level"]=="reply")["id"], "9007199254740993")
        self.assertTrue(any(route=="replies" and p["root"]=="21" for route,p in api.calls))
        self.assertEqual(len(status["root_paging"]["pages"]),3)

    def test_same_text_same_author_different_ids_not_merged(self):
        status, rows, _ = collect_video(self.s, FakeAPI([comment("1"),comment("2")]), self.video())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["author_id"],rows[1]["author_id"])
        self.assertEqual(rows[0]["text_hash"], rows[1]["text_hash"])

    def test_pinned_duplicate_keeps_one_entity_and_observations(self):
        class PinAPI(FakeAPI):
            def get(inner, route, p):
                e = super().get(route,p)
                if route=="roots":
                    e["response"]["data"]["top"] = {"upper":comment("1")}
                return e
        status, rows, obs = collect_video(self.s, PinAPI([comment("1")]), self.video())
        self.assertEqual(status["status"], "enumerated_pending_review")
        self.assertEqual(len(rows),1)
        self.assertGreater(len(obs),1)
        self.assertTrue(rows[0]["pinned"])

    def test_fake_end_with_three_hot_comments_fails(self):
        status, rows, _ = collect_video(self.s, FakeAPI([comment(str(i)) for i in range(1,4)], count_override=1000), self.video())
        self.assertEqual(status["status"],"incomplete")
        self.assertIn("terminal_count_mismatch",status["reason"])
        self.assertEqual(len(rows),3)

    def test_repeated_page_fails(self):
        status, _, _ = collect_video(self.s, FakeAPI([comment("1")], repeat=True), self.video())
        self.assertEqual(status["reason"],"duplicate_or_repeated_page")

    def test_missing_reply_page_fails_and_keeps_partial(self):
        children = [comment(str(i),root="1",parent="1") for i in range(2,24)]
        api = FakeAPI([comment("1",count=22)], {"1":children}, fail=lambda r,p:r=="replies" and p["pn"]==2)
        status, rows, _ = collect_video(self.s,api,self.video())
        self.assertEqual(status["reason"],"http_412")
        self.assertEqual(len(rows),21)

    def test_safety_limit_not_success(self):
        self.s.config["http"]["max_pages"] = 1
        status, _, _ = collect_video(self.s,FakeAPI([comment("1")]),self.video())
        self.assertEqual(status["reason"],"safety_page_limit_not_terminal")

    def test_count_changes_fail(self):
        class Drift(FakeAPI):
            def get(inner, route,p):
                e=super().get(route,p)
                if p["pn"]>1:
                    e["response"]["data"]["page"]["count"]+=1
                return e
        status, _, _ = collect_video(self.s,Drift([comment("1")]),self.video())
        self.assertEqual(status["reason"],"count_changed_during_capture")

    def test_missing_ancestor_fails(self):
        api = FakeAPI([comment("1",count=1)],{"1":[comment("2",root="1",parent="999")]})
        status, _, _ = collect_video(self.s,api,self.video())
        self.assertEqual(status["reason"],"missing_ancestor")

    def test_zero_comment_video_has_normal_end(self):
        status, rows, _ = collect_video(self.s,FakeAPI(),self.video())
        self.assertEqual(status["status"],"enumerated_pending_review")
        self.assertEqual(status["unique_count"],0)

    def test_inline_reply_preview_not_used_as_full_thread(self):
        root=comment("1",count=2)
        root["replies"]=[comment("2",root="1",parent="1")]
        api=FakeAPI([root],{"1":[comment("2",root="1",parent="1"),comment("3",root="1",parent="2")]})
        status, rows, _=collect_video(self.s,api,self.video())
        self.assertEqual(len(rows),3)
        self.assertEqual(status["status"],"enumerated_pending_review")

    def test_raw_profile_minimized_and_actor_stable(self):
        api=HTTP(self.s)
        r=comment("9007199254740993")
        r.update(mid=123, member=dict(mid=123,uname="不要存我",sex="不要存我",vip={}))
        clean=api.redact_comment(r)
        self.assertNotIn("member",clean)
        self.assertNotIn("mid",clean)
        self.assertEqual(clean["author_id"],api.actor("123"))
        self.assertNotIn("不要存我",json.dumps(clean,ensure_ascii=False))


class FrameTests(Base):
    def setup_collection(self):
        vf=dict(config_hash=self.s.config_hash,coverage_stable=False,videos=[self.video()])
        self.s.immutable("video_frame.json",vf)
        api=FakeAPI([comment("1",ctime=T-1,count=1)],{"1":[comment("2",root="1",parent="1",ctime=T+1)]})
        state,rows,obs=collect_video(self.s,api,self.video())
        write_json(self.s.path/"collection.json",dict(config_hash=self.s.config_hash,video_frame_hash=digest(vf),videos=[state],comments_hash=digest(rows),observations_hash=digest(obs)))
        write_jsonl(self.s.path/"comments.jsonl",rows)
        write_jsonl(self.s.path/"observations.jsonl",obs)
        write_csv(self.s.path/"collection_review.csv",[dict(bvid=BV,status="accepted",count_semantics_evidence="fixture",ui_count_scope="all historical fixture",reconciliation="fixture",pagination_evidence="fixture",reviewer="fixture")],["bvid","status","count_semantics_evidence","ui_count_scope","reconciliation","pagination_evidence","reviewer"])

    def test_old_ancestor_only_context_and_reply_in_all_three_domains(self):
        self.setup_collection()
        cf=freeze_comments(self.s)
        self.assertEqual(cf["context_ids"],["1"])
        self.assertEqual(cf["domains"],{m:["2"] for m in MODES})

    def test_missing_independent_capture_review_blocks_freeze(self):
        self.setup_collection()
        (self.s.path/"collection_review.csv").unlink()
        with self.assertRaises(GateError):
            freeze_comments(self.s)

    def test_partial_capture_blocks_freeze(self):
        self.setup_collection()
        c=read_json(self.s.path/"collection.json")
        c["videos"][0]["status"]="incomplete"
        write_json(self.s.path/"collection.json",c)
        with self.assertRaises(GateError):
            freeze_comments(self.s)

    def test_body_edit_even_with_same_count_blocks_freeze(self):
        self.setup_collection()
        rows=[json.loads(x) for x in (self.s.path/"comments.jsonl").read_text(encoding="utf-8").splitlines()]
        rows[0]["text"]="被意外改写"
        write_jsonl(self.s.path/"comments.jsonl",rows)
        with self.assertRaises(GateError):
            freeze_comments(self.s)


class DiscoveryTests(Base):
    def review_all(self):
        rows=read_csv(self.s.path/"video_review.csv")
        for n,r in enumerate(rows):
            r.update(decision="include",reason="合成来源",period_evidence="00:12 synthetic",reviewer="fixture",aid=str(n+1),published_at=str(T-10),primary_up="456",coauthors="",tags="<none>",content_type="guide")
        write_csv(self.s.path/"video_review.csv",rows,list(rows[0]))
        return rows

    class Search:
        def __init__(self,cap=False,blocked=False):
            self.calls=[]
            self.cap=cap
            self.blocked=blocked
        def get(self,route,p):
            self.calls.append((route,p))
            if self.blocked:
                raise AccessError("http_412")
            active=p["keyword"]==template()["queries"][0]["keyword"]
            values=[dict(type="video",bvid="BV"+str(i).zfill(10),title="synthetic",aid=i) for i in range(1,23)] if active else []
            pn=p["page"]
            return envelope(dict(numPages=50 if self.cap else (2 if active else 0),numResults=len(values),result=values[(pn-1)*20:pn*20]))

    def test_complete_all54_and_more_than_first12(self):
        api=self.Search()
        summaries=discover(self.s,api,"main")
        self.assertEqual(len(summaries),54)
        self.assertEqual(len(read_csv(self.s.path/"video_review.csv")),22)
        self.assertTrue(any(p["page"]==2 for _,p in api.calls))
        self.assertEqual(summaries[0]["unique_videos"],22)

    def test_cap_and_access_error_never_complete(self):
        for api in (self.Search(cap=True),self.Search(blocked=True)):
            with self.assertRaises(GateError):
                discover(self.s,api,"main")
            obj=read_json(self.s.path/"discovery_main.json")
            self.assertTrue(any(q["status"]=="incomplete" for q in obj["queries"]))

    def test_audit_cannot_start_before_baseline_freeze(self):
        with self.assertRaises(FileNotFoundError):
            discover(self.s,self.Search(),"audit_a")

    def test_missing_search_last_page_not_called_complete(self):
        class Missing(self.Search):
            def get(inner,route,p):
                e=super().get(route,p)
                if p["page"]==2:
                    e["response"]["data"]["result"]=[]
                return e
        with self.assertRaises(GateError):
            discover(self.s,Missing(),"main")
        obj=read_json(self.s.path/"discovery_main.json")
        self.assertIn("search_terminal_count_mismatch",obj["queries"][0]["reason"])

    def test_b_audit_addition_marks_coverage_unstable(self):
        discover(self.s,self.Search(),"main")
        self.review_all()
        checkpoint(self.s,"main")
        discover(self.s,self.Search(),"audit_a")
        checkpoint(self.s,"audit_a")
        discover(self.s,self.Search(),"audit_b")
        # 模拟最后审计正常命中额外来源；原始命中表同步保留。
        d=read_json(self.s.path/"discovery_audit_b.json")
        d["queries"][0]["hits"].append(dict(bvid="BV0000000099",page=1,rank=1))
        write_json(self.s.path/"discovery_audit_b.json",d)
        self.s.candidate("BV0000000099",MODES[0])
        self.review_all()
        checkpoint(self.s,"audit_b")
        path_template(self.s)
        paths=read_csv(self.s.path/"paths.csv")
        for r in paths:
            r.update(status="complete",evidence="fixture",reviewer="fixture")
        write_csv(self.s.path/"paths.csv",paths,list(paths[0]))
        self.assertFalse(freeze_videos(self.s)["coverage_stable"])

    def test_review_cannot_drop_a_discovered_source(self):
        discover(self.s,self.Search(),"main")
        rows=self.review_all()
        write_csv(self.s.path/"video_review.csv",rows[1:],list(rows[0]))
        with self.assertRaises(GateError):
            checkpoint(self.s,"main")

    def test_main_a_b_paths_union_no_creator_quota(self):
        discover(self.s,self.Search(),"main")
        self.review_all()
        checkpoint(self.s,"main")
        discover(self.s,self.Search(),"audit_a")
        checkpoint(self.s,"audit_a")
        discover(self.s,self.Search(),"audit_b")
        checkpoint(self.s,"audit_b")
        path_template(self.s)
        paths=read_csv(self.s.path/"paths.csv")
        for r in paths:
            r.update(status="complete",evidence="synthetic full public list",reviewer="fixture")
        write_csv(self.s.path/"paths.csv",paths,list(paths[0]))
        frame=freeze_videos(self.s)
        self.assertEqual(len(frame["videos"]),22)
        self.assertEqual(len({v["primary_up"] for v in frame["videos"]}),1)
        self.assertTrue(frame["coverage_stable"])


class RandomTests(Base):
    def test_replay_streams_and_no_replacement(self):
        ids=[str(i) for i in range(100)]
        a=permutation(ids,"ab"*32,"main")
        self.assertEqual(a,permutation(list(reversed(ids)),"ab"*32,"main"))
        self.assertEqual(set(a),set(ids))
        self.assertNotEqual(a,permutation(ids,"ab"*32,"audit"))
        self.assertEqual(permutation([],"ab"*32,"main"),[])

    def test_duplicate_random_ids_refused(self):
        with self.assertRaises(GateError):
            permutation(["1","1"],"ab"*32,"main")

    def test_target_400_not_manual_quota_and_pending_blocks(self):
        ids=[str(i) for i in range(1000)]
        rows={(MODES[0],i):dict(final="yes",relevance="related" if int(i)%2 else "irrelevant",reason="fixture",evidence="fixture",reviewer="fixture") for i in ids}
        selected=main_selection(ids,rows,MODES[0])
        self.assertEqual(len(selected["ids"]),400)
        self.assertEqual(len(selected["scanned"]),800)
        rows[(MODES[0],"1")]["final"]="no"
        blocked=main_selection(ids,rows,MODES[0])
        self.assertEqual(blocked["next_id"],"1")
        self.assertEqual(blocked["ids"],[])

    def test_less_than_400_is_census_no_padding(self):
        self.frames(7)
        d=draw(self.s)
        self.fill_screen()
        e=export(self.s)
        locked=lock_selection(self.s)
        self.assertEqual(e[MODES[0]]["selected"],7)
        self.assertTrue(all(r["census"] for r in locked["domains"].values()))
        self.assertEqual(len(d["domains"][MODES[0]]["raw_audit"]),7)

    def test_draw_once_and_tampered_permutation_refused(self):
        self.frames()
        draw(self.s)
        with self.assertRaises(GateError):
            draw(self.s)
        d=read_json(self.s.path/"draw.json")
        d["domains"][MODES[0]]["main"].reverse()
        write_json(self.s.path/"draw.json",d)
        with self.assertRaises(GateError):
            load_draw(self.s)

    def test_raw_audit_is_200_unfiltered_not_inverse_stopping(self):
        self.frames(510)
        d=draw(self.s)
        self.fill_screen(False)
        locked=lock_selection(self.s)
        self.assertEqual(len(locked["domains"][MODES[0]]["ids"]),0)
        self.assertEqual(len(d["domains"][MODES[0]]["raw_audit"]),200)

    def test_screening_cannot_drop_id(self):
        self.frames()
        draw(self.s)
        r=self.fill_screen()
        write_csv(self.s.path/"screening.csv",r[1:],SCREEN_FIELDS)
        with self.assertRaises(GateError):
            export(self.s)

    def test_correction_replays_same_seed_and_retains_snapshot(self):
        self.frames(410)
        d=draw(self.s)
        r=self.fill_screen()
        original=lock_selection(self.s)
        first=original["domains"][MODES[0]]["ids"][0]
        next(x for x in r if x["id"]==first and x["mode"]==MODES[0])["relevance"]="irrelevant"
        write_csv(self.s.path/"screening.csv",r,SCREEN_FIELDS)
        updated=lock_selection(self.s,"固定准则误判纠正，合成测试")
        self.assertNotIn(first,updated["domains"][MODES[0]]["ids"])
        self.assertEqual(d["seed"],read_json(self.s.path/"draw.json")["seed"])
        self.assertNotEqual(original["review_file"],updated["review_file"])
        self.assertEqual(read_json(self.s.path/"selection_frozen.json"),original)

    def test_wilson_design_width(self):
        low,high=wilson(200,400)
        self.assertAlmostEqual((high-low)/2,0.0487654958,places=8)
        self.assertGreater(wilson(0,20)[1],.05)
        self.assertLess(wilson(0,200)[1],.05)


class ResultsTests(Base):
    def completed_inputs(self, n=420):
        self.frames(n)
        draw(self.s)
        self.fill_screen()
        sel=lock_selection(self.s)
        raw=read_csv(self.s.path/"raw_audit_review.csv")
        for r in raw:
            r.update(relevance="related",reason="fixture",evidence="fixture",reviewer="fixture",context_status="checked",role_checked="yes",date_checked="yes",final="yes")
        write_csv(self.s.path/"raw_audit_review.csv",raw,list(raw[0]))
        blind=read_csv(self.s.path/sel["review_file"])
        original={(r["mode"],r["id"]):r for r in sel["screening_snapshot"]}
        for r in blind:
            o=original[(r["mode"],r["id"])]
            r.update(review_kind="same_person_blind_recode",reviewer="fixture",relevance="related",themes=o["themes"],self_experience_themes=o["self_experience_themes"],corrected="no",resolution="fixture",final="yes")
        write_csv(self.s.path/sel["review_file"],blind,list(blind[0]))
        return sel

    def test_formal_estimates_gated_but_draft_allowed(self):
        self.frames()
        draw(self.s)
        self.fill_screen()
        lock_selection(self.s)
        with self.assertRaises(GateError):
            estimates(self.s)
        out=estimates(self.s,draft=True)
        self.assertEqual(out["status"],"DRAFT_NOT_VALIDATED")
        self.assertFalse((self.s.path/"estimates.json").exists())

    def test_result_denominators_coding_audit_and_no_overall_ratio(self):
        self.completed_inputs()
        out=estimates(self.s)
        self.assertEqual(set(out["domains"]),set(MODES))
        self.assertTrue(all(v["n"]==400 for v in out["domains"].values()))
        self.assertTrue(all(v["raw_audit"]["n"]==200 for v in out["domains"].values()))
        self.assertTrue(all(v["coding"]["n"]==100 for v in out["domains"].values()))
        self.assertFalse(out["coverage_stable"])
        self.assertFalse(out["domains"][MODES[0]]["qualitative"]["pass_gate"])

    def test_unknown_audit_risk_blocks_release(self):
        self.completed_inputs()
        raw=read_csv(self.s.path/"raw_audit_review.csv")
        for r in raw[:30]:
            r["relevance"]="unknown"
        write_csv(self.s.path/"raw_audit_review.csv",raw,list(raw[0]))
        with self.assertRaises(GateError):
            estimates(self.s)

    def test_small_domain_census_has_no_sampling_interval(self):
        self.completed_inputs(7)
        out=estimates(self.s)
        for r in out["domains"].values():
            self.assertTrue(r["census"])
            self.assertEqual(r["raw_audit"]["unknown_interval"],[0.,0.])
            self.assertEqual(r["raw_audit"]["related_rate_interval"],[1.,1.])

    def test_live_label_changes_require_versioned_correction(self):
        self.completed_inputs()
        r=read_csv(self.s.path/"screening.csv")
        r[0]["themes"]=""
        write_csv(self.s.path/"screening.csv",r,SCREEN_FIELDS)
        with self.assertRaises(GateError):
            estimates(self.s)


class QualTests(Base):
    def prepare_qual(self):
        videos=[]
        comments=[]
        for i in range(1,19):
            bv="BV"+str(i).zfill(10)
            v=self.video()
            v.update(bvid=bv,aid=str(i),primary_up=str(100+i),content_type="guide" if i<=2 or i>6 else "record" if i<=4 else "discussion")
            videos.append(v)
            comments.append(normalize(comment(str(i)),bv))
        self.s.immutable("video_frame.json",dict(config_hash=self.s.config_hash,videos=videos,coverage_stable=True))
        self.s.immutable("comment_frame.json",dict(config_hash=self.s.config_hash,comments=comments,domains={m:[r["id"] for r in comments] for m in MODES}))
        qual_init(self.s)
        write_csv(self.s.path/"qual_holdout.csv",[dict(mode=MODES[0],bvid=v["bvid"],reason="fixture",reviewer="fixture") for v in videos[-3:]],["mode","bvid","reason","reviewer"])
        reserve_qual(self.s)
        rows=read_csv(self.s.path/"qual_screening.csv")
        for r in rows:
            r.update(relevance="related",final="yes",reviewer="fixture",reason="fixture",evidence="fixture")
        write_csv(self.s.path/"qual_screening.csv",rows,SCREEN_FIELDS)
        return videos

    def test_reserved_sources_protected_and_validation_not_opened_early(self):
        v=self.prepare_qual()
        with self.assertRaises(GateError):
            qual_queue(self.s,MODES[0],v[-1]["bvid"],"development")
        with self.assertRaises(GateError):
            qual_queue(self.s,MODES[0],v[-1]["bvid"],"validation")

    def test_saturation_batches_holdout_and_new_information_reset(self):
        videos=self.prepare_qual()
        rows=[]
        fields=["mode","batch","role","bvids","new_problem","new_condition","new_counterexample","unresolved_gaps","evidence","reviewer","final"]
        groups=[("base",videos[:6]),("development",videos[6:9]),("development",videos[9:12]),("development",videos[12:15]),("validation",videos[15:])]
        for index,(role,group) in enumerate(groups):
            for v in group:
                q=qual_queue(self.s,MODES[0],v["bvid"],"validation" if role=="validation" else "development")
                self.assertEqual(q["state"],"ready")
                self.assertLessEqual(len(q["ids"]),30)
            rows.append(dict(mode=MODES[0],batch=str(index),role=role,bvids=";".join(v["bvid"] for v in group),new_problem="1" if role=="base" else "0",new_condition="0",new_counterexample="0",unresolved_gaps="none",evidence="synthetic",reviewer="fixture",final="yes"))
            write_csv(self.s.path/"qual_batches.csv",rows,fields)
        self.assertTrue(qualitative_status(self.s)[MODES[0]]["pass_gate"])
        extra=dict(rows[-1],role="new_information",new_condition="1")
        rows.append(extra)
        write_csv(self.s.path/"qual_batches.csv",rows,fields)
        self.assertFalse(qualitative_status(self.s)[MODES[0]]["pass_gate"])


if __name__ == "__main__":
    unittest.main()
