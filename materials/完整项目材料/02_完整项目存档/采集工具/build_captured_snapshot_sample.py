"""Offline entry point for the approved saved-corpus sampling workaround."""
import argparse
import json
from observer.core import Study
from observer.snapshot_sample import run


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--study',default='正式采集_小样本v1_20261018')
    args=ap.parse_args()
    result=run(Study(args.study))
    print(json.dumps({k:result[k] for k in ('status','domains','raw_sample_rows','unique_sampled_IDs',
        'seed_replay_verified','coding_completed','feedback_proportions_computed')},ensure_ascii=False))
