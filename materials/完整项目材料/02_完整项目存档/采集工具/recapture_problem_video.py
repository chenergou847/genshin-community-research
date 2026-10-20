"""A new capture of the same locked source; old caches are immutable."""
from observer.core import Study, digest, now, write_json
from observer.collect import collect_video
from observer.web_api import NormalWebAPI
from observer import small


def main():
    s = Study('正式采集_小样本v1_20261018')
    final_name = 'small_repair_004_recapture.json'
    if (s.path / final_name).exists():
        result = s.frozen(final_name)
        print({'already_saved': result['status']['status']}, flush=True)
        return
    selection = s.frozen('small_video_selection.json')
    video = next(v for v in selection['videos'] if v['bvid'] == 'BV1AQJU6hE93')
    small.seal(s, 'small_repair_004_registration.json', dict(
        selection_hash=digest(selection), bvid=video['bvid'], capture_namespace='repair_004_full',
        purpose='Fresh complete enumeration of the same video; all original snapshots retained. No promotion or frame freeze.')) if not (s.path / 'small_repair_004_registration.json').exists() else s.frozen('small_repair_004_registration.json')
    write_json(s.path / 'small_repair_004_progress.json', dict(stage='running', at=now(), bvid=video['bvid']))
    api = NormalWebAPI(s, capture_namespace='repair_004_full')
    status, rows, observations = collect_video(s, api, video)
    small.seal(s, final_name, dict(selection_hash=digest(selection), status=status, comments=rows,
                                  observations=observations, capture_namespace='repair_004_full'))
    write_json(s.path / 'small_repair_004_progress.json', dict(stage=status['status'], reason=status.get('reason'),
                                                            unique_count=len(rows), at=now()))
    print({k: status.get(k) for k in ('bvid', 'status', 'reason', 'unique_count', 'root_count', 'reply_count')}, flush=True)


if __name__ == '__main__':
    main()
