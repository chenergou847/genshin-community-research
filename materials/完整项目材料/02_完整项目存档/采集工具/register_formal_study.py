"""本轮正式执行的预登记；仅创建新目录，不覆盖旧研究或试跑。"""
from observer.core import Study, digest, now, write_json


def main():
    s=Study.init("正式采集_v1_20261017")
    c=s.config
    c.update(adapter="web_wbi_v1",revision="1-registered",t0="2026-10-17T23:09:00+08:00",
             confirmed_by="用户",confirmation_record="本会话已确认12-v1双轨抽样；2026-10-17要求生成正式样本，并确认深渊/剧诗凌晨4点、幽境上午10点")
    date_source="https://ys.mihoyo.com/main/news/detail/166392"
    hours="小时依据：用户本会话明确确认国服时刻；不冒称官网7.1正文写了04:00"
    c["periods"]={
        "abyss":dict(period_id="CN-7.1-abyss-20261016",start="2026-10-16T04:00:00+08:00",
                     characteristics="骇星之月；第11层风/冰伤+60%；第12层上半星烁反应伤害+75%、下半冰伤+75%；11/12层当期阵容另随视频核验",
                     evidence=date_source+"，九、深境螺旋（日期和祝福/地脉）；"+hours,verified_by="AI读取官网日期与规则；用户确认国服刷新小时"),
        "theater":dict(period_id="CN-7.1-theater-20261001",start="2026-10-01T04:00:00+08:00",
                       characteristics="限定水、冰、风；开幕那维莱特、芭芭拉、茜特菈莉、凯亚、流浪者、布伦妮；特邀伊涅芙、八重神子、托马、千织",
                       evidence=date_source+"，八、幻想真境剧诗第一期（日期/元素/开幕/特邀）；"+hours,verified_by="AI读取官网日期与规则；用户确认国服刷新小时"),
        "stygian":dict(period_id="CN-7.1-stygian-20260930",start="2026-09-30T10:00:00+08:00",
                       characteristics="7.1活动区间9月30日至11月3日；紊乱爆发期9月30日至10月10日；三场当期敌人与难度随原视频实机内容核验，不凭7.1标题认定",
                       evidence="https://www.taptap.cn/moment/853584114496833713?group_id=201765 西风快报员活动公告；用户本会话确认国服10:00",
                       verified_by="AI读取官方运营账号公告；用户确认国服开放小时")}
    write_json(s.path/"config.json",c)
    s=Study(s.path)
    s.validate()
    s.import_candidates("../11_优化样本清单.csv",path_id="legacy-reviewed-35")
    s.import_candidates("../数据/扩检全部命中索引.csv",path_id="legacy-search-252")
    s.immutable("registration.json",dict(config_hash=s.config_hash,registered_at=now(),t0=c["t0"],
                purpose="正式规则预登记；尚未形成合格视频库和随机样本",periods=c["periods"],
                queries_hash=digest(c["queries"]),targets=c["targets"],credential_method="正常公开匿名会话，无浏览器凭证提取",
                evidence_note="日期/识别特征来自官网7.1说明及西风快报员公告；深渊和剧诗的具体小时由用户确认，尚无外部实机截图"))
    print(str(s.path))


if __name__=="__main__":
    main()
