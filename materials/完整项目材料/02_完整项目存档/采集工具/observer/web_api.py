"""按正常网页公开会话与WBI传输协议读取；不提取浏览器凭证，不绕过访问挑战。"""
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .core import GateError, now
from .collect import HTTP, AccessError, payload, rid

TABLE = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]


class NormalWebAPI(HTTP):
    def __init__(self, study, capture_namespace=None, source_captures=None):
        super().__init__(study, capture_namespace=capture_namespace)
        self.source_captures = source_captures or {}
        self.source_apis = {}
        try:
            req=urllib.request.Request("https://www.bilibili.com/", headers={"User-Agent":"Mozilla/5.0"})
            with self.opener.open(req, timeout=int(self.h["timeout_seconds"])) as response:
                response.read(32*1024*1024)
            self.last=time.monotonic()
            self.s.event("normal_public_session_started", adapter="web_wbi_v1", credential_source="user_supplied_file" if __import__('os').environ.get('BILI_COOKIE_FILE') else "anonymous_public_session")
            nav=payload(super().get("nav_public",{}))
            pair=nav.get("wbi_img") or {}
            raw="".join(pair.get(k,"").rsplit("/",1)[-1].split(".")[0] for k in ("img_url","sub_url"))
            if len(raw)!=64:
                raise GateError("normal_public_wbi_key_unavailable")
            self.mixin="".join(raw[i] for i in TABLE)[:32]
        except urllib.error.HTTPError as e:
            self.s.event("normal_public_session_failed",reason="http_"+str(e.code))
            raise AccessError("http_"+str(e.code))
        except (urllib.error.URLError,OSError) as e:
            self.s.event("normal_public_session_failed",reason="network_"+type(e).__name__)
            raise AccessError("network_"+type(e).__name__)

    def for_video(self, video):
        """Replay an explicitly registered fresh capture of the same source."""
        namespace = self.source_captures.get(video['bvid'])
        if namespace is None:
            return self
        if namespace not in self.source_apis:
            self.source_apis[namespace] = NormalWebAPI(self.s, capture_namespace=namespace)
        return self.source_apis[namespace]

    def sign(self,params):
        p={k:str(v) for k,v in dict(params,wts=int(time.time())).items()}
        p={k:"".join(c for c in v if c not in "!'()*") for k,v in p.items()}
        query=urllib.parse.urlencode(sorted(p.items()))
        p["w_rid"]=hashlib.md5((query+self.mixin).encode()).hexdigest()
        return p

    def get(self,route,params):
        mapped={"view":"view_web","search":"search_web_wbi","replies":"replies_web"}.get(route,route)
        return super().get(mapped,self.sign(params) if mapped in ("view_web","roots_web","search_web_wbi") else params)

    def root_paging(self,s,aid,consume):
        next_value, offset = 0, None
        cursors, signatures, unique, pages = set(),set(),set(),[]
        expected=None
        for pn in range(1,int(s.config["http"]["max_pages"])+1):
            cursor_key=(str(next_value),offset)
            if cursor_key in cursors:
                raise GateError("cursor_loop")
            cursors.add(cursor_key)
            params=dict(oid=aid,type=1,mode=2,next=next_value,ps=20,plat=1,web_location=1315875)
            if offset:
                params["pagination_str"]=json.dumps({"offset":offset},separators=(",",":"))
            env=self.get("roots_web",params)
            d=payload(env)
            c=d.get("cursor")
            if not isinstance(c,dict) or type(c.get("is_end")) is not bool:
                raise GateError("cursor_schema_changed")
            # Observed normal zero-comment response: begin+end, no rows and no
            # all_count. Preserve the missing total instead of inventing one.
            # This only reaches pending independent count/terminal review.
            if "all_count" not in c:
                empty_first_end=(pn==1 and c.get("is_begin") is True and c["is_end"]
                    and c.get("prev")==0 and c.get("next")==0
                    and c.get("pagination_reply")=={}
                    and not any(d.get(k) for k in ("replies","top_replies","top","hots")))
                if not empty_first_end:
                    raise GateError("cursor_schema_changed")
                page=dict(pn=pn,ids=[],all_count=None,acount=None,cursor=c,
                          captured_at=env["captured_at"],response_hash=env["response_hash"])
                s.event("comment_cursor_empty_terminal_without_total",**page)
                return dict(status="enumerated",normal_end=True,
                            end_signal="first_cursor_explicit_begin_and_end_empty_no_total",
                            unique_count=0,reported_count=None,pages=[page],
                            count_review_required="no_total_returned_check_independent_metadata_or_UI")
            total=int(c["all_count"])
            if expected is not None and total!=expected:
                raise GateError("all_count_changed_during_capture")
            expected=total
            regular=d.get("replies") or []
            ids=tuple(rid(r) for r in regular)
            if len(set(ids))!=len(ids) or (ids and ids in signatures) or set(ids)&unique:
                raise GateError("duplicate_repeated_or_overlapping_cursor_page")
            unique.update(ids)
            signatures.add(ids)
            for rank,r in enumerate(regular,1):
                consume(r,False,env,pn,rank)
            for rank,r in enumerate(list((d.get("top") or {}).values())+(d.get("top_replies") or []),1):
                if isinstance(r,dict) and (r.get("rpid_str") or r.get("rpid")):
                    consume(r,True,env,pn,rank)
            page=dict(pn=pn,ids=list(ids),all_count=total,acount=None,cursor=c,captured_at=env["captured_at"],response_hash=env["response_hash"])
            pages.append(page)
            s.event("comment_cursor_page",**page)
            if c["is_end"]:
                return dict(status="enumerated",normal_end=True,end_signal="cursor_is_end_plus_full_root_reply_reconciliation",unique_count=len(unique),all_count=total,pages=pages)
            if not regular:
                raise GateError("empty_cursor_page_before_end")
            next_value=c.get("next")
            offset=(c.get("pagination_reply") or {}).get("next_offset")
            if next_value is None and not offset:
                raise GateError("missing_next_cursor")
        raise GateError("safety_page_limit_not_terminal")
