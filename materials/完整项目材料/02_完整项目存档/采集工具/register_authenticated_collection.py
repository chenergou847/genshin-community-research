"""Register the genuinely verified date contract. Preserve failed v1/v2 histories."""
import argparse
from observer.core import Study, VIDEO_FIELDS, digest, now, read_csv, read_json, write_csv, write_json, ts


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--study',default='正式采集_v3_20261017')
    parser.add_argument('--revision',default='3-authenticated-nonzero-date-boundaries')
    parser.add_argument('--candidates',default='正式采集_v2_20261017/video_review.csv')
    parser.add_argument('--video-publish-start')
    args=parser.parse_args()
    parent = Study('正式采集_v1_20261017')
    registration = parent.frozen('registration.json')
    evidence = read_json('登录后契约核验_20261017/日期边界契约.json')
    if evidence.get('status') != 'passed_positive_and_negative_boundary_checks':
        raise RuntimeError('日期正反边界核验未通过')
    s = Study.init(args.study)
    c = parent.config
    c['revision'] = args.revision
    if args.video_publish_start:
        c['video_publish_start']=args.video_publish_start
        c['video_discovery_scope']=dict(confirmed_by='user',confirmation='用户在本会话选择统一从2026年9月1日起；本期内容核验和三个副本评论窗口及T0不变',publication_begin=args.video_publish_start,publication_end=c['t0'],inference_boundary='仅限这段视频发布期按登记路径建立的合格视频库')
    c['date_partitioning'] = dict(
        begin_param='pubtime_begin_s', end_param='pubtime_end_s', result_cap=1000,
        verified_status=evidence['status'], evidence_hashes=evidence['evidence_hashes'],
        evidence='../登录后契约核验_20261017/日期边界契约.json；正常搜索前端对0使用未启用日期筛选语义，改从Unix秒1开始；实际核验包含近期正例、B站存在前负例、单秒包含与相邻秒排除',
        algorithm='同一预登记查询从[video_publish_start或Unix秒1,T0]开始；触及1000结果或50页上限、分页重叠/重复、总数漂移或末页唯一数不一致时，在整数秒中点二分；子区间[lo,mid]与[mid+1,hi]；只有完整且计数一致的叶区间可结束；单秒仍异常、日期越界、缺页/访问失败或请求上限均失败；保留所有父区间命中与拆分原因',
        amendment_reason='修正Unix秒0作为未启用筛选标记造成的分箱失效；研究窗口、关键词、相关性规则和样本目标不变；用户正常扫码登录会话仅用于B站读取请求')
    write_json(s.path / 'config.json', c)
    s = Study(s.path)
    s.validate()
    s.import_candidates(args.candidates, path_id='legacy-and-prior-known-candidates')
    if args.video_publish_start:
        rows=read_csv(s.path/'video_review.csv')
        excluded=0
        for r in rows:
            if r['published_at'].isdigit() and int(r['published_at']) < ts(args.video_publish_start):
                r.update(decision='exclude',reason='早于用户确认的2026-09-01视频发布下限',reviewer='deterministic_date_rule_user_confirmed',notes='旧候选保留；按明确发布日期规则排除，不冒称已核验视频内容')
                excluded+=1
        write_csv(s.path/'video_review.csv',rows,VIDEO_FIELDS)
        s.event('registered_video_publication_boundary',begin=args.video_publish_start,automatically_excluded_rows=excluded)
    s.immutable('registration.json', dict(
        config_hash=s.config_hash, registered_at=now(), t0=c['t0'],
        parent_registration_hash=digest(registration), periods=c['periods'],
        date_partitioning=c['date_partitioning'], queries_hash=digest(c['queries']),
        targets=c['targets'], video_publication_scope=c.get('video_discovery_scope'),purpose='按用户确认的视频发布范围和修复后的日期边界重新建库；旧失败版本保留；未冻结视频库，未抽样'))
    print(str(s.path))


if __name__ == '__main__':
    main()
