"""正常只读 HTTP 适配器。接口形状需实测；不签名、不绕过风控、不提取浏览器凭证。"""
from __future__ import annotations

import hashlib
import hmac
import http.cookiejar
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .core import (GateError, MODES, VIDEO_FIELDS, bvid, canonical, digest, identifier,
                   now, read_csv, read_json, source_hash, ts, write_csv, write_json, write_jsonl)


ROUTES = {"view": "/x/web-interface/view", "search": "/x/web-interface/search/type",
          "roots": "/x/v2/reply", "replies": "/x/v2/reply/reply",
          "view_web": "/x/web-interface/wbi/view", "roots_web": "/x/v2/reply/wbi/main",
          "search_web": "/x/web-interface/search/type", "replies_web": "/x/v2/reply/reply",
          "search_web_wbi": "/x/web-interface/wbi/search/type",
          "reply_jump_web": "/x/v2/reply/jump",
          "reply_detail_web": "/x/v2/reply/detail",
          "reply_dialog_web": "/x/v2/reply/dialog/cursor",
          "nav_public": "/x/web-interface/nav"}


class AccessError(GateError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class HTTP:
    def __init__(self, study, capture_namespace=None):
        self.s = study
        self.h = study.config["http"]
        if capture_namespace is not None and not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', capture_namespace):
            raise GateError('invalid_capture_namespace')
        self.capture_namespace = capture_namespace
        self.cache_root = study.path / 'cache' if capture_namespace is None else study.path / 'cache_captures' / capture_namespace
        self.last = 0.
        self.key = bytes.fromhex(read_json(study.path / ".private.json")["author_hmac_key"])
        self.key_id = hashlib.sha256(self.key).hexdigest()
        self.jar = http.cookiejar.CookieJar()
        cookie_file = os.environ.get("BILI_COOKIE_FILE")
        if cookie_file:
            supplied = http.cookiejar.MozillaCookieJar(cookie_file)
            supplied.load(ignore_discard=True, ignore_expires=False)
            for c in supplied:
                if c.domain.lstrip(".") in ("bilibili.com", "api.bilibili.com", "www.bilibili.com"):
                    self.jar.set_cookie(c)
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def actor(self, mid):
        return "U_" + hmac.new(self.key, identifier(mid).encode(), hashlib.sha256).hexdigest()[:24]

    def redact_comment(self, r):
        # 只保存研究所需字段；不会把昵称、IP、性别、会员和个人签名存入原始归档。
        mid = r.get("mid") or (r.get("member") or {}).get("mid")
        result = {k: r[k] for k in ("rpid", "rpid_str", "root", "root_str", "parent", "parent_str", "dialog", "ctime", "like", "rcount", "count", "state", "floor") if k in r}
        result["author_id"] = self.actor(mid) if mid else None
        content = r.get("content") or {}
        result["content"] = {k: content[k] for k in ("message", "pictures", "emote", "attachment") if k in content}
        result["replies"] = [self.redact_comment(x) for x in r.get("replies") or []]
        if isinstance(r.get('folder'), dict):
            result['folder'] = {k: v for k, v in r['folder'].items()
                                if k in ('has_folded', 'is_folded', 'rule') and isinstance(v, (bool, int, str))}
        return result

    def sanitize(self, route, data):
        if route == "nav_public":
            return {"code":data.get("code"), "data":{"wbi_img":(data.get("data") or {}).get("wbi_img")}}
        if route not in ("roots", "replies", "roots_web", "replies_web", "reply_jump_web", "reply_detail_web", "reply_dialog_web"):
            return data
        # 保留分页/数量原始返回，但去除不需要的用户画像。
        d = data.get("data") or {}
        clean = {k: d[k] for k in ("page", "cursor", "notice", "config", "upper") if k in d}
        clean.pop("upper", None)
        if 'FoldRpids' in d:
            folded = d['FoldRpids']
            if folded is not None and not isinstance(folded, list):
                raise GateError('folded_ID_schema_changed')
            clean['FoldRpids'] = None if folded is None else [identifier(i) for i in folded]
        if isinstance(d.get('dialog'), dict):
            clean['dialog'] = {k: d['dialog'][k] for k in ('min_floor', 'max_floor') if k in d['dialog']}
        if isinstance(d.get('control'), dict):
            clean['fold_control'] = {k: v for k, v in d['control'].items()
                                     if 'fold' in k.lower() and isinstance(v, (bool, int, str, type(None)))}
        if isinstance(d.get('folder'), dict):
            clean['folder'] = {k: v for k, v in d['folder'].items()
                               if k in ('has_folded', 'is_folded', 'rule') and isinstance(v, (bool, int, str))}
        clean["replies"] = [self.redact_comment(r) for r in d.get("replies") or []]
        clean["top_replies"] = [self.redact_comment(r) for r in d.get("top_replies") or []]
        clean["hots"] = [self.redact_comment(r) for r in d.get("hots") or []]
        clean["top"] = {k: self.redact_comment(v) for k, v in (d.get("top") or {}).items() if isinstance(v, dict) and (v.get("rpid") or v.get("rpid_str"))}
        if d.get("root"):
            clean["root"] = self.redact_comment(d["root"])
        result = {"code": data["code"], "data": clean}
        result['source_data_keys'] = sorted(d)
        if route in ('reply_jump_web','reply_detail_web','reply_dialog_web'):
            result['message'] = data.get('message')
            result['source_data_was_null'] = data.get('data') is None
        return result

    def get(self, route, params):
        if route not in ROUTES:
            raise GateError("未知只读路由")
        logical_params = {k:v for k,v in params.items() if k not in ("wts","w_rid")}
        token = digest({"route": route, "params": logical_params})
        p = self.cache_root / (token + ".json")
        if p.exists():
            envelope = read_json(p)
            if digest(envelope["response"]) != envelope["response_hash"]:
                raise GateError("请求缓存哈希损坏")
            cached_data=envelope["response"].get("data")
            if isinstance(cached_data,dict) and cached_data.get("v_voucher"):
                self.s.event("cached_response_reclassified_access_challenge",route=route,params=logical_params,cache=token)
                raise AccessError("access_challenge_voucher_present")
            if route in ("roots", "replies", "roots_web", "replies_web", "reply_jump_web", "reply_detail_web", "reply_dialog_web") and envelope.get("author_key_id") != self.key_id:
                raise GateError("匿名化密钥与缓存不一致，不能混用作者关系")
            self.s.event("cache_hit", route=route, params=logical_params, cache=token)
            return envelope
        url = "https://api.bilibili.com" + ROUTES[route] + "?" + urllib.parse.urlencode(params)
        retries = max(0, min(3, int(self.h["retries"])))
        for attempt in range(retries + 1):
            time.sleep(max(0., max(1., float(self.h["delay_seconds"])) - (time.monotonic() - self.last)))
            started = now()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/", "Accept": "application/json"})
                with self.opener.open(req, timeout=int(self.h["timeout_seconds"])) as response:
                    raw = response.read(32 * 1024 * 1024 + 1)
                self.last = time.monotonic()
                if len(raw) > 32 * 1024 * 1024:
                    raise AccessError("response_too_large")
                try:
                    body = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    raise AccessError("non_json_or_challenge")
                if isinstance(body,dict) and isinstance(body.get("data"),dict) and body["data"].get("v_voucher"):
                    raise AccessError("access_challenge_voucher_present")
                public_key_response = isinstance(body,dict) and route=="nav_public" and body.get("code")==-101 and (body.get("data") or {}).get("wbi_img")
                # A direct lookup may report this particular comment absent.
                # This is non-recovery evidence, never a zero-row success.
                # Authentication, rate limits and challenges still stop.
                absent_comment = isinstance(body,dict) and route=='reply_jump_web' and body.get('code')==12006
                if not isinstance(body, dict) or (body.get("code") != 0 and not public_key_response and not absent_comment):
                    raise AccessError("api_code_" + str(body.get("code") if isinstance(body, dict) else "invalid"))
                data = self.sanitize(route, body)
                envelope = dict(route=route, params=logical_params, captured_at=started, response=data,
                                response_hash=digest(data), original_bytes_sha256=hashlib.sha256(raw).hexdigest(),
                                author_key_id=self.key_id if route in ("roots", "replies", "roots_web", "replies_web", "reply_jump_web", "reply_detail_web", "reply_dialog_web") else None,
                                storage="comments_minimized_no_profile_or_credentials")
                if self.capture_namespace is not None:
                    envelope['capture_namespace'] = self.capture_namespace
                write_json(p, envelope)
                self.s.event("request_ok", route=route, params=logical_params, attempt=attempt + 1, cache=token, captured_at=started)
                return envelope
            except urllib.error.HTTPError as e:
                reason = "http_" + str(e.code)
                # 风控/登录/限流停止，绝不以换身份或并发重试绕过。
                retryable = e.code in (500, 502, 503, 504)
            except AccessError as e:
                reason, retryable = e.reason, False
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                reason = "network_" + type(e).__name__
                retryable = True
            self.last = time.monotonic()
            self.s.event("request_failed", route=route, params=logical_params, attempt=attempt + 1, reason=reason)
            if not retryable or attempt == retries:
                raise AccessError(reason)
            time.sleep(min(8, 2 ** (attempt + 1)))
        raise AccessError("unreachable")


def payload(envelope):
    data = envelope["response"].get("data")
    if not isinstance(data, dict):
        raise GateError("接口 data 缺失；不能解释为零条")
    return data


def discover(s, api, group):
    if s.config.get("date_partitioning"):
        return discover_partitioned(s,api,group)
    s.validate()
    s.assert_mutable()
    prior = {"audit_a": "main", "audit_b": "audit_a"}.get(group)
    if prior:
        s.frozen("checkpoint_" + prior + ".json")
    summaries = []
    for q in (q for q in s.config["queries"] if q["group"] == group):
        ids, hits, seen_pages = set(), [], set()
        state, reason = "incomplete", "not_started"
        try:
            total = None
            for pn in range(1, int(s.config["http"]["max_pages"]) + 1):
                params = dict(search_type="video", keyword=q["keyword"], order=q["order"], page=pn, **q.get("date_params", {}))
                env = api.get("search", params)
                d = payload(env)
                if "numPages" not in d or "numResults" not in d or "result" not in d:
                    raise GateError("search_schema_changed")
                n_pages, n_total = int(d["numPages"]), int(d["numResults"])
                if total is not None and total != (n_pages, n_total):
                    raise GateError("search_totals_changed")
                total = (n_pages, n_total)
                page_ids = []
                for rank, item in enumerate(d["result"] or [], 1):
                    if item.get("type", "video") != "video":
                        continue
                    bv = bvid(item.get("bvid"))
                    page_ids.append(bv)
                    hits.append(dict(bvid=bv, page=pn, rank=rank, duplicate=bv in ids, captured_at=env["captured_at"]))
                    ids.add(bv)
                    s.candidate(bv, q["mode"], {"title": re.sub("<[^>]*>", "", item.get("title", "")), "aid": str(item.get("aid", ""))})
                signature = tuple(page_ids)
                if signature and signature in seen_pages:
                    raise GateError("search_repeated_page")
                seen_pages.add(signature)
                s.event("search_page", query=q, page=pn, ids=page_ids, num_pages=n_pages, num_results=n_total, captured_at=env["captured_at"])
                if n_pages >= int(s.config["http"]["search_cap_pages"]):
                    raise GateError("search_cap_possible_register_verified_date_bins")
                if pn >= max(1, n_pages):
                    if len(ids) != n_total:
                        raise GateError(f"search_terminal_count_mismatch:{len(ids)}!={n_total}")
                    state, reason = "endpoint_terminal", "reported_last_page"
                    break
                if not page_ids:
                    raise GateError("search_empty_before_last_page")
            else:
                raise GateError("search_safety_limit")
        except GateError as e:
            reason = str(e)
        summaries.append(dict(query=q, status=state, reason=reason, unique_videos=len(ids), hits=hits))
        # 每个查询结束写检查点，进程中断仍可从缓存重放；不是只存最终列表。
        write_json(s.path / ("discovery_" + group + ".json"), dict(config_hash=s.config_hash, queries=summaries, captured_at=now()))
        if reason.startswith(("http_", "api_code_", "non_json", "network_", "access_challenge", "search_schema_changed")):
            break
    expected = len([q for q in s.config["queries"] if q["group"] == group])
    if len(summaries) != expected or any(x["status"] != "endpoint_terminal" for x in summaries):
        raise GateError("检索未完成；已保存命中与失败状态，不能冻结")
    return summaries


def discover_partitioned(s,api,group):
    """同一预登记查询的时间分箱；触顶递归二分，叶区间不重叠并覆盖[1,T0]。

    正常网页把0用作不筛日期；因此不可用0作为已启用分箱的起点。
    Unix第0秒早于B站存在，不可能对应本研究目标视频。
    """
    s.validate()
    s.assert_mutable()
    contract=s.config["date_partitioning"]
    if contract.get("verified_status")!="passed_positive_and_negative_boundary_checks" or not contract.get("evidence_hashes"):
        raise GateError("日期分箱缺少正反边界验证；不能凭首页日期恰好在范围内认定参数有效")
    if contract.get("begin_param")!="pubtime_begin_s" or contract.get("end_param")!="pubtime_end_s" or not contract.get("evidence"):
        raise GateError("日期分箱契约尚未登记核验")
    prior={"audit_a":"main","audit_b":"audit_a"}.get(group)
    if prior:
        s.frozen("checkpoint_"+prior+".json")
    summaries=[]
    for q in (q for q in s.config["queries"] if q["group"]==group):
        hits,unique,leaves=[],set(),[]
        request_count=0

        def walk(lo,hi,depth=0):
            nonlocal request_count
            if depth>64:
                raise GateError("date_partition_depth_limit")

            def split(reason):
                if lo==hi:
                    raise GateError("date_one_second_still_"+reason)
                mid=(lo+hi)//2
                s.event("search_date_split",query_id=q["id"],begin=lo,end=hi,left_end=mid,right_begin=mid+1,reason=reason)
                walk(lo,mid,depth+1)
                walk(mid+1,hi,depth+1)

            seen_pages,set_in_bin=set(),set()
            expected=None
            for pn in range(1,int(s.config["http"]["max_pages"])+1):
                request_count+=1
                if request_count>int(s.config["http"]["max_pages"]):
                    raise GateError("search_query_request_limit_not_terminal")
                params=dict(search_type="video",keyword=q["keyword"],order=q["order"],page=pn,pubtime_begin_s=lo,pubtime_end_s=hi)
                env=api.get("search",params)
                d=payload(env)
                if not all(k in d for k in ("numPages","numResults")):
                    raise GateError("search_schema_changed")
                n_pages,n_total=int(d["numPages"]),int(d["numResults"])
                # 已核验的正常空区间响应：明确返回两个0计数，但省略result字段。
                # 非零响应仍必须带列表；缺字段不能泛化成零结果或正常终点。
                if "result" not in d and (n_pages,n_total)!=(0,0):
                    raise GateError("search_schema_changed")
                values=d.get("result")
                if values is None and (n_pages,n_total)==(0,0):
                    values=[]
                if not isinstance(values,list) or n_pages<0 or n_total<0:
                    raise GateError("search_schema_changed")
                if expected is not None and expected!=(n_pages,n_total):
                    split("search_totals_changed")
                    return
                expected=(n_pages,n_total)
                page_ids,additions=[],[]
                for rank,item in enumerate(values,1):
                    if item.get("type","video")!="video":
                        continue
                    bv=bvid(item.get("bvid"))
                    pub=int(item.get("pubdate",-1))
                    if not lo<=pub<=hi:
                        raise GateError("date_filter_ignored_or_bad_pubdate")
                    page_ids.append(bv)
                    hits.append(dict(bvid=bv,page=pn,rank=rank,begin=lo,end=hi,depth=depth,duplicate=bv in unique,captured_at=env["captured_at"]))
                    unique.add(bv)
                    additions.append((bv,q["mode"],dict(title=re.sub("<[^>]*>","",item.get("title","")),aid=str(item.get("aid","")),published_at=str(pub))))
                s.candidates(additions)
                signature=tuple(page_ids)
                if signature and (signature in seen_pages or set(page_ids)&set_in_bin):
                    split("search_repeated_or_overlapping_page")
                    return
                seen_pages.add(signature)
                set_in_bin.update(page_ids)
                capped=n_pages>=int(s.config["http"]["search_cap_pages"]) or n_total>=int(contract.get("result_cap",1000))
                s.event("search_date_page",query=q,page=pn,ids=page_ids,begin=lo,end=hi,depth=depth,num_pages=n_pages,num_results=n_total,capped=capped,captured_at=env["captured_at"])
                if capped:
                    split("capped")
                    return
                if pn>=max(1,n_pages):
                    if len(set_in_bin)!=n_total:
                        split("terminal_count_mismatch")
                        return
                    leaves.append(dict(begin=lo,end=hi,status="endpoint_terminal",unique_videos=len(set_in_bin),pages=pn))
                    return
                if not page_ids:
                    raise GateError("search_empty_before_last_page")
            raise GateError("search_safety_page_limit")

        state,reason="incomplete","not_started"
        try:
            publish_start=int(ts(s.config['video_publish_start'])) if s.config.get('video_publish_start') else 1
            walk(publish_start,int(ts(s.config["t0"])))
            ordered=sorted(leaves,key=lambda x:x["begin"])
            if not ordered or ordered[0]["begin"]!=publish_start or ordered[-1]["end"]!=int(ts(s.config["t0"])) or any(a["end"]+1!=b["begin"] for a,b in zip(ordered,ordered[1:])):
                raise GateError("date_partition_gap_or_overlap")
            state,reason="endpoint_terminal","all_registered_date_leaves_enumerated"
        except GateError as e:
            reason=str(e)
        summaries.append(dict(query=q,status=state,reason=reason,unique_videos=len(unique),hits=hits,date_leaves=leaves,requests=request_count))
        write_json(s.path/("discovery_"+group+".json"),dict(config_hash=s.config_hash,queries=summaries,captured_at=now(),contract=contract))
        if reason.startswith(("http_","api_code_","network_","non_json","access_challenge","search_schema_changed","date_filter_ignored")):
            break
    expected=len([q for q in s.config["queries"] if q["group"]==group])
    if len(summaries)!=expected or any(q["status"]!="endpoint_terminal" for q in summaries):
        raise GateError("日期分箱检索未完成；保留失败与分箱日志，不允许冻结")
    return summaries


def enrich(s, api):
    s.assert_mutable()
    rows = read_csv(s.path / "video_review.csv")
    metadata = {}
    for bv in sorted({r["bvid"] for r in rows if r["decision"]!='exclude'}):
        env = api.get("view", {"bvid": bvid(bv)})
        d = payload(env)
        metadata[bv] = dict(bvid=bv, aid=identifier(d.get("aid")), title=d.get("title"), description=d.get("desc"),
                            pubdate=d.get("pubdate"), owner=d.get("owner"), staff=d.get("staff", []), stat=d.get("stat"), captured_at=env["captured_at"])
        for row in (r for r in rows if r["bvid"] == bv):
            # 元数据可刷新；decision/evidence 不由接口自动生成。
            row.update(aid=identifier(d.get("aid")), title=d.get("title", ""), description=d.get("desc", ""),
                       published_at=str(d.get("pubdate", "")), primary_up=identifier((d.get("owner") or {}).get("mid")),
                       coauthors=";".join(identifier(x["mid"]) for x in d.get("staff") or []))
            if row['decision']=='pending' and s.config.get('video_publish_start') and int(row['published_at']) < ts(s.config['video_publish_start']):
                row.update(decision='exclude',reason='早于用户确认的视频发布日期下限',reviewer='deterministic_date_rule_user_confirmed',notes=(row.get('notes','')+'；仅日期规则自动排除，未冒称内容已人工核验').strip('；'))
        write_csv(s.path / "video_review.csv", rows, VIDEO_FIELDS)
        write_json(s.path / "video_metadata.json", metadata)
    return len(metadata)


def rid(r):
    result = identifier(r.get("rpid_str") or r.get("rpid"))
    if r.get("rpid_str") and r.get("rpid") and result != identifier(r["rpid"]):
        raise GateError("comment_id_string_numeric_conflict")
    return result


def normalize(r, bv, root=None, pinned=False):
    i = rid(r)
    rt = identifier(r.get("root_str") or r.get("root", 0), zero=True)
    par = identifier(r.get("parent_str") or r.get("parent", 0), zero=True)
    if root:
        if rt != root or par == "0":
            raise GateError("reply_root_parent_invalid")
    elif rt != "0" or par != "0":
        raise GateError("root_has_nonzero_parent")
    ctime = r.get("ctime")
    if isinstance(ctime, bool) or not isinstance(ctime, int) or ctime <= 0:
        raise GateError("comment_time_missing_or_invalid")
    c = r.get("content") or {}
    text = c.get("message")
    if not isinstance(text, str):
        raise GateError("comment_body_missing")
    media = bool(c.get("pictures") or c.get("attachment"))
    if not text and not media and not c.get("emote"):
        raise GateError("comment_empty_without_media")
    return dict(id=i, bvid=bv, root_id=root or i, parent_id=par, level="reply" if root else "root",
                author_id=r.get("author_id"), ctime=ctime, ctime_bjt=datetime.fromtimestamp(ctime, timezone(timedelta(hours=8))).isoformat(),
                text=text, body_status="saved", edit_time=None, edit_time_reason="not_returned_by_adapter", media=media, emote=bool(c.get("emote")),
                media_readability="pending" if media else "not_applicable", pinned=pinned,
                like=r.get("like"), reply_count=r.get("rcount"), text_hash=hashlib.sha256(text.encode()).hexdigest())


def paged(s, api, route, params, consume, top=False):
    """页码接口：固定 count + 唯一数量核对 + 明确的空末页；预览回复从不作全集。"""
    unique, signatures, pages, totals = set(), set(), [], None
    page_size = 20
    limit = int(s.config["http"]["max_pages"])
    for pn in range(1, limit + 1):
        env = api.get(route, dict(params, pn=pn, ps=page_size))
        d = payload(env)
        page = d.get("page")
        if not isinstance(page, dict) or not all(k in page for k in ("num", "size", "count")):
            raise GateError("page_schema_missing")
        if int(page["num"]) != pn or int(page["size"]) != page_size:
            raise GateError("page_number_or_size_mismatch")
        count = int(page["count"])
        if count < 0 or (totals is not None and count != totals):
            raise GateError("count_changed_during_capture")
        totals = count
        regular = d.get("replies") or []
        if not isinstance(regular, list):
            raise GateError("replies_not_array")
        ids = tuple(rid(r) for r in regular)
        if len(set(ids)) != len(ids) or (ids and ids in signatures):
            raise GateError("duplicate_or_repeated_page")
        signatures.add(ids)
        overlap = set(ids) & unique
        # 跨页重叠可能意味着排序漂移；保留观测，但不声称完整。
        unique.update(ids)
        for rank, r in enumerate(regular, 1):
            consume(r, False, env, pn, rank)
        if top:
            pinned = list((d.get("top") or {}).values()) + (d.get("top_replies") or [])
            for rank, r in enumerate(pinned, 1):
                if isinstance(r, dict) and (r.get("rpid_str") or r.get("rpid")):
                    consume(r, True, env, pn, rank)
        pages.append(dict(pn=pn, ids=list(ids), count=count, acount=page.get("acount"), captured_at=env["captured_at"], response_hash=env["response_hash"]))
        s.event("comment_page", route=route, params=params, **pages[-1])
        if overlap:
            raise GateError("cross_page_overlap_requires_new_capture_version")
        if not regular:
            if len(unique) != count:
                raise GateError(f"terminal_count_mismatch:{len(unique)}!={count}")
            return dict(status="enumerated", normal_end=True, unique_count=len(unique), reported_count=count, pages=pages)
        if pn > math.ceil(count / page_size) + 1:
            raise GateError("unexpected_nonempty_beyond_reported_end")
    raise GateError("safety_page_limit_not_terminal")


def collect_video(s, api, video):
    bv, aid = bvid(video["bvid"]), identifier(video["aid"])
    comments, observations, threads = {}, [], {}
    roles = {api.actor(video["primary_up"]): "uploader"}
    for m in video.get("coauthors", "").split(";"):
        if m and m != video["primary_up"]:
            roles[api.actor(m)] = "coauthor"

    def save(r, pinned, env, pn, rank, root=None):
        row = normalize(r, bv, root, pinned)
        row["author_role"] = roles.get(row["author_id"], "audience" if row["author_id"] else "unknown")
        old = comments.get(row["id"])
        if old:
            if any(old[k] != row[k] for k in ("bvid", "root_id", "parent_id", "ctime", "text", "author_id")):
                raise GateError("comment_changed_during_capture")
            row["pinned"] |= old["pinned"]
            row["first_read_at"] = old["first_read_at"]
        else:
            row["first_read_at"] = env["captured_at"]
        row["last_read_at"] = env["captured_at"]
        comments[row["id"]] = row
        observations.append(dict(id=row["id"], bvid=bv, root_id=root, pinned=pinned, pn=pn, rank=rank, captured_at=env["captured_at"], response_hash=env["response_hash"]))

    status = dict(bvid=bv, status="incomplete", started_at=now(), root_paging=None, threads=threads)
    try:
        status["root_paging"] = api.root_paging(s, aid, save) if hasattr(api,"root_paging") else paged(s, api, "roots", {"type": 1, "oid": aid, "sort": 0}, save, top=True)
        roots = list(comments.values())
        for root in roots:
            # 故意不按日期过滤根；对每个根请求回复页，rcount=0 也核对正常终点。
            i = root["id"]
            if hasattr(api,"root_paging") and root["reply_count"] == 0:
                child_result = dict(status="zero_declared_by_root_response", normal_end=True, unique_count=0, reported_count=0, pages=[])
            else:
                child_result = paged(s, api, "replies", {"type": 1, "oid": aid, "root": i},
                                     lambda r, pin, env, pn, rank: save(r, pin, env, pn, rank, root=i))
            threads[i] = child_result
            if root["reply_count"] is None or int(root["reply_count"]) != child_result["unique_count"]:
                raise GateError("root_rcount_vs_reply_count_mismatch")
        for row in comments.values():
            if row["parent_id"] != "0" and row["parent_id"] not in comments:
                raise GateError("missing_ancestor")
        if "all_count" in status["root_paging"] and len(comments) != status["root_paging"]["all_count"]:
            raise GateError(f"root_plus_reply_count_mismatch:{len(comments)}!={status['root_paging']['all_count']}")
        status["status"] = "enumerated_pending_review"
    except GateError as e:
        status["reason"] = str(e)
    status.update(finished_at=now(), root_count=sum(x["level"] == "root" for x in comments.values()),
                  reply_count=sum(x["level"] == "reply" for x in comments.values()), unique_count=len(comments))
    # acount 语义不自动等同根数。保存全部快照供独立核验。
    if status["root_paging"]:
        status["api_acount_values"] = [p["acount"] for p in status["root_paging"]["pages"]]
    return status, list(comments.values()), observations


def collect(s, api):
    s.validate()
    frame = s.frozen("video_frame.json")
    if (s.path / "comment_frame.json").exists():
        raise GateError("发言清单已冻结；不能覆盖采集")
    videos = {v["bvid"]: v for v in frame["videos"]}
    states, all_comments, all_obs = [], {}, []
    for bv in sorted(videos):
        status, comments, obs = collect_video(s, api, videos[bv])
        states.append(status)
        for row in comments:
            if row["id"] in all_comments and all_comments[row["id"]]["bvid"] != bv:
                raise GateError("相同评论 ID 出现在不同视频")
            all_comments[row["id"]] = row
        all_obs.extend(obs)
        sorted_comments = sorted(all_comments.values(), key=lambda x: x["id"])
        write_json(s.path / "collection.json", dict(config_hash=s.config_hash, video_frame_hash=digest(frame), source_hash=source_hash(),
                   comments_hash=digest(sorted_comments), observations_hash=digest(all_obs), videos=states))
        write_jsonl(s.path / "comments.jsonl", sorted_comments)
        write_jsonl(s.path / "observations.jsonl", all_obs)
        if status.get("reason", "").startswith(("http_", "api_code_", "network_", "non_json", "access_challenge")):
            break
    p = s.path / "collection_review.csv"
    if not p.exists():
        write_csv(p, [dict(bvid=b, status="pending") for b in sorted(videos)], ["bvid", "status", "count_semantics_evidence", "ui_count", "ui_count_scope", "reconciliation", "pagination_evidence", "reviewer"])
    if len(states) != len(videos) or any(x["status"] != "enumerated_pending_review" for x in states):
        raise GateError("采集未通过；保留部分正文、观测与失败日志，不允许冻结统计清单")
    return states
