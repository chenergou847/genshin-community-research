from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import GateError, MODES, Study, digest, now, read_json, write_json
from .collect import HTTP, collect, collect_video, discover, enrich, payload
from .web_api import NormalWebAPI
from .research import (checkpoint, coverage_audit, draw, estimates, export, freeze_codebook,
                       freeze_comments, freeze_videos, lock_selection, path_template,
                       qual_init, qual_queue, qualitative_status, reserve_qual)


def parser():
    p = argparse.ArgumentParser(description="本期B站观察：只读采集、完整性门槛与双轨抽样")
    p.add_argument("--study", required=True, type=Path, help="独立研究目录；正式与试跑分开")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("init", "validate", "enrich", "paths-template", "freeze-videos", "collect", "freeze-comments", "coverage-audit", "qual-init", "qual-reserve", "qual-status", "freeze-codebook", "draw", "export", "lock-selection", "status"):
        sub.add_parser(name)
    imp = sub.add_parser("import-candidates")
    imp.add_argument("--file", required=True, type=Path)
    imp.add_argument("--mode", choices=MODES)
    imp.add_argument("--path-id", default="legacy")
    for name in ("discover", "checkpoint"):
        q = sub.add_parser(name)
        q.add_argument("--group", choices=("main", "audit_a", "audit_b"), required=True)
    q = sub.add_parser("qual-queue")
    q.add_argument("--mode", choices=MODES, required=True)
    q.add_argument("--bvid", required=True)
    q.add_argument("--role", choices=("development", "validation"), required=True)
    q = sub.add_parser("revise-selection")
    q.add_argument("--reason", required=True)
    q = sub.add_parser("estimates")
    q.add_argument("--draft", action="store_true")
    q = sub.add_parser("smoke")
    q.add_argument("--bvid", required=True)
    return p


def status(s):
    names = ["discovery_main.json", "checkpoint_main.json", "discovery_audit_a.json", "checkpoint_audit_a.json", "discovery_audit_b.json", "checkpoint_audit_b.json", "video_frame.json", "collection.json", "comment_frame.json", "qual_draw.json", "codebook_frozen.json", "draw.json", "selection_frozen.json", "estimates.json"]
    try:
        s.validate()
        config_status = "verified"
    except GateError as e:
        config_status = "not_verified: " + str(e)
    return dict(at=now(), config_hash=s.config_hash, period_and_t0=config_status, files={n: {"exists": (s.path/n).exists(), "hash": digest(read_json(s.path/n)) if (s.path/n).exists() else None} for n in names},
                note="文件存在不代表验证通过；查看每项状态。smoke 不是正式样本。")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            s = Study.init(args.study)
            result = dict(study=str(s.path), status="created_unverified", message="先填期次卡、共同T0与确认记录；候选不自动纳入")
        else:
            s = Study(args.study)
            if s.config.get('protocol')=='17-small-v1':
                raise GateError('小样本研究必须使用run_small.py，不能沿用400条旧抽样命令')
            def api():
                return NormalWebAPI(s) if s.config.get("adapter")=="web_wbi_v1" else HTTP(s)
            cmd = args.command
            if cmd == "validate":
                result = dict(valid=s.validate())
            elif cmd == "import-candidates":
                s.import_candidates(args.file, args.mode, args.path_id)
                result = dict(status="imported_as_pending")
            elif cmd == "discover":
                s.validate()
                contract=s.config.get("date_partitioning")
                if contract and (contract.get("verified_status")!="passed_positive_and_negative_boundary_checks" or not contract.get("evidence_hashes")):
                    raise GateError("日期分箱正反边界验证未通过；不启动网络请求，需修订契约后建立新研究版本")
                result = dict(combinations=len(discover(s, api(), args.group)))
            elif cmd == "enrich":
                result = dict(videos=enrich(s, api()))
            elif cmd == "checkpoint":
                cp = checkpoint(s, args.group)
                result = dict(status="checkpointed", included=len(cp["included_keys"]), added=len(cp["new_included"]))
            elif cmd == "paths-template":
                result = dict(paths=path_template(s))
            elif cmd == "freeze-videos":
                frame = freeze_videos(s)
                result = dict(videos=len(frame["videos"]), coverage_stable=frame["coverage_stable"])
            elif cmd == "collect":
                result = dict(enumerated_videos=len(collect(s, api())), status="pending_independent_review")
            elif cmd == "freeze-comments":
                frame = freeze_comments(s)
                result = dict(domains={m: len(v) for m, v in frame["domains"].items()}, context=len(frame["context_ids"]))
            elif cmd == "coverage-audit":
                result = coverage_audit(s)
            elif cmd == "freeze-codebook":
                result = dict(hash=digest(freeze_codebook(s)))
            elif cmd == "draw":
                result = dict(hash=digest(draw(s)), status="seed_registered_once")
            elif cmd == "export":
                result = export(s)
            elif cmd == "lock-selection":
                result = dict(hash=digest(lock_selection(s)))
            elif cmd == "revise-selection":
                result = dict(hash=digest(lock_selection(s, args.reason)))
            elif cmd == "qual-init":
                result = dict(hash=digest(qual_init(s)))
            elif cmd == "qual-reserve":
                result = dict(hash=digest(reserve_qual(s)))
            elif cmd == "qual-queue":
                result = qual_queue(s, args.mode, args.bvid, args.role)
            elif cmd == "qual-status":
                result = qualitative_status(s)
            elif cmd == "estimates":
                write_json(s.path / "estimates_current.json", dict(status="PENDING_REVALIDATION", at=now()))
                est = estimates(s, args.draft)
                result = dict(status=est["status"], domains={m: r["proportion_release_ready"] for m, r in est["domains"].items()})
            elif cmd == "status":
                result = status(s)
            elif cmd == "smoke":
                # 不读取正式期次和 T0，也不写入正式帧；专门隔离接口连通/结构验证。
                if (s.path / "video_frame.json").exists():
                    raise GateError("smoke 请使用独立试跑目录，不能污染已冻结研究缓存")
                client = api()
                try:
                    env = client.get("view", {"bvid": args.bvid})
                    d = payload(env)
                    video = dict(bvid=args.bvid, aid=d.get("aid"), primary_up=str((d.get("owner") or {}).get("mid")), coauthors=";".join(str(x["mid"]) for x in d.get("staff") or []))
                    state, comments, observations = collect_video(s, client, video)
                    result = dict(at=now(), purpose="SMOKE_ONLY_NOT_SAMPLE", metadata=d, collection=state, comments=comments, observations=observations)
                    write_json(s.path / "smoke.json", result)
                    if state["status"] != "enumerated_pending_review":
                        raise GateError("smoke 未能枚举完整，见 smoke.json")
                    result = dict(status="smoke_enumerated_needs_ui_contract_review", comments=len(comments))
                except GateError as e:
                    if str(e) != "smoke 未能枚举完整，见 smoke.json":
                        write_json(s.path / "smoke.json", dict(at=now(), purpose="SMOKE_ONLY_NOT_SAMPLE", status="blocked", reason=str(e)))
                    raise
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (GateError, OSError, ValueError, KeyError, TypeError) as e:
        # 不输出带认证头的异常/完整 URL；需要细查时看经过清理的 events.jsonl。
        print(json.dumps(dict(status="STOPPED", error=str(e), error_type=type(e).__name__), ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("已中断；成功响应已缓存。相同配置重跑可恢复，未标记完整。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
