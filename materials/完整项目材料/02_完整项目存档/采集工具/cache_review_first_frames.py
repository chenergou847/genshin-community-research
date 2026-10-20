"""Cache API-linked first frames for at most 20 pending-prefix review items.

These public images are eligibility evidence, not comment samples or proof that
the whole video was watched. No cookie file is read by this helper.
"""
import argparse
import hashlib
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from observer.core import Study, GateError, digest, now, read_json, write_json
from observer import small


def pending_items(study, limit, cap_remaining=False):
    draw = study.frozen('small_video_draw.json')
    progress = small.video_progress(study)
    starts = {m: draw['orders'][m].index(x['next_bvid'])
              for m, x in progress.items() if x['status'] != 'ready'}
    items = []
    for rank in range(limit):
        for mode, start in starts.items():
            if cap_remaining and rank >= 20 - len(progress[mode]['selected']):
                continue
            if start + rank < len(draw['orders'][mode]):
                items.append(dict(mode=mode, bvid=draw['orders'][mode][start+rank],
                                  position=start+rank+1))
    return draw, items[:limit]


def validate_images(manifest):
    for row in manifest['records']:
        if row['status'] == 'saved':
            if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() != row['sha256']:
                raise GateError('first_frame_local_hash_changed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', required=True)
    parser.add_argument('--batch', required=True)
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--cap-remaining', action='store_true',
                        help='Only prepare up to the remaining eligible-video target per mode; keep original order.')
    args = parser.parse_args()
    if len(args.batch) != 3 or not args.batch.isdigit() or not 1 <= args.limit <= 20:
        parser.error('batch must be three digits and limit must be 1..20')
    s = Study(args.study)
    try:
        small.check(s)
        name = 'small_video_review_batch_' + args.batch + '_first_frames.json'
        if (s.path / name).exists():
            frozen = s.frozen(name)
            validate_images(frozen)
            print({'status':'already_sealed_no_network', 'records':len(frozen['records'])})
            return 0
        draw, todo = pending_items(s, args.limit, cap_remaining=args.cap_remaining)
        frame = s.frozen('small_candidate_frame.json')
        metadata = {}
        for path in (s.path / 'cache').glob('*.json'):
            env = read_json(path)
            if env.get('route') == 'view_web':
                if digest(env['response']) != env['response_hash']:
                    raise GateError('metadata_cache_hash_changed')
                metadata[env['params']['bvid']] = env
        # Verify all metadata before making any image requests.
        if any(x['bvid'] not in metadata for x in todo):
            raise GateError('enrich_next_required_before_image_cache')
        folder = s.path / 'review_evidence' / ('batch_' + args.batch)
        folder.mkdir(parents=True, exist_ok=True)
        progress_file = folder / 'progress.json'
        if progress_file.exists():
            manifest = read_json(progress_file)
            if (manifest['config_hash'] != s.config_hash or
                manifest['video_draw_hash'] != digest(draw) or manifest['requested_items'] != todo):
                raise GateError('evidence_batch_scope_changed_use_new_batch')
            validate_images(manifest)
            if any(r['status'] == 'failed_stop' for r in manifest['records']):
                raise GateError('failed_evidence_batch_requires_explicit_recovery_no_auto_retry')
        else:
            manifest = dict(config_hash=s.config_hash, video_draw_hash=digest(draw),
                            candidate_frame_hash=digest(frame), capture_started_at=now(),
                            purpose='first_frame_eligibility_evidence_not_full_video_review',
                            credential_policy='anonymous_CDN_reads_no_cookie_file_loaded',
                            requested_items=todo, records=[])
        done = {(r['mode'],r['bvid']) for r in manifest['records']}
        for item in todo:
            if (item['mode'],item['bvid']) in done:
                continue
            env = metadata[item['bvid']]
            data = env['response']['data']
            pages = data.get('pages') or []
            url = (pages[0] if pages else {}).get('first_frame')
            row = dict(item, metadata_response_hash=env['response_hash'],
                       title=data.get('title'), duration=data.get('duration'), source_url=url)
            try:
                if not url:
                    row.update(status='missing_first_frame_not_an_exclusion')
                else:
                    parts = urllib.parse.urlsplit(url)
                    if (parts.scheme not in ('https','http') or
                        not (parts.hostname or '').endswith('.hdslb.com') or
                        parts.username or parts.password or parts.port not in (None,80,443)):
                        raise GateError('unexpected_first_frame_url')
                    target = folder / (item['bvid'] + '_first_frame.jpg')
                    if target.exists():
                        previous = next((r for r in manifest['records'] if r['status']=='saved'
                                         and r.get('path')==str(target) and r.get('source_url')==url), None)
                        if not previous:
                            raise GateError('unregistered_existing_image_do_not_overwrite')
                        body = target.read_bytes()
                        if hashlib.sha256(body).hexdigest()!=previous['sha256']:
                            raise GateError('first_frame_local_hash_changed')
                        captured_at = previous['captured_at']
                    else:
                        time.sleep(max(3, float(s.config['http']['delay_seconds'])))
                        req = urllib.request.Request(url, headers={
                            'User-Agent':'Mozilla/5.0', 'Referer':'https://www.bilibili.com/'})
                        with urllib.request.urlopen(req, timeout=25) as response:
                            if not (urllib.parse.urlsplit(response.url).hostname or '').endswith('.hdslb.com'):
                                raise GateError('unexpected_asset_redirect')
                            body = response.read(5*1024*1024+1)
                        captured_at = now()
                    image = (body.startswith(b'\xff\xd8\xff') or body.startswith(b'\x89PNG') or
                             (body.startswith(b'RIFF') and body[8:12] == b'WEBP'))
                    if len(body) > 5*1024*1024 or not image:
                        raise GateError('first_frame_not_image_or_oversized')
                    if not target.exists():
                        target.write_bytes(body)
                    row.update(status='saved', path=str(target), bytes=len(body),
                               sha256=hashlib.sha256(body).hexdigest(), captured_at=captured_at)
            except (GateError, urllib.error.URLError, OSError, ValueError) as exc:
                reason = ('http_'+str(exc.code)) if isinstance(exc, urllib.error.HTTPError) else (
                    str(exc) if isinstance(exc, GateError) else type(exc).__name__)
                row.update(status='failed_stop', reason=reason)
                manifest['records'].append(row)
                write_json(progress_file, manifest)
                raise GateError(reason)
            manifest['records'].append(row)
            write_json(progress_file, manifest)
        payload = {k:v for k,v in manifest.items() if k != 'config_hash'}
        small.seal(s, name, payload)
        print({'status':'saved', 'records':len(manifest['records']),
               'image_domain_rows':sum(r['status']=='saved' for r in manifest['records']),
               'different_images':len({r['path'] for r in manifest['records'] if r['status']=='saved'})})
        return 0
    except GateError as exc:
        print({'status':'STOPPED', 'reason':str(exc)})
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
