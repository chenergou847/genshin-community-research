import json
from unittest.mock import patch

from observer.core import GateError, digest, write_json
from observer.collect import collect_video, discover, payload
from observer.web_api import NormalWebAPI
from test_observer import Base, FakeAPI, comment, envelope, T, BV


class FakeWeb(NormalWebAPI):
    def __init__(self, pages, children=None):
        self.pages=pages
        self.children=children or {}
        self.calls=[]
    def actor(self,mid):
        return "UP_"+str(mid)
    def get(self,route,p):
        self.calls.append((route,p))
        if route=="roots_web":
            return envelope(self.pages[len([x for x in self.calls if x[0]==route])-1])
        return FakeAPI(replies=self.children).get("replies",p)


def page(rows,end,total,next_value=0,offset=None):
    return dict(cursor=dict(is_end=end,all_count=total,next=next_value,pagination_reply={"next_offset":offset} if offset else {}),replies=rows)


class CursorTests(Base):
    def empty_without_total(self):
        return dict(cursor=dict(is_begin=True,is_end=True,prev=0,next=0,pagination_reply={}),
                    replies=[],top_replies=[],top={},hots=[])

    def test_real_shape_empty_first_terminal_preserves_missing_total_for_review(self):
        api=FakeWeb([self.empty_without_total()])
        status,rows,_=collect_video(self.s,api,self.video())
        self.assertEqual(status['status'],'enumerated_pending_review')
        self.assertEqual(rows,[])
        self.assertNotIn('all_count',status['root_paging'])
        self.assertIsNone(status['root_paging']['reported_count'])
        self.assertIn('independent',status['root_paging']['count_review_required'])

    def test_missing_total_empty_not_end_still_rejected(self):
        data=self.empty_without_total();data['cursor']['is_end']=False
        status,_,_=collect_video(self.s,FakeWeb([data]),self.video())
        self.assertEqual(status['reason'],'cursor_schema_changed')

    def test_missing_total_with_pinned_comment_not_accepted_as_zero(self):
        data=self.empty_without_total();data['top_replies']=[comment('1')]
        status,_,_=collect_video(self.s,FakeWeb([data]),self.video())
        self.assertEqual(status['reason'],'cursor_schema_changed')

    def test_missing_total_nonempty_not_accepted_as_zero(self):
        data=self.empty_without_total();data['replies']=[comment('1')]
        status,_,_=collect_video(self.s,FakeWeb([data]),self.video())
        self.assertEqual(status['reason'],'cursor_schema_changed')

    def test_later_empty_terminal_without_total_not_accepted(self):
        data=self.empty_without_total()
        status,_,_=collect_video(self.s,FakeWeb([page([comment('1')],False,2,1),data]),self.video())
        self.assertEqual(status['reason'],'cursor_schema_changed')

    def test_two_cursor_pages_plus_complete_child_thread(self):
        api=FakeWeb([page([comment("1",count=1)],False,3,25,"normal_offset"),page([comment("2")],True,3)],{"1":[comment("3",root="1",parent="1")]})
        status,rows,_=collect_video(self.s,api,self.video())
        self.assertEqual(status["status"],"enumerated_pending_review")
        self.assertEqual(len(rows),3)
        second=[p for r,p in api.calls if r=="roots_web"][1]
        self.assertEqual(second["next"],25)
        self.assertEqual(json.loads(second["pagination_str"]),{"offset":"normal_offset"})

    def test_is_end_true_with_hidden_missing_roots_fails_total_check(self):
        api=FakeWeb([page([comment("1")],True,1000)])
        status,_,_=collect_video(self.s,api,self.video())
        self.assertEqual(status["reason"],"root_plus_reply_count_mismatch:1!=1000")

    def test_looping_cursor_not_accepted(self):
        api=FakeWeb([page([comment("1")],False,2,0)])
        status,_,_=collect_video(self.s,api,self.video())
        self.assertEqual(status["reason"],"cursor_loop")

    def test_count_drift_not_silently_accepted(self):
        api=FakeWeb([page([comment("1")],False,2,1),page([comment("2")],True,3)])
        status,_,_=collect_video(self.s,api,self.video())
        self.assertEqual(status["reason"],"all_count_changed_during_capture")

    def test_empty_cursor_without_terminal_fails(self):
        api=FakeWeb([page([],False,2,1)])
        status,_,_=collect_video(self.s,api,self.video())
        self.assertEqual(status["reason"],"empty_cursor_page_before_end")


class PartitionTests(Base):
    def configure(self):
        self.s.config["date_partitioning"]=dict(begin_param="pubtime_begin_s",end_param="pubtime_end_s",result_cap=1000,evidence="synthetic",verified_status="passed_positive_and_negative_boundary_checks",evidence_hashes=["SYNTHETIC_TEST_ONLY"])
        self.s.config["t0"]="1970-01-01T00:00:03+00:00"
        for p in self.s.config["periods"].values():
            p["start"]="1970-01-01T00:00:01+00:00"
        self.s.config_hash=digest(self.s.config)

    class Search:
        def __init__(self,ignore=False,always_cap=False):
            self.calls=[]
            self.ignore=ignore
            self.always_cap=always_cap
        def get(self,route,p):
            self.calls.append(p)
            lo,hi=p["pubtime_begin_s"],p["pubtime_end_s"]
            if self.ignore:
                values=[dict(type="video",bvid="BV0000000001",pubdate=99)]
                return envelope(dict(numPages=1,numResults=1,result=values))
            if lo<hi or self.always_cap:
                return envelope(dict(numPages=50,numResults=1000,result=[]))
            values=[dict(type="video",bvid="BV"+str(lo+1).zfill(10),pubdate=lo,aid=lo+1,title="synthetic")]
            return envelope(dict(numPages=1,numResults=1,result=values))

    def test_recursive_leaves_cover_full_range_no_gaps(self):
        self.configure()
        api=self.Search()
        results=discover(self.s,api,"main")
        self.assertEqual(len(results),54)
        self.assertEqual([(x["begin"],x["end"]) for x in results[0]["date_leaves"]],[(1,1),(2,2),(3,3)])
        self.assertEqual(results[0]["unique_videos"],3)
        self.assertTrue(all(call['pubtime_begin_s'] > 0 for call in api.calls))
        self.assertEqual(results[0]["status"],"endpoint_terminal")

    def test_registered_publication_start_limits_every_requested_bin(self):
        self.configure()
        self.s.config['video_publish_start']='1970-01-01T00:00:02+00:00'
        self.s.config_hash=digest(self.s.config)
        api=self.Search()
        result=discover(self.s,api,'main')[0]
        self.assertEqual([(x['begin'],x['end']) for x in result['date_leaves']],[(2,2),(3,3)])
        self.assertTrue(all(p['pubtime_begin_s']>=2 for p in api.calls))

    def test_ignored_date_filter_fails(self):
        self.configure()
        api=self.Search(ignore=True)
        with self.assertRaises(GateError):
            discover(self.s,api,"main")
        self.assertEqual(len(api.calls),1)

    def test_explicit_zero_counts_can_omit_result(self):
        self.configure()
        class Empty:
            def get(self,route,p):
                return envelope(dict(numPages=0,numResults=0))
        result=discover(self.s,Empty(),"main")
        self.assertTrue(all(x['status']=='endpoint_terminal' and x['unique_videos']==0 for x in result))

    def test_nonzero_missing_result_cannot_be_empty_end(self):
        self.configure()
        class Missing:
            def get(self,route,p):
                return envelope(dict(numPages=1,numResults=1))
        with self.assertRaises(GateError):
            discover(self.s,Missing(),"main")

    def test_nonempty_result_with_zero_totals_cannot_pass(self):
        self.configure()
        class Inconsistent:
            def get(self,route,p):
                return envelope(dict(numPages=0,numResults=0,result=[dict(bvid='BV0000000001',pubdate=1)]))
        with self.assertRaises(GateError):
            discover(self.s,Inconsistent(),"main")

    class Unstable:
        def __init__(self,kind):
            self.kind=kind
        def get(self,route,p):
            lo,hi,pn=p['pubtime_begin_s'],p['pubtime_end_s'],p['page']
            def rows(points):
                return [dict(bvid='BV'+str(i).zfill(10),pubdate=i) for i in points]
            if (lo,hi)==(1,3):
                if pn==1:
                    return envelope(dict(numPages=2,numResults=3,result=rows([1,2])))
                if self.kind=='overlap':
                    return envelope(dict(numPages=2,numResults=3,result=rows([1,3])))
                if self.kind=='drift':
                    return envelope(dict(numPages=2,numResults=4,result=rows([3])))
                return envelope(dict(numPages=2,numResults=3,result=[]))
            return envelope(dict(numPages=1,numResults=hi-lo+1,result=rows(range(lo,hi+1))))

    def test_pagination_overlap_splits_instead_of_passing_bad_parent(self):
        self.configure()
        r=discover(self.s,self.Unstable('overlap'),'main')[0]
        self.assertEqual(r['status'],'endpoint_terminal')
        self.assertEqual([(x['begin'],x['end']) for x in r['date_leaves']],[(1,2),(3,3)])

    def test_total_drift_splits_into_consistent_leaves(self):
        self.configure()
        r=discover(self.s,self.Unstable('drift'),'main')[0]
        self.assertEqual(r['status'],'endpoint_terminal')
        self.assertEqual(sum(x['unique_videos'] for x in r['date_leaves']),3)

    def test_terminal_mismatch_splits_into_consistent_leaves(self):
        self.configure()
        r=discover(self.s,self.Unstable('mismatch'),'main')[0]
        self.assertEqual(r['status'],'endpoint_terminal')
        self.assertEqual(sum(x['unique_videos'] for x in r['date_leaves']),3)

    def test_single_second_still_capped_cannot_pass(self):
        self.configure()
        with self.assertRaises(GateError):
            discover(self.s,self.Search(always_cap=True),"main")
