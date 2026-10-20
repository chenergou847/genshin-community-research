from __future__ import annotations

import csv
import hashlib
import hmac
import json
import math
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path


class GateError(Exception):
    """未满足研究门槛；CLI 返回非零退出码。"""


MODES = ("abyss", "theater", "stygian")
NAMES = dict(zip(MODES, ("深境螺旋", "幻想真境剧诗", "幽境危战")))
MAIN = [
    ["原神 深境螺旋 2026年10月", "原神 7.1 深渊", "原神 10月16 深渊 攻略", "原神 10月16 深渊 实录", "原神 7.1 深渊 体验", "原神 7.1 深渊 讨论"],
    ["原神 幻想真境剧诗 2026年10月", "原神 7.1 剧诗", "原神 10月 剧诗 攻略", "原神 10月 剧诗 实录", "原神 10月 剧诗 体验", "原神 10月 剧诗 讨论"],
    ["原神 幽境危战 7.1", "原神 幽境危战 2026年9月", "原神 7.1 幽境危战 攻略", "原神 7.1 幽境危战 实录", "原神 7.1 幽境危战 体验", "原神 7.1 幽境危战 联机"],
]
AUDIT_A = [["原神 老深渊 202610", "原神 十月 螺旋 十二层"], ["原神 十月 水冰风 月谕", "原神 十月 圣牌挑战"], ["原神 7.1 危战 绝境", "原神 7.1 幽境 N5"]]
AUDIT_B = [["原神 7.1 深境 满星", "原神 2026年10月 深渊 通关"], ["原神 2026年10月 新深渊", "原神 十月 剧诗 困难"], ["原神 7.1 危战 N4", "原神 7.1 危战 配队"]]
VIDEO_FIELDS = ["bvid", "mode", "decision", "reason", "period_evidence", "reviewer", "aid", "published_at", "primary_up", "coauthors", "title", "description", "tags", "content_type", "relations", "difficulty", "config_evidence", "outcome", "notes"]
SCREEN_FIELDS = ["mode", "id", "relevance", "reason", "evidence", "reviewer", "final", "themes", "self_experience_themes", "experience_kind", "difficulty", "conditions", "action", "outcome", "sentiment", "context_status", "notes"]


def now():
    return datetime.now(timezone.utc).isoformat()


def ts(s):
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            raise ValueError()
        return d.timestamp()
    except (TypeError, ValueError):
        raise GateError(f"需要带时区的 ISO 时刻，收到：{s!r}")


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def read_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def write_json(p, obj, exclusive=False):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(obj, ensure_ascii=False, indent=2)
    if exclusive:
        with p.open("x", encoding="utf-8") as f:
            f.write(body)
    else:
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, p)


def read_csv(p):
    p = Path(p)
    if not p.exists():
        return []
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(p, rows, fields):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            # 可直接在表格软件打开；防止原文被解释成公式。JSONL 保留原文。
            w.writerow({k: ("'" + str(v) if str(v).startswith(("=", "+", "-", "@")) else v) for k, v in row.items()})


def write_jsonl(p, rows):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(p):
    with Path(p).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def identifier(value, zero=False):
    if isinstance(value, bool) or isinstance(value, float):
        raise GateError("ID 不接受浮点数/布尔值（可能已损失精度）")
    value = str(value)
    if not re.fullmatch(r"[0-9]+", value) or (int(value) == 0 and not zero):
        raise GateError(f"平台 ID 缺失或非法：{value!r}")
    return value


def bvid(value):
    if not re.fullmatch(r"BV[0-9A-Za-z]{10}", str(value)):
        raise GateError(f"BVID 非法：{value!r}")
    return value


def source_hash():
    return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))})


def template():
    queries = []
    for group, lists in (("main", MAIN), ("audit_a", AUDIT_A), ("audit_b", AUDIT_B)):
        for mode, words in zip(MODES, lists):
            for i, word in enumerate(words, 1):
                for order in ("totalrank", "pubdate", "click"):
                    queries.append(dict(id=f"{group}-{mode}-{i}-{order}", group=group, mode=mode, keyword=word, order=order, date_params={}))
    return dict(protocol="12-v1", revision="1", timezone="Asia/Shanghai", t0=None,
                confirmed_by=None, confirmation_record=None,
                periods={m: dict(period_id=None, start=None, characteristics=None, evidence=None, verified_by=None) for m in MODES},
                targets=dict(main=400, raw_audit=200, coding_review=100),
                http=dict(delay_seconds=2.0, retries=2, timeout_seconds=25, max_pages=5000, search_cap_pages=50),
                queries=queries)


class Study:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.config = read_json(self.path / "config.json")
        self.config_hash = digest(self.config)

    @classmethod
    def init(cls, path):
        p = Path(path).resolve()
        p.mkdir(parents=True, exist_ok=False)
        write_json(p / "config.json", template(), exclusive=True)
        write_json(p / ".private.json", {"author_hmac_key": secrets.token_hex(32)}, exclusive=True)
        (p / ".gitignore").write_text(".private.json\ncache/\nhttp.jsonl\n", encoding="utf-8")
        write_csv(p / "video_review.csv", [], VIDEO_FIELDS)
        write_csv(p / "paths.csv", [], ["path_id", "kind", "mode", "locator", "status", "evidence", "reviewer"])
        write_json(p / "codebook.json", {"version": None, "relevance_rules": None, "context_rules": None, "themes": [], "examples": None, "reviewer": None})
        write_csv(p / "qual_batches.csv", [], ["mode", "batch", "role", "bvids", "new_problem", "new_condition", "new_counterexample", "unresolved_gaps", "evidence", "reviewer", "final"])
        return cls(p)

    def validate(self):
        c = self.config
        expected = {"videos":20,"comments_per_video":10,"coding_review":30} if c.get('protocol')=='17-small-v1' else {"main":400,"raw_audit":200,"coding_review":100}
        if c.get("timezone") != "Asia/Shanghai" or c.get("targets") != expected:
            raise GateError("时区或样本目标与登记方案不一致；变更需新方案")
        if c.get('protocol')=='17-small-v1':
            if c.get('bounded_search')!={'main':3,'audit_a':1,'audit_b':1,'page_size':20} or c.get('date_partitioning'):
                raise GateError('小样本版固定检索深度，不使用递归日期分箱')
        end = ts(c.get("t0"))
        if end > datetime.now(timezone.utc).timestamp():
            raise GateError("T0 必须是已到达的固定时刻")
        if c.get("video_publish_start") and not 1 <= ts(c["video_publish_start"]) <= end:
            raise GateError("视频发布日期下限必须是Unix秒1之后且不晚于T0")
        if not c.get("confirmed_by") or not c.get("confirmation_record"):
            raise GateError("缺少方案确认记录")
        for m in MODES:
            p = c["periods"][m]
            if not all(p.get(k) for k in ("period_id", "start", "characteristics", "evidence", "verified_by")):
                raise GateError(f"{m} 期次卡未核定")
            if ts(p["start"]) > end:
                raise GateError(f"{m} 开放时刻晚于 T0")
        q = c["queries"]
        if len({x["id"] for x in q}) != len(q):
            raise GateError("查询 ID 重复")
        # 原 90 个组合不可被悄悄删掉；允许登记额外日期分箱/新查询。
        required = {(x["group"], x["mode"], x["keyword"], x["order"]) for x in template()["queries"]}
        if not required.issubset({(x["group"], x["mode"], x["keyword"], x["order"]) for x in q}):
            raise GateError("预登记的主/封存审计查询缺失")
        return True

    def event(self, name, **data):
        with (self.path / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({**data, "at": now(), "event": name}, ensure_ascii=False) + "\n")

    def immutable(self, name, obj):
        write_json(self.path / name, obj, exclusive=True)
        with (self.path / (name + ".sha256")).open("x", encoding="ascii") as f:
            f.write(digest(obj))
        self.event("freeze", file=name, sha256=digest(obj))
        return obj

    def frozen(self, name):
        obj = read_json(self.path / name)
        if name not in ("collection.json",) and not name.startswith("discovery_"):
            seal = self.path / (name + ".sha256")
            if not seal.exists() or seal.read_text(encoding="ascii").strip() != digest(obj):
                raise GateError(f"{name} 缺少冻结校验或已被改写")
        if obj["config_hash"] != self.config_hash:
            raise GateError(f"配置与 {name} 冻结时不同；请建立新研究目录，不覆盖旧版本")
        return obj

    def assert_mutable(self):
        if (self.path / "video_frame.json").exists():
            raise GateError("视频库已冻结；新增/修改来源必须建立新版本目录")

    def candidate(self, bv, mode, metadata=None):
        self.candidates([(bv,mode,metadata or {})])

    def candidates(self, additions):
        rows = read_csv(self.path / "video_review.csv")
        mapping = {(r["bvid"],r["mode"]):r for r in rows}
        for bv,mode,metadata in additions:
            row = mapping.get((bv,mode))
            if not row:
                row = dict.fromkeys(VIDEO_FIELDS, "")
                row.update(bvid=bvid(bv), mode=mode, decision="pending")
                rows.append(row)
                mapping[(bv,mode)] = row
            for k, v in metadata.items():
                if k in VIDEO_FIELDS and not row.get(k):
                    row[k] = v
        write_csv(self.path / "video_review.csv", rows, VIDEO_FIELDS)

    def import_candidates(self, file, mode=None, path_id="legacy"):
        self.assert_mutable()
        for r in read_csv(file):
            m = mode or next((k for k, v in NAMES.items() if r.get("副本") == v), r.get("mode"))
            if m not in MODES:
                raise GateError("候选 CSV 需要 mode 或可识别的副本列")
            bv = bvid(r.get("bvid"))
            # 复用已观测元数据，入排结论与人工判断仍重置为pending。
            metadata={k:r.get(k,"") for k in ("aid","published_at","primary_up","coauthors","description","tags")}
            metadata['title']=r.get("title",r.get("标题",""))
            self.candidate(bv, m, metadata)
            self.event("candidate_import", bvid=bv, mode=m, path_id=path_id)


def unique_rows(rows, keys):
    out = {}
    for r in rows:
        k = tuple(r[x] for x in keys)
        if k in out:
            raise GateError(f"审核表重复主键：{k}")
        out[k] = r
    return out


def wilson(k, n):
    if n <= 0:
        return None
    z = 1.959963984540054
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0., center - half), min(1., center + half)]


def permutation(ids, seed, stream):
    """SHA-256 计数流 + 拒绝取模 + Fisher-Yates；不依赖 Python random 版本。"""
    values = sorted(set(ids))
    if len(values) != len(ids):
        raise GateError("随机框中有重复 ID")
    key = bytes.fromhex(seed)
    counter = 0
    for i in range(len(values) - 1, 0, -1):
        bound = i + 1
        limit = (1 << 256) - ((1 << 256) % bound)
        while True:
            block = hmac.new(key, stream.encode() + b"\0" + counter.to_bytes(16, "big"), hashlib.sha256).digest()
            counter += 1
            x = int.from_bytes(block, "big")
            if x < limit:
                j = x % bound
                break
        values[i], values[j] = values[j], values[i]
    return values
