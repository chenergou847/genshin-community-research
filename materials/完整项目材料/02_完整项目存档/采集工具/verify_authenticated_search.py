"""Small boundary checks with the user-authorized local session; not sampling."""
import json
import os
from pathlib import Path
from observer.core import Study, read_json, write_json, now, digest, ts
from observer.collect import payload, AccessError
from observer.web_api import NormalWebAPI


def main():
    if not os.environ.get('BILI_COOKIE_FILE'):
        raise RuntimeError('user_supplied_cookie_file_required')
    s = Study.init('登录后契约核验_20261017')
    config = read_json('正式采集_v1_20261017/config.json')
    config['revision'] = 'authenticated-contract-probe-not-formal'
    write_json(s.path / 'config.json', config)
    s = Study(s.path)
    result = dict(purpose='CONTRACT_PROBE_NOT_FORMAL_SAMPLE', at=now(), checks=[])
    try:
        api = NormalWebAPI(s)
        def check(label, lo, hi):
            env = api.get('search', dict(search_type='video', keyword='原神 深境螺旋 2026年10月',
                                        order='totalrank', page=1, pubtime_begin_s=lo, pubtime_end_s=hi))
            data = payload(env)
            rows = data.get('result') or []
            dates = [int(r['pubdate']) for r in rows if r.get('type') == 'video' or r.get('bvid')]
            item = dict(label=label, begin=lo, end=hi, numResults=data.get('numResults'),
                        numPages=data.get('numPages'), ids=[r.get('bvid') for r in rows],
                        pubdates=dates, all_in_range=all(lo <= p <= hi for p in dates),
                        response_hash=env['response_hash'])
            result['checks'].append(item)
            write_json(s.path / '日期边界契约.json', result)
            return item
        positive = check('positive_recent_week', 1791648000, int(ts(config['t0'])))
        negative = check('negative_before_bilibili_existed_begin_is_nonzero', 1, 915148799)
        if not positive['pubdates']:
            result['status'] = 'failed_no_positive_results'
        elif not positive['all_in_range'] or negative['numResults'] != 0 or negative['ids']:
            result['status'] = 'failed_date_filter'
        else:
            point = positive['pubdates'][0]
            exact = check('inclusive_single_second', point, point)
            excluded = check('exclude_known_second', point + 1, point + 1)
            known_id = positive['ids'][0]
            passed = (exact['all_in_range'] and known_id in exact['ids'] and
                      excluded['all_in_range'] and known_id not in excluded['ids'])
            result['status'] = 'passed_positive_and_negative_boundary_checks' if passed else 'failed_second_boundary'
        result['evidence_hashes'] = [x['response_hash'] for x in result['checks']]
    except AccessError as exc:
        result['status'] = 'blocked'
        result['reason'] = str(exc)
    write_json(s.path / '日期边界契约.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
