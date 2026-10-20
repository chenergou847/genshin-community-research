"""Create a new preregistration; preserves all previous studies unchanged."""
from observer.core import Study, digest, now, read_json, write_json
from observer.small import PROTOCOL


def main():
    parent=Study('正式采集_v6_20261017')
    s=Study.init('正式采集_小样本v1_20261018')
    c=parent.config
    c.pop('date_partitioning',None)
    c.update(protocol=PROTOCOL,revision='1-user-confirmed-20-videos-10-raw-utterances',
             targets=dict(videos=20,comments_per_video=10,coding_review=30),
             bounded_search=dict(main=3,audit_a=1,audit_b=1,page_size=20),
             precision=dict(confidence=.95,target_margin=.10,guaranteed=False),
             confirmation_record='2026-10-18用户确认：缩减全流程；目标95%±10pp；固定关键词×三排序最多前3页；每副本随机20合格视频×最多10原始窗口发言；加权并按视频聚类估计；另留定向补查')
    c['http']['delay_seconds']=3.0
    c['discovery_scope']='新有界主/A/B请求返回并集；旧v1—v6候选保留作外部遗漏线索，不自动混入新抽样框；未完整执行的页不视为有界范围完成'
    write_json(s.path/'config.json',c);s=Study(s.path);s.validate()
    s.immutable('registration.json',dict(config_hash=s.config_hash,at=now(),parent_config_hash=parent.config_hash,
                targets=c['targets'],bounded_search=c['bounded_search'],precision=c['precision'],
                video_publish_start=c['video_publish_start'],t0=c['t0'],periods=c['periods'],queries_hash=digest(c['queries']),
                qualitative_budget=dict(development_videos=6,validation_videos=3,raw_comments_per_video=10),
                note='目标总量至多600条原始发言，不保证600条相关或独立玩家；旧主题饱和门槛不冒称已通过'))
    cb=read_json(s.path/'codebook.json');cb['exploration_review']=dict(status='limited',evidence=None,reviewer=None)
    write_json(s.path/'codebook.json',cb)
    print(str(s.path))


if __name__=='__main__':main()
