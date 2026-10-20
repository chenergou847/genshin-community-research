"""一次正常公开会话的接口契约核验；不读取浏览器Cookie、不重试风控响应。"""
import hashlib
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from observer.core import Study, now, write_json
from observer.collect import HTTP

TABLE = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]


def main():
    s = Study(Path(sys.argv[1]))
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    result = dict(at=now(), purpose="CONTRACT_PROBE_NOT_FORMAL_SAMPLE", requests=[])
    redactor = HTTP(s)

    def get(path, params=None, allow_nav_public_key=False):
        time.sleep(2)
        url = "https://api.bilibili.com" + path + ("?"+urllib.parse.urlencode(params) if params else "")
        entry = dict(path=path, captured_at=now())
        result["requests"].append(entry)
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0", "Referer":"https://www.bilibili.com/"})
        with opener.open(req, timeout=25) as response:
            body = json.load(response)
        entry["api_code"] = body.get("code")
        if isinstance(body.get("data"),dict) and body["data"].get("v_voucher"):
            raise RuntimeError("access_challenge_voucher_present")
        if body.get("code") != 0 and not (allow_nav_public_key and body.get("code")==-101 and (body.get("data") or {}).get("wbi_img")):
            raise RuntimeError("api_code_"+str(body.get("code")))
        return body.get("data") or {}

    try:
        # 正常匿名会话：首页允许设置的普通会话Cookie仅在内存使用。
        req = urllib.request.Request("https://www.bilibili.com/", headers={"User-Agent":"Mozilla/5.0"})
        with opener.open(req, timeout=25) as response:
            response.read(32*1024*1024)
        nav = get("/x/web-interface/nav", allow_nav_public_key=True)
        pair = nav.get("wbi_img") or {}
        raw = "".join(pair.get(k, "").rsplit("/",1)[-1].split(".")[0] for k in ("img_url","sub_url"))
        if len(raw)!=64:
            raise RuntimeError("normal_public_wbi_key_unavailable")
        key = "".join(raw[i] for i in TABLE)[:32]

        def sign(params):
            p = {k: str(v) for k,v in dict(params,wts=int(time.time())).items()}
            p = {k:"".join(c for c in v if c not in "!'()*") for k,v in p.items()}
            query = urllib.parse.urlencode(sorted(p.items()))
            p["w_rid"] = hashlib.md5((query+key).encode()).hexdigest()
            return p

        view = get("/x/web-interface/wbi/view", sign(dict(bvid=sys.argv[2] if len(sys.argv)>2 else "BV1vSJS6DEEs")))
        result["video"] = {k:view.get(k) for k in ("bvid","aid","title","pubdate","owner","stat")}
        d = get("/x/v2/reply/wbi/main", sign(dict(oid=str(view["aid"]),type=1,mode=2,next=0,ps=20,plat=1,web_location=1315875)))
        minimized = redactor.sanitize("roots",dict(code=0,data=d))
        result["first_comment_page"] = minimized
        result["status"] = "returned_first_page_only_not_completeness_verified"
    except (urllib.error.HTTPError,urllib.error.URLError,ValueError,KeyError,RuntimeError,OSError) as e:
        result["status"] = "blocked"
        result["reason"] = "http_"+str(e.code) if isinstance(e,urllib.error.HTTPError) else str(e)
    bv = sys.argv[2] if len(sys.argv)>2 else "BV1vSJS6DEEs"
    write_json(s.path/("正常公开接口核验_"+bv+".json"),result)
    print(json.dumps({k:v for k,v in result.items() if k not in ("first_comment_page","video")},ensure_ascii=False,indent=2))
    return 0 if result["status"]!="blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
