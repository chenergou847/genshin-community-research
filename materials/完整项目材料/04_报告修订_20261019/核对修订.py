"""核对修订前全部文件、原始档保留、引文、报告重建及本地链接；不联网。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import io
import json
import re
import runpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ALLOWED = {
    '00_从这里开始.md',
    '01_当前交付/04_社区观察分析报告.md',
    '02_完整项目存档/全量编码_20261019/04_社区观察分析报告.md',
    '02_完整项目存档/采集工具/write_full_corpus_report.py',
    '03_岗位与接续资料/项目接续说明.md',
    '03_岗位与接续资料/检索规则与脚本分工.md',
    '03_岗位与接续资料/接续状态.json',
    '03_岗位与接续资料/下一对话直接发送.txt',
}
BACKUPS = {
    '01_当前交付/04_社区观察分析报告.md': '04_社区观察分析报告_修订前.md',
    '02_完整项目存档/采集工具/write_full_corpus_report.py': 'write_full_corpus_report_修订前.py',
    '00_从这里开始.md': '00_从这里开始_修订前.md',
    '03_岗位与接续资料/项目接续说明.md': '项目接续说明_修订前.md',
    '03_岗位与接续资料/接续状态.json': '接续状态_修订前.json',
    '03_岗位与接续资料/检索规则与脚本分工.md': '检索规则与脚本分工_修订前.md',
    '03_岗位与接续资料/下一对话直接发送.txt': '下一对话直接发送_修订前.txt',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline = json.loads((HERE / '修订前文件哈希.json').read_text(encoding='utf-8'))
    changed, deleted, unexpected = [], [], []
    for name, old in baseline.items():
        p = ROOT / name
        if not p.is_file():
            deleted.append(name)
        elif sha(p) != old:
            changed.append(name)
            if name not in ALLOWED:
                unexpected.append(name)
    assert not deleted, deleted
    assert not unexpected, unexpected
    assert set(changed) == ALLOWED, (set(changed), ALLOWED)
    for name, backup in BACKUPS.items():
        assert sha(HERE / '历史原稿' / backup) == baseline[name], backup
    assert baseline['01_当前交付/04_社区观察分析报告.md'] == baseline['02_完整项目存档/全量编码_20261019/04_社区观察分析报告.md']

    ns = runpy.run_path(str(HERE / '生成修订报告.py'))
    report, semantic_checks = ns['build']()
    local_links = []
    for i, target in enumerate(ns['TARGETS']):
        expected = report if i == 0 else report.replace('../04_报告修订_20261019/', '../../04_报告修订_20261019/')
        actual = target.read_text(encoding='utf-8')
        assert actual == expected, str(target)
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', actual):
            if link.startswith(('http://', 'https://', '#')):
                continue
            local = (target.parent / link).resolve()
            assert local.is_relative_to(ROOT.resolve()), link
            assert local.is_file(), str(local)
            local_links.append({'report': target.relative_to(ROOT).as_posix(), 'link': link})
    evidence = json.loads((HERE / '已核对评论及父链.json').read_text(encoding='utf-8'))
    raw = {r['id']: r for r in ns['read'](ns['RAW'])['comments']}
    for e in evidence:
        assert e['raw_comment'] == raw[e['row']['id']]
        for a in e['ancestors']:
            assert a == raw[a['id']]

    result = {
        'status': 'PASS',
        'checked_at_bjt': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'baseline_files': len(baseline),
        'intentionally_changed_files': sorted(changed),
        'unchanged_existing_files': len(baseline) - len(changed),
        'unexpected_changes': unexpected,
        'deleted_existing_files': deleted,
        'original_data_csv_json_and_responses_unchanged': True,
        'historical_backups_verified': len(BACKUPS),
        'local_report_links_checked': len(local_links),
        'evidence_and_readable_ancestors_match_saved_raw': True,
        'no_new_collection_sampling_or_coding': True,
        'independent_human_validation_remains_waived': True,
        'report_checks': semantic_checks,
        'data_quality_limitations_unchanged': ['strict collection gate not passed',
            'source concentration', 'missing ancestors and unread images',
            'no independent semantic accuracy measurement'],
    }
    (HERE / '修订完整性校验.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    # 将校验脚本自身及校验结果纳入新增清单，排除清单本身以避免循环哈希。
    manifest = HERE / '修订后文件清单_SHA256.csv'
    buf = io.StringIO(newline='')
    writer = csv.writer(buf)
    writer.writerow(['relative_path', 'bytes', 'sha256'])
    files = [p for p in ROOT.rglob('*') if p.is_file() and p != manifest]
    for path in sorted(files):
        writer.writerow([path.relative_to(ROOT).as_posix(), path.stat().st_size, sha(path)])
    manifest.write_text(buf.getvalue(), encoding='utf-8-sig', newline='')
    print(json.dumps({'status': result['status'], 'baseline_files': len(baseline),
                      'unchanged': result['unchanged_existing_files'], 'intentional_changes': len(changed),
                      'unexpected_changes': len(unexpected), 'local_links': len(local_links),
                      'manifest_files': len(files), 'report_checks': semantic_checks}, ensure_ascii=False))


if __name__ == '__main__':
    main()
