"""落实预先约定的触顶分箱；旧失败版本保留，目标总体和T0不变。"""
from observer.core import Study, digest, now, read_json, write_json


def main():
    parent=Study("正式采集_v1_20261017")
    registration=parent.frozen("registration.json")
    contract=read_json("接口核验_20261017_2300/日期筛选契约核验.json")
    if not contract["all_returned_dates_in_range"]:
        raise RuntimeError("日期过滤契约未通过")
    s=Study.init("正式采集_v2_20261017")
    c=parent.config
    c["revision"]="2-normal-web-date-partitions"
    c["date_partitioning"]=dict(begin_param="pubtime_begin_s",end_param="pubtime_end_s",result_cap=1000,
          evidence="正常B站搜索页最近一周控件生成秒时间戳；对应普通WBI搜索请求返回视频日期均在界内，见../接口核验_20261017_2300/日期筛选契约核验.json",
          algorithm="每查询从[0,T0]开始；触及1000结果或50页上限则在整数秒中点二分；子区间[lo,mid]与[mid+1,hi]；每个未触顶叶区间完整分页；单秒仍触顶或任一缺页则失败",
          amendment_reason="主查询真实遇到平台截断，按12-v1既定日期分箱规则落实，不调整关键词、相关性或样本目标")
    write_json(s.path/"config.json",c)
    s=Study(s.path)
    s.validate()
    s.import_candidates(parent.path/"video_review.csv",path_id="legacy-and-v1-known-candidates")
    s.immutable("registration.json",dict(config_hash=s.config_hash,registered_at=now(),t0=c["t0"],
                parent_registration_hash=digest(registration),periods=c["periods"],date_partitioning=c["date_partitioning"],queries_hash=digest(c["queries"]),targets=c["targets"],
                purpose="正常网页接口及日期分箱技术修订；未冻结视频库，未产生正式样本"))
    print(str(s.path))


if __name__=="__main__":
    main()
