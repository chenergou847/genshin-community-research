from __future__ import annotations

import json
import secrets
from collections import Counter

from .core import (GateError, MODES, SCREEN_FIELDS, digest, identifier, now, permutation,
                   read_csv, read_json, read_jsonl, source_hash, ts, unique_rows, wilson,
                   write_csv, write_json, write_jsonl)


def reviewed_videos(s):
    rows = read_csv(s.path / "video_review.csv")
    unique_rows(rows, ("bvid", "mode"))
    actual_keys = {(r["bvid"], r["mode"]) for r in rows}
    expected_keys = set()
    for path in s.path.glob("discovery_*.json"):
        discovery = read_json(path)
        if discovery["config_hash"] != s.config_hash:
            raise GateError("查询记录来自不同配置")
        for q in discovery["queries"]:
            expected_keys |= {(h["bvid"], q["query"]["mode"]) for h in q["hits"]}
    if (s.path / "events.jsonl").exists():
        for event in read_jsonl(s.path / "events.jsonl"):
            if event["event"] == "candidate_import":
                expected_keys.add((event["bvid"], event["mode"]))
    if not expected_keys.issubset(actual_keys):
        raise GateError("视频审核表删掉了已发现候选；请保留并填写排除理由")
    if not rows:
        raise GateError("候选视频表为空；需要核查真实零结果而非未执行")
    for r in rows:
        if r["mode"] not in MODES or r["decision"] not in ("include", "exclude") or not r["reviewer"] or not r["reason"]:
            raise GateError(f"候选 {r['bvid']} / {r['mode']} 尚未完成人工入排")
        if r["decision"] == "include":
            for key in ("period_evidence", "aid", "primary_up", "published_at", "content_type", "tags"):
                if not r.get(key):
                    raise GateError(f"纳入视频 {r['bvid']} 缺少 {key}")
            identifier(r["aid"])
            identifier(r["primary_up"])
            for uid in r.get("coauthors", "").split(";"):
                if uid:
                    identifier(uid)
            if int(r["published_at"]) > ts(s.config["t0"]):
                raise GateError("视频发布时间晚于 T0")
            if s.config.get('video_publish_start') and int(r['published_at']) < ts(s.config['video_publish_start']):
                raise GateError('视频发布时间早于登记下限')
    return rows


def discovery_complete(s, group):
    obj = s.frozen("discovery_" + group + ".json")
    expected = {q["id"] for q in s.config["queries"] if q["group"] == group}
    actual = {x["query"]["id"] for x in obj["queries"] if x["status"] == "endpoint_terminal"}
    if actual != expected:
        raise GateError(f"{group} 查询没有全部正常结束")
    return obj


def checkpoint(s, group):
    s.validate()
    discovery = discovery_complete(s, group)
    rows = reviewed_videos(s)
    previous = {"audit_a": "main", "audit_b": "audit_a"}.get(group)
    old = set()
    if previous:
        old = {tuple(x) for x in s.frozen("checkpoint_" + previous + ".json")["included_keys"]}
    included = sorted((r["bvid"], r["mode"]) for r in rows if r["decision"] == "include")
    added = [list(x) for x in included if x not in old]
    return s.immutable("checkpoint_" + group + ".json", dict(config_hash=s.config_hash, at=now(), group=group,
                       discovery_hash=digest(discovery), reviews_hash=digest(rows), included_keys=included, new_included=added))


def path_template(s):
    rows = reviewed_videos(s)
    existing = {r["path_id"]: r for r in read_csv(s.path / "paths.csv")}
    for r in (r for r in rows if r["decision"] == "include"):
        items = [("up", r["primary_up"], "https://space.bilibili.com/" + r["primary_up"] + "/upload/video")]
        items += [("tag", t, t) for t in r["tags"].split(";") if t and t != "<none>"]
        for kind, value, locator in items:
            key = kind + ":" + r["mode"] + ":" + value
            existing.setdefault(key, dict(path_id=key, mode=r["mode"], kind=kind, locator=locator, status="pending", evidence="", reviewer=""))
    write_csv(s.path / "paths.csv", sorted(existing.values(), key=lambda x: x["path_id"]), ["path_id", "kind", "mode", "locator", "status", "evidence", "reviewer"])
    return len(existing)


def freeze_videos(s):
    s.validate()
    rows = reviewed_videos(s)
    discovery = {g: discovery_complete(s, g) for g in ("main", "audit_a", "audit_b")}
    checkpoints = {g: s.frozen("checkpoint_" + g + ".json") for g in discovery}
    for g in discovery:
        if checkpoints[g]["discovery_hash"] != digest(discovery[g]):
            raise GateError("检查点后的检索记录被更换；建立新版本，不能覆盖基线")
    path_template(s)
    paths = read_csv(s.path / "paths.csv")
    unique_rows(paths, ("path_id",))
    if any(p["status"] != "complete" or not p["evidence"] or not p["reviewer"] for p in paths):
        raise GateError("标签/UP投稿列表路径尚未核验完整，见 paths.csv；不能只把生成模板算作已执行")
    # 最后审计后的新路径发现也回填；不得删除先前合格来源消除新增。
    included_keys = {(r["bvid"], r["mode"]) for r in rows if r["decision"] == "include"}
    for cp in checkpoints.values():
        if not {tuple(x) for x in cp["included_keys"]}.issubset(included_keys):
            raise GateError("检查点之后排除了合格来源；修订需要新研究版本")
    videos = {}
    for row in (r for r in rows if r["decision"] == "include"):
        if row["bvid"] in videos:
            v = videos[row["bvid"]]
            if any(v[k] != row[k] for k in ("aid", "primary_up", "published_at", "coauthors")):
                raise GateError("同一视频在不同域的元数据冲突")
        else:
            v = dict(row, domains=[])
            videos[row["bvid"]] = v
        v["domains"].append(dict(mode=row["mode"], evidence=row["period_evidence"], reviewer=row["reviewer"], content_type=row["content_type"]))
    if not videos:
        raise GateError("没有已核定的合格视频，不能建立空研究库")
    current = set(included_keys)
    after_b = current - {tuple(x) for x in checkpoints["audit_b"]["included_keys"]}
    added_b = checkpoints["audit_b"]["new_included"]
    return s.immutable("video_frame.json", dict(config_hash=s.config_hash, at=now(), source_hash=source_hash(),
                       discovery_hashes={k: digest(v) for k, v in discovery.items()}, checkpoint_hashes={k: digest(v) for k, v in checkpoints.items()},
                       paths=paths, reviews=rows, videos=sorted(videos.values(), key=lambda x: x["bvid"]),
                       coverage_stable=not added_b and not after_b,
                       coverage_note="仅限预登记路径，不能证明全站覆盖；B组或后续路径仍有新增则稳定性未验证"))


def freeze_comments(s):
    s.validate()
    videos = s.frozen("video_frame.json")
    collection = s.frozen("collection.json")
    if collection["video_frame_hash"] != digest(videos):
        raise GateError("采集使用的视频库哈希不一致")
    statuses = {r["bvid"]: r for r in collection["videos"]}
    if set(statuses) != {v["bvid"] for v in videos["videos"]} or any(r["status"] != "enumerated_pending_review" for r in statuses.values()):
        raise GateError("部分视频/根/回复采集未完成")
    reviews = unique_rows(read_csv(s.path / "collection_review.csv"), ("bvid",))
    for bv in statuses:
        r = reviews.get((bv,), {})
        if r.get("status") != "accepted" or not all(r.get(k) for k in ("count_semantics_evidence", "ui_count_scope", "reconciliation", "pagination_evidence", "reviewer")):
            raise GateError(f"{bv} 需要独立核验数量口径、分页终点及差额；不能只看总数相等")
    rows = read_jsonl(s.path / "comments.jsonl")
    if collection.get("comments_hash") != digest(rows):
        raise GateError("正文与采集时哈希不一致")
    observations = read_jsonl(s.path / "observations.jsonl")
    if collection.get("observations_hash") != digest(observations):
        raise GateError("逐页观测日志与采集时哈希不一致")
    unique_rows(rows, ("id",))
    by_id = {r["id"]: r for r in rows}
    for bv, status in statuses.items():
        actual = [r for r in rows if r["bvid"] == bv]
        if len(actual) != status["unique_count"] or sum(r["level"] == "root" for r in actual) != status["root_count"]:
            raise GateError("正文清单与采集计数不一致")
    domains = {m: [] for m in MODES}
    vm = {v["bvid"]: [d["mode"] for d in v["domains"]] for v in videos["videos"]}
    for r in rows:
        identifier(r["id"])
        if r["bvid"] not in vm:
            raise GateError("评论属于冻结库以外视频")
        if r["parent_id"] != "0":
            seen = {r["id"]}
            parent = r["parent_id"]
            while parent != "0":
                if parent in seen or parent not in by_id or by_id[parent]["bvid"] != r["bvid"]:
                    raise GateError("祖先缺失、跨视频或存在循环")
                seen.add(parent)
                parent = by_id[parent]["parent_id"]
        for m in vm[r["bvid"]]:
            if ts(s.config["periods"][m]["start"]) <= r["ctime"] <= ts(s.config["t0"]):
                domains[m].append(r["id"])
    for m in domains:
        domains[m].sort()
    texts = Counter(r["text_hash"] for r in rows)
    authors = Counter(r["author_id"] for r in rows if r["author_id"])
    domain_sets = {m: set(ids) for m, ids in domains.items()}
    for r in rows:
        r["same_text_count"] = texts[r["text_hash"]]
        r["same_author_count"] = authors[r["author_id"]] if r["author_id"] else None
        r["window_modes"] = [m for m in MODES if r["id"] in domain_sets[m]]
    any_window = set().union(*(set(x) for x in domains.values()))
    context = [r["id"] for r in rows if r["id"] not in any_window]
    # 快照正文直接嵌入冻结文件；后续不依赖可修改的工作表。
    frame = dict(config_hash=s.config_hash, at=now(), video_frame_hash=digest(videos), collection=collection,
                 collection_reviews=list(reviews.values()), comments=rows, domains=domains, context_ids=context,
                 capture_start=min((r["first_read_at"] for r in rows), default=None),
                 capture_end=max((r["last_read_at"] for r in rows), default=None), source_hash=source_hash())
    return s.immutable("comment_frame.json", frame)


def freeze_codebook(s):
    s.frozen("comment_frame.json")
    cb = read_json(s.path / "codebook.json")
    if not all(cb.get(k) for k in ("version", "relevance_rules", "context_rules", "themes", "examples", "reviewer")):
        raise GateError("代码本需含规则、语境、主题定义、入排例子与人工核定人")
    ids = []
    for t in cb["themes"]:
        if not all(t.get(k) for k in ("id", "definition", "include", "exclude")):
            raise GateError("每个主题需有 ID、定义及纳入/排除例子")
        ids.append(t["id"])
    if len(set(ids)) != len(ids) or "other_current_experience" not in ids:
        raise GateError("主题 ID 必须唯一，且保留 other_current_experience 开口类别")
    exploration = cb.get("exploration_review") or {}
    if exploration.get("status") not in ("completed", "limited") or not exploration.get("evidence") or not exploration.get("reviewer"):
        raise GateError("需记录前期探索完成情况；未充分时填 limited 并说明证据与局限")
    if exploration["status"] == "completed" and not all(x["pass_gate"] for x in qualitative_status(s).values()):
        raise GateError("探索尚未通过全部模式验证；不能把 completed 当作人工绕过开关")
    return s.immutable("codebook_frozen.json", dict(config_hash=s.config_hash, at=now(), codebook=cb, source_hash=source_hash()))


def coverage_audit(s):
    cf = s.frozen("comment_frame.json")
    vf = s.frozen("video_frame.json")
    comments = {r["id"]: r for r in cf["comments"]}
    vm = {v["bvid"]: v for v in vf["videos"]}
    groups = {g: [tuple(x) for x in s.frozen("checkpoint_"+g+".json")["new_included"]] for g in ("audit_a", "audit_b")}
    last = {tuple(x) for x in s.frozen("checkpoint_audit_b.json")["included_keys"]}
    groups["post_audit_paths"] = [(v["bvid"], d["mode"]) for v in vf["videos"] for d in v["domains"] if (v["bvid"],d["mode"]) not in last]
    result = {}
    for group, keys in groups.items():
        result[group] = {}
        for m in MODES:
            sources = {bv for bv, mode in keys if mode == m}
            result[group][m] = dict(new_videos=sorted(sources), new_video_n=len(sources),
                 new_up_n=len({vm[b]["primary_up"] for b in sources}),
                 content_types=sorted({d["content_type"] for b in sources for d in vm[b]["domains"] if d["mode"]==m}),
                 difficulty_labels=sorted({vm[b].get("difficulty", "") for b in sources}),
                 window_utterance_n=sum(comments[i]["bvid"] in sources for i in cf["domains"][m]))
    output = dict(config_hash=s.config_hash, at=now(), frame_hash=digest(cf), groups=result,
                  coverage_stable=vf["coverage_stable"], note="只检验预登记路径；窗口发言为实际枚举唯一ID，不是页面全历史总数")
    write_json(s.path/"coverage_audit.json", output)
    return output


def load_draw(s):
    draw = s.frozen("draw.json")
    cf = s.frozen("comment_frame.json")
    cb = s.frozen("codebook_frozen.json")
    if draw["comment_frame_hash"] != digest(cf) or draw["codebook_hash"] != digest(cb):
        raise GateError("抽样框/代码本发生变化，禁止沿用旧抽样")
    for m in MODES:
        for purpose in ("main", "raw_audit"):
            order = permutation(cf["domains"][m], draw["seed"], m + ":" + purpose)
            if purpose == "raw_audit":
                order = order[:200]
            if order != draw["domains"][m][purpose]:
                raise GateError("随机顺序与种子重放不一致")
    return draw, cf, cb


def draw(s):
    s.validate()
    cf = s.frozen("comment_frame.json")
    cb = s.frozen("codebook_frozen.json")
    if (s.path / "draw.json").exists():
        raise GateError("种子已登记；请使用 export，不允许换种子重抽")
    seed = secrets.token_hex(32)
    streams = {}
    for m in MODES:
        ids = cf["domains"][m]
        streams[m] = dict(main=permutation(ids, seed, m + ":main"), raw_audit=permutation(ids, seed, m + ":raw_audit")[:200])
    result = s.immutable("draw.json", dict(config_hash=s.config_hash, at=now(), seed=seed,
                         generator="HMAC-SHA256-counter-rejection-Fisher-Yates-v1", source_hash=source_hash(),
                         comment_frame_hash=digest(cf), codebook_hash=digest(cb), domains=streams))
    all_ids = sorted((m, i) for m in MODES for i in streams[m]["main"])
    write_csv(s.path / "screening.csv", [dict(mode=m, id=i, relevance="pending", final="no") for m, i in all_ids], SCREEN_FIELDS)
    audit_rows = [dict(mode=m, id=i, relevance="pending", final="no") for m in MODES for i in streams[m]["raw_audit"]]
    write_csv(s.path / "raw_audit_review.csv", audit_rows, ["mode", "id", "relevance", "reason", "evidence", "reviewer", "context_status", "role_checked", "date_checked", "final"])
    return result


def screening(s, draw):
    rows = unique_rows(read_csv(s.path / "screening.csv"), ("mode", "id"))
    expected = {(m, i) for m in MODES for i in draw["domains"][m]["main"]}
    if set(rows) != expected:
        raise GateError("screening.csv 增删了框内 ID；不能手工换样本")
    for r in rows.values():
        if r["relevance"] not in ("pending", "related", "irrelevant", "unknown"):
            raise GateError("相关性状态非法")
        if r["final"] == "yes" and (r["relevance"] == "pending" or not all(r.get(k) for k in ("reason", "evidence", "reviewer"))):
            raise GateError("相关性定稿必须保留人工证据及处理人")
    return rows


def main_selection(order, rows, mode):
    selected, scanned = [], []
    for i in order:
        r = rows[(mode, i)]
        if r["final"] != "yes":
            return dict(status="pending_screening", ids=selected, scanned=scanned, next_id=i, census=False)
        scanned.append(dict(id=i, relevance=r["relevance"], reason=r["reason"], evidence=r["evidence"], reviewer=r["reviewer"]))
        if r["relevance"] == "related":
            selected.append(i)
            if len(selected) == 400:
                return dict(status="ready", ids=selected, scanned=scanned, next_id=None, census=len(scanned) == len(order))
    return dict(status="ready", ids=selected, scanned=scanned, next_id=None, census=True)


def export(s):
    d, cf, _ = load_draw(s)
    rows = screening(s, d)
    comments = {r["id"]: r for r in cf["comments"]}
    result = {}
    queue, audit = [], []
    for m in MODES:
        selection = main_selection(d["domains"][m]["main"], rows, m)
        result[m] = selection
        for rank, i in enumerate(d["domains"][m]["main"], 1):
            r = comments[i]
            queue.append(dict(mode=m, id=i, position=rank, bvid=r["bvid"], root_id=r["root_id"], parent_id=r["parent_id"], level=r["level"], text=r["text"], ctime=r["ctime"], selected=i in selection["ids"], **{k: rows[(m, i)].get(k, "") for k in ("relevance", "final")}))
        for rank, i in enumerate(d["domains"][m]["raw_audit"], 1):
            r = comments[i]
            audit.append(dict(mode=m, id=i, position=rank, bvid=r["bvid"], text=r["text"], root_id=r["root_id"], parent_id=r["parent_id"]))
    write_json(s.path / "selection_preview.json", dict(at=now(), domains=result))
    write_csv(s.path / "main_queue.csv", queue, ["mode", "id", "position", "bvid", "root_id", "parent_id", "level", "text", "ctime", "relevance", "final", "selected"])
    write_csv(s.path / "raw_audit_queue.csv", audit, ["mode", "id", "position", "bvid", "root_id", "parent_id", "text"])
    write_jsonl(s.path / "context_lookup.jsonl", cf["comments"])
    return {m: dict(status=r["status"], selected=len(r["ids"]), scanned=len(r["scanned"]), next_id=r["next_id"]) for m, r in result.items()}


def current_selection(s):
    amendments = sorted(s.path.glob("selection_amendment_*.json"))
    return s.frozen(amendments[-1].name if amendments else "selection_frozen.json")


def lock_selection(s, revision_reason=None):
    d, cf, cb = load_draw(s)
    rows = screening(s, d)
    chosen = {m: main_selection(d["domains"][m]["main"], rows, m) for m in MODES}
    themes = {t["id"] for t in cb["codebook"]["themes"]}
    for m in MODES:
        if chosen[m]["status"] != "ready":
            raise GateError(f"{m} 随机顺序尚有待筛项，不能越过后换入别的发言")
        for i in chosen[m]["ids"]:
            r = rows[(m, i)]
            if not r.get("experience_kind") or not r.get("sentiment") or not r.get("context_status"):
                raise GateError("主样本需要人工定稿经历类型、情感、语境状态（没有主题可留空）")
            for field in ("themes", "self_experience_themes"):
                if not set(filter(None, r.get(field, "").split(";"))).issubset(themes):
                    raise GateError("发现冻结代码本以外的新主题：先报告探索并修订验证，不能悄悄加入确认性指标")
            if not set(filter(None, r.get("self_experience_themes", "").split(";"))).issubset(set(filter(None, r.get("themes", "").split(";")))):
                raise GateError("本人经历主题必须同时属于问题提及主题")
    exists = (s.path / "selection_frozen.json").exists()
    if exists and not revision_reason:
        raise GateError("样本已冻结；按固定准则纠错请使用 revise-selection --reason，仍重放原种子和原顺序")
    version = len(list(s.path.glob("selection_amendment_*.json"))) + (2 if exists else 1)
    name = f"selection_amendment_{version:04d}.json" if exists else "selection_frozen.json"
    review_file = f"coding_blind_v{version}.csv"
    result = s.immutable(name, dict(config_hash=s.config_hash, at=now(), draw_hash=digest(d),
                         screening_snapshot=list(rows.values()), domains=chosen, revision_reason=revision_reason,
                         previous_hash=digest(current_selection(s)) if exists else None, review_file=review_file))
    blind = []
    for m in MODES:
        ids = permutation(chosen[m]["ids"], d["seed"], m + ":coding_review")[:100]
        for i in ids:
            blind.append(dict(mode=m, id=i, review_kind="", reviewer="", relevance="", themes="", self_experience_themes="", corrected="", resolution="", final="no"))
    write_csv(s.path / review_file, blind, ["mode", "id", "review_kind", "reviewer", "relevance", "themes", "self_experience_themes", "corrected", "resolution", "final"])
    comments = {r["id"]: r for r in cf["comments"]}
    material = [dict(mode=r["mode"], id=r["id"], bvid=comments[r["id"]]["bvid"], text=comments[r["id"]]["text"], root_id=comments[r["id"]]["root_id"], parent_id=comments[r["id"]]["parent_id"]) for r in blind]
    write_csv(s.path / review_file.replace(".csv", "_material.csv"), material, ["mode", "id", "bvid", "text", "root_id", "parent_id"])
    return result


def qual_init(s):
    cf = s.frozen("comment_frame.json")
    if (s.path / "qual_draw.json").exists():
        q = s.frozen("qual_draw.json")
        if q["comment_frame_hash"] != digest(cf):
            raise GateError("探索框发生变化")
        return q
    q = s.immutable("qual_draw.json", dict(config_hash=s.config_hash, at=now(), seed=secrets.token_hex(32), comment_frame_hash=digest(cf)))
    write_csv(s.path / "qual_screening.csv", [dict(mode=m, id=i, relevance="pending", final="no") for m in MODES for i in cf["domains"][m]], SCREEN_FIELDS)
    write_csv(s.path / "qual_holdout.csv", [], ["mode", "bvid", "reason", "reviewer"])
    return q


def reserve_qual(s):
    qual_init(s)
    used = read_json(s.path / "qual_selections.json") if (s.path / "qual_selections.json").exists() else {}
    vf = s.frozen("video_frame.json")
    vm = {v["bvid"]: v for v in vf["videos"]}
    rows = read_csv(s.path / "qual_holdout.csv")
    unique_rows(rows, ("mode", "bvid"))
    used_ups = {(k.split(":")[0], vm[v["bvid"]]["primary_up"]) for k, v in used.items()}
    for r in rows:
        if r["bvid"] not in vm or not r["reason"] or not r["reviewer"] or (r["mode"], vm[r["bvid"]]["primary_up"]) in used_ups:
            raise GateError("预留来源必须此前未读，且有选择理由")
        if r["mode"] not in {d["mode"] for d in vm[r["bvid"]]["domains"]}:
            raise GateError("验证来源不属于所填模式")
    version = len(list(s.path.glob("qual_reserve_*.json"))) + 1
    return s.immutable(f"qual_reserve_{version:04d}.json", dict(config_hash=s.config_hash, at=now(), sources=rows))


def qual_queue(s, mode, bv, role):
    q = qual_init(s)
    cf = s.frozen("comment_frame.json")
    vf = s.frozen("video_frame.json")
    vm = {v["bvid"]: v for v in vf["videos"]}
    if bv not in vm or mode not in {d["mode"] for d in vm[bv]["domains"]}:
        raise GateError("探索来源不属于冻结域")
    reservations = sorted(s.path.glob("qual_reserve_*.json"))
    if not reservations:
        raise GateError("先登记未读验证来源，再开展探索；来源不足时只能报告未验证")
    reserved = [r for p in reservations for r in s.frozen(p.name)["sources"]]
    reserved_ups = {(r["mode"], vm[r["bvid"]]["primary_up"]) for r in reserved}
    if role == "development" and (mode, vm[bv]["primary_up"]) in reserved_ups:
        raise GateError("预留验证 UP 不能用于开发；若验证失败已转开发，应在日志说明，不再算新来源")
    if role == "validation" and (mode, vm[bv]["primary_up"]) not in reserved_ups:
        raise GateError("验证视频未预留")
    if role == "validation":
        qs = qualitative_status(s)[mode]
        if qs.get("base_ups", 0) < 6 or qs.get("no_addition_batches", 0) < 3 or not {"guide", "record", "discussion"}.issubset(qs.get("content_types", [])):
            raise GateError("基础覆盖和连续三批无新增未完成，不能提前揭开验证来源")
    rows = unique_rows(read_csv(s.path / "qual_screening.csv"), ("mode", "id"))
    comments = {r["id"]: r for r in cf["comments"]}
    ids = [i for i in cf["domains"][mode] if comments[i]["bvid"] == bv]
    order = permutation(ids, q["seed"], mode + ":qual:" + bv)
    chosen, scanned, state = [], [], "ready"
    for i in order:
        r = rows[(mode, i)]
        if r["final"] != "yes":
            state = "pending_screening"
            break
        if r["relevance"] not in ("related", "irrelevant", "unknown") or not all(r.get(k) for k in ("reviewer", "reason", "evidence")):
            raise GateError("探索相关性定稿字段不完整")
        scanned.append(i)
        if r["relevance"] == "related":
            chosen.append(i)
            if len(chosen) == 30:
                break
    p = s.path / "qual_selections.json"
    selections = read_json(p) if p.exists() else {}
    key = mode + ":" + bv
    if key in selections and selections[key]["role"] != role:
        raise GateError("已读开发来源不能改名为未读验证来源")
    selections[key] = dict(mode=mode, bvid=bv, role=role, state=state, ids=chosen, scanned=scanned, at=now(), order_hash=digest(order))
    write_json(p, selections)
    write_csv(s.path / f"qual_queue_{mode}_{bv}.csv", [dict(position=j, id=i, text=comments[i]["text"], root_id=comments[i]["root_id"], parent_id=comments[i]["parent_id"], selected=i in chosen) for j, i in enumerate(order, 1)], ["position", "id", "text", "root_id", "parent_id", "selected"])
    s.event("qual_queue", **selections[key])
    return selections[key]


def qualitative_status(s):
    """检查批次结构；新增信息仍由人判断，不能自动声称主题饱和。"""
    if not (s.path / "qual_selections.json").exists():
        return {m: dict(pass_gate=False, reason="尚未执行探索") for m in MODES}
    vf = s.frozen("video_frame.json")
    vm = {v["bvid"]: v for v in vf["videos"]}
    selections = read_json(s.path / "qual_selections.json")
    batches = read_csv(s.path / "qual_batches.csv")
    result = {}
    for m in MODES:
        used, kinds, base_ups, streak, passed, reason = set(), set(), set(), 0, False, "基础覆盖或验证未完成"
        rows = [r for r in batches if r["mode"] == m]
        for row in rows:
            if row["final"] != "yes" or not row["evidence"] or not row["reviewer"]:
                reason = "批次尚未人工定稿"
                passed = False
                break
            bvs = list(filter(None, row["bvids"].split(";")))
            if not bvs or any(b not in vm for b in bvs):
                raise GateError("主题日志来源非法")
            ups = {vm[b]["primary_up"] for b in bvs}
            role = row["role"]
            expected_role = "validation" if role == "validation" else "development"
            if role not in ("base", "development", "validation", "new_information"):
                raise GateError("主题批次 role 非法")
            if role != "new_information":
                for b in bvs:
                    q = selections.get(m + ":" + b, {})
                    if q.get("state") != "ready" or q.get("role") != expected_role:
                        raise GateError("主题批次缺少完成的随机读取记录")
                if used & ups:
                    raise GateError("重复 UP 不能充作新的开发批或验证来源")
            try:
                addition = sum(int(row[k]) for k in ("new_problem", "new_condition", "new_counterexample"))
                if addition < 0:
                    raise ValueError()
            except ValueError:
                raise GateError("新增信息数量需要非负整数")
            if row["unresolved_gaps"].lower() != "none":
                passed, reason = False, "仍有待核覆盖缺口"
                streak = 0
            if role == "base":
                base_ups |= ups
                kinds |= {vm[b]["content_type"] for b in bvs}
                passed = False
            elif role == "development":
                if len(ups) < 3:
                    raise GateError("每个追加批次至少 3 名新 UP")
                streak = streak + 1 if addition == 0 and row["unresolved_gaps"].lower() == "none" else 0
                passed = False
            elif role == "validation":
                if len(ups) < 3 or len(base_ups) < 6 or streak < 3 or not {"guide", "record", "discussion"}.issubset(kinds):
                    passed, reason = False, "基础类型覆盖/三批无新增/三名未读验证来源未满足"
                elif addition or row["unresolved_gaps"].lower() != "none":
                    passed, reason, streak = False, "验证发现新信息；回到开发并另留未用来源", 0
                else:
                    passed, reason = True, "结构规则通过；主题判断仍需阅读所列证据"
            else:
                passed, reason, streak = False, "主统计或回查出现新信息，充分性需要重新验证", 0
            used |= ups
        result[m] = dict(pass_gate=passed, reason=reason, base_ups=len(base_ups), content_types=sorted(kinds), no_addition_batches=streak)
    return result


def estimates(s, draft=False):
    draw, cf, cb = load_draw(s)
    sel = current_selection(s)
    if sel["draw_hash"] != digest(draw):
        raise GateError("样本冻结记录与随机登记不一致")
    rows = unique_rows(sel["screening_snapshot"], ("mode", "id"))
    live = screening(s, draw)
    if digest(list(live.values())) != digest(sel["screening_snapshot"]):
        raise GateError("筛查/编码表冻结后被修改；先 revise-selection 留下修订与新盲复核记录")
    comments = {r["id"]: r for r in cf["comments"]}
    vm = {v["bvid"]: v for v in s.frozen("video_frame.json")["videos"]}
    audit = unique_rows(read_csv(s.path / "raw_audit_review.csv"), ("mode", "id"))
    audit_expected = {(m, i) for m in MODES for i in draw["domains"][m]["raw_audit"]}
    if set(audit) != audit_expected:
        raise GateError("固定原始审计 ID 被增删")
    blind = unique_rows(read_csv(s.path / sel["review_file"]), ("mode", "id"))
    themes = [x["id"] for x in cb["codebook"]["themes"]]
    qual = qualitative_status(s)
    result, tables = {}, []
    for m in MODES:
        selected = sel["domains"][m]
        ids = selected["ids"]
        n = len(ids)
        expected_blind = set(permutation(ids, draw["seed"], m + ":coding_review")[:100])
        if {i for mode, i in blind if mode == m} != expected_blind:
            raise GateError("盲复核清单偏离登记的随机样本")
        raw = [audit[(m, i)] for i in draw["domains"][m]["raw_audit"]]
        raw_complete = bool(raw) and all(r["final"] == "yes" and r["relevance"] in ("related", "irrelevant", "unknown") and all(r.get(k) for k in ("reviewer", "reason", "evidence", "context_status")) and r.get("role_checked") == "yes" and r.get("date_checked") == "yes" for r in raw)
        unknown = sum(r["relevance"] == "unknown" for r in raw)
        related = sum(r["relevance"] == "related" for r in raw)
        relevant_or_unknown = unknown + related
        interval = wilson(unknown, relevant_or_unknown) if raw_complete else None
        raw_census = len(raw) == len(cf["domains"][m])
        if raw_complete and raw_census and relevant_or_unknown:
            interval = [unknown / relevant_or_unknown] * 2
        uncertainty_upper = unknown / relevant_or_unknown if raw_complete and raw_census and relevant_or_unknown else (interval[1] if interval else None)
        relevance_pass = raw_complete and uncertainty_upper is not None and uncertainty_upper <= .05
        checks, confusion = [], Counter()
        for i in sorted(expected_blind):
            b = blind[(m, i)]
            original = rows[(m, i)]
            complete = b["final"] == "yes" and b["relevance"] == "related" and b["corrected"] in ("yes", "no") and all(b.get(k) for k in ("review_kind", "reviewer", "resolution"))
            equal = complete and all(set(filter(None, b[k].split(";"))) == set(filter(None, original[k].split(";"))) for k in ("themes", "self_experience_themes"))
            checks.append((complete, equal, b["corrected"] == "yes"))
            confusion[(original["themes"], b["themes"])] += 1
        coding_complete = bool(checks) and all(x[0] for x in checks)
        agreement = sum(x[1] for x in checks) / len(checks) if coding_complete else None
        correction_rate = sum(x[2] for x in checks) / len(checks) if coding_complete else None
        coding_pass = coding_complete and agreement >= .9 and correction_rate <= .05
        # 若复核仍有不同主题，必须先裁决并修订全部受影响记录；不能自动拿复核码覆盖。
        unresolved_coding = any(x[0] and not x[1] for x in checks)
        main_precision = n == 400 or selected["census"]
        author_counts = Counter(comments[i]["author_id"] for i in ids)
        up_counts = Counter(vm[comments[i]["bvid"]]["primary_up"] for i in ids)
        thread_counts = Counter(comments[i]["root_id"] for i in ids)
        largest_up = up_counts.most_common(1)[0][0] if up_counts else None
        largest_thread = thread_counts.most_common(1)[0][0] if thread_counts else None
        groups = {"all": ids,
                  "roots": [i for i in ids if comments[i]["level"] == "root"],
                  "replies": [i for i in ids if comments[i]["level"] == "reply"],
                  "exclude_video_authors": [i for i in ids if comments[i]["author_role"] == "audience"],
                  "drop_largest_up": [i for i in ids if vm[comments[i]["bvid"]]["primary_up"] != largest_up],
                  "drop_largest_thread": [i for i in ids if comments[i]["root_id"] != largest_thread]}
        start, end = ts(s.config["periods"][m]["start"]), ts(s.config["t0"])
        for part in range(3):
            groups[f"time_third_{part+1}"] = [i for i in ids if min(2, int((comments[i]["ctime"] - start) / max(1, end - start) * 3)) == part]
        main_ratios, sensitivity_triggers = {}, []
        for metric in ("themes", "self_experience_themes"):
            for theme in themes:
                for group, members in groups.items():
                    count = sum(theme in rows[(m, i)][metric].split(";") for i in members)
                    size = len(members)
                    ratio = count / size if size else None
                    census = selected["census"]
                    ci = ([ratio, ratio] if size else None) if census else wilson(count, size)
                    key = metric + ":" + theme
                    if group == "all":
                        main_ratios[key] = ratio
                    elif ratio is not None and main_ratios.get(key) is not None and abs(ratio - main_ratios[key]) > .05:
                        sensitivity_triggers.append(dict(metric=metric, theme=theme, group=group, change=ratio-main_ratios[key]))
                    tables.append(dict(mode=m, metric=metric, theme=theme, group=group, n=size, count=count, proportion=ratio,
                                       lower=ci[0] if ci else None, upper=ci[1] if ci else None,
                                       interval_method="frozen_domain_census_no_sampling_error" if census else "Wilson_nominal_pointwise_95_large_population_approximation",
                                       precision_note="±5pp仅为各副本主域400条的单项设计目标；子组不保证"))
        result[m] = dict(n=n, census=selected["census"], main_precision_design=main_precision,
                         raw_audit=dict(n=len(raw), completed=raw_complete, unknown=unknown, related=related,
                                        unknown_upper=uncertainty_upper, unknown_interval=interval, census=raw_census,
                                        related_rate=related/len(raw) if raw_complete and raw else None,
                                        related_rate_interval=([related/len(raw)]*2 if raw_census else wilson(related, len(raw))) if raw_complete else None, pass_gate=relevance_pass),
                         coding=dict(n=len(checks), completed=coding_complete, agreement=agreement, correction_rate=correction_rate,
                                     pass_gate=coding_pass and not unresolved_coding,
                                     review_kinds=sorted({blind[(m,i)]["review_kind"] for i in expected_blind}),
                                     confusion=[dict(original=a, review=b, count=c) for (a,b),c in confusion.items()]),
                         concentration=dict(largest_up=largest_up, largest_up_n=max(up_counts.values(), default=0), largest_thread=largest_thread,
                                            largest_thread_n=max(thread_counts.values(), default=0), largest_comment_author_n=max(author_counts.values(), default=0),
                                            root_n=len(groups["roots"]), reply_n=len(groups["replies"])),
                         sensitivity_review_triggers=sensitivity_triggers, qualitative=qual[m],
                         proportion_release_ready=bool(n and main_precision and relevance_pass and coding_pass and not unresolved_coding))
    ready = all(v["proportion_release_ready"] for v in result.values())
    output = dict(at=now(), status="reviewable_results" if ready and not draft else "DRAFT_NOT_VALIDATED", source_hash=source_hash(),
                  config_hash=s.config_hash, draw_hash=digest(draw), selection_hash=digest(sel), domains=result,
                  raw_audit_hash=digest(list(audit.values())), coding_review_hash=digest(list(blind.values())), codebook_hash=digest(cb),
                  coverage_stable=s.frozen("video_frame.json")["coverage_stable"],
                  scope="仅限冻结视频库内、窗口内、可判定本期相关的发言；不是全站或玩家人数。多标签可相加超过100%。")
    name = "estimates" if ready and not draft else "estimates_DRAFT"
    write_json(s.path / (name + ".json"), output)
    write_csv(s.path / (name + ".csv"), tables, ["mode", "metric", "theme", "group", "n", "count", "proportion", "lower", "upper", "interval_method", "precision_note"])
    write_json(s.path / "estimates_current.json", dict(status=output["status"], file=name+".json", hash=digest(output), at=now()))
    if not ready and not draft:
        raise GateError("审计/人工编码等发布门槛未满足；仅生成标明 DRAFT 的结果，详情见 estimates_DRAFT.json")
    return output
