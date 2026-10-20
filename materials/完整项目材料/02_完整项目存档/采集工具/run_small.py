"""Small-study CLI, deliberately separated from the legacy 400-comment sampler."""
import argparse
import json
from observer.core import Study, GateError, MODES, now, write_json
from observer.web_api import NormalWebAPI
from observer import small


def main(argv=None):
    p=argparse.ArgumentParser(description='有界视频库：20视频×10原始发言/副本，两阶段抽样')
    p.add_argument('--study',required=True)
    sub=p.add_subparsers(dest='command',required=True)
    for c in ('status','freeze-candidates','draw-videos','video-progress','lock-videos','collect','freeze-comments','freeze-codebook','draw-comments','qual-status','probe'):
        sub.add_parser(c)
    q=sub.add_parser('discover');q.add_argument('--group',choices=small.GROUPS,required=True)
    q=sub.add_parser('enrich-next');q.add_argument('--limit',type=int,default=6)
    q=sub.add_parser('lock-coding');q.add_argument('--revision-reason')
    q=sub.add_parser('estimates');q.add_argument('--draft',action='store_true')
    q=sub.add_parser('qual-queue');q.add_argument('--mode',choices=MODES,required=True);q.add_argument('--bvid',required=True);q.add_argument('--role',choices=['development','validation'],required=True)
    args=p.parse_args(argv);s=Study(args.study)
    try:
        small.check(s);c=args.command
        if c=='status':
            result=small.status(s)
        elif c=='probe':
            q=s.config['queries'][0];api=NormalWebAPI(s)
            from observer.collect import payload
            from observer.core import ts
            env=api.get('search',dict(search_type='video',keyword=q['keyword'],order=q['order'],page=1,page_size=20,
                 pubtime_begin_s=int(ts(s.config['video_publish_start'])),pubtime_end_s=int(ts(s.config['t0']))))
            data=payload(env)
            result=dict(purpose='ONE_PAGE_ACCESS_PROBE_NOT_FORMAL_SAMPLE',api_returned=True,returned=len(data.get('result') or []),response_hash=env['response_hash'])
            write_json(s.path/'small_access_probe.json',dict(at=now(),**result))
        elif c=='discover':result=small.discover(s,NormalWebAPI(s),args.group)
        elif c=='freeze-candidates':result=small.freeze_candidates(s)
        elif c=='draw-videos':result=small.draw_videos(s)
        elif c=='video-progress':
            progress=small.video_progress(s);result={m:{k:(len(v) if k in ('selected','prefix') else v) for k,v in x.items()} for m,x in progress.items()}
        elif c=='enrich-next':result={'fetched':small.enrich_next(s,NormalWebAPI(s),args.limit)}
        elif c=='lock-videos':result=small.lock_videos(s)
        elif c=='collect':result={'videos':len(small.collect_selected(s,NormalWebAPI(s)))}
        elif c=='freeze-comments':result=small.freeze_comments(s)
        elif c=='freeze-codebook':result=small.freeze_codebook(s)
        elif c=='draw-comments':result=small.draw_comments(s)
        elif c=='lock-coding':result=small.lock_coding(s,args.revision_reason)
        elif c=='qual-queue':result=small.qual_queue(s,args.mode,args.bvid,args.role)
        elif c=='qual-status':result=small.qual_status(s)
        else:result=small.estimates(s,args.draft)
        # Never print study seeds, comment bodies, user IDs or full raw responses.
        print(json.dumps({'status':'OK','command':c,'summary':result if c in ('status','video-progress','enrich-next','probe','lock-coding') else 'saved_to_study_files'},ensure_ascii=False))
        return 0
    except (GateError,FileNotFoundError) as exc:
        reason=str(exc) if isinstance(exc,GateError) else 'required_stage_file_missing'
        write_json(s.path/'small_last_command.json',dict(at=now(),command=args.command,status='STOPPED',reason=reason))
        print(json.dumps({'status':'STOPPED','reason':reason},ensure_ascii=False));return 2


if __name__=='__main__':
    raise SystemExit(main())
