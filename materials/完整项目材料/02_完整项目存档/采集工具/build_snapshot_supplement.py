"""Retain the 232-ID baseline; extend to at most 200 IDs per game mode."""
import argparse
import json
from observer.core import Study
from observer.snapshot_supplement import run


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--study',default='正式采集_小样本v1_20261018')
    args=ap.parse_args()
    result=run(Study(args.study))
    print(json.dumps({k:result[k] for k in ('status','domains','original_n','added_n','final_n',
        'original_IDs_retained','original_files_unchanged','quota_and_prefix_replay_verified')},ensure_ascii=False))
