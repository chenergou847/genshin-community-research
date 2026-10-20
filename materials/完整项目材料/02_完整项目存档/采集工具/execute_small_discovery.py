"""Execute only the preregistered finite discovery budget, stopping on failure."""
from observer.core import Study,GateError,now,write_json
from observer.web_api import NormalWebAPI
from observer import small


def main():
    s=Study('正式采集_小样本v1_20261018')
    try:
        small.check(s)
        if (s.path/'small_candidate_frame.json').exists() and (s.path/'small_video_draw.json').exists():
            print({'status':'already_frozen_no_network_request'});return 0
        api=NormalWebAPI(s)
        for group in small.GROUPS:
            name='small_discovery_'+group+'.json'
            if (s.path/name).exists():s.frozen(name)
            else:small.discover(s,api,group)
        if not (s.path/'small_candidate_frame.json').exists():small.freeze_candidates(s)
        if not (s.path/'small_video_draw.json').exists():small.draw_videos(s)
        result=dict(at=now(),status='candidate_frame_and_random_video_queue_ready',**small.status(s))
        write_json(s.path/'执行状态.json',result)
        print({'status':result['status'],'candidates':result['different_candidate_videos'],'candidate_domain_rows':result['candidate_video_domain_rows']})
        return 0
    except GateError as exc:
        write_json(s.path/'执行状态.json',dict(at=now(),status='STOPPED',reason=str(exc),**small.status(s)))
        print({'status':'STOPPED','reason':str(exc)});return 2


if __name__=='__main__':raise SystemExit(main())
