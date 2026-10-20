"""Normal Bilibili QR login; saves only Bilibili cookies to a user-selected file.

No browser profile access. No credentials, QR keys, or response bodies in logs.
The loopback page serves a QR image and a non-sensitive status only.
"""
import argparse
import copy
import csv
import http.cookiejar
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class LoginError(Exception):
    pass


class BiliOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urllib.parse.urlsplit(newurl)
        if p.scheme != 'https' or not bili_domain(p.hostname or ''):
            raise LoginError('unexpected_redirect_stopped')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def bili_domain(domain):
    domain = domain.lower().lstrip('.')
    return domain == 'bilibili.com' or domain.endswith('.bilibili.com')


def request_json(opener, url, params=None):
    if params:
        url += '?' + urllib.parse.urlencode(params)
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or not bili_domain(p.hostname or ''):
        raise LoginError('destination_not_bilibili')
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0', 'Referer': 'https://passport.bilibili.com/',
        'Accept': 'application/json',
    })
    try:
        with opener.open(request, timeout=15) as response:
            data = json.loads(response.read(1024 * 1024))
    except urllib.error.HTTPError as exc:
        raise LoginError('http_' + str(exc.code)) from None
    except (OSError, ValueError):
        raise LoginError('network_or_json_error') from None
    if not isinstance(data, dict) or data.get('code') != 0:
        raise LoginError('login_endpoint_rejected')
    body = data.get('data')
    if not isinstance(body, dict) or body.get('v_voucher'):
        raise LoginError('unexpected_response_or_access_challenge')
    return body


def prepare_private_file(path):
    """Apply access restrictions to an EMPTY new file before any secret is written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        if os.name == 'nt':
            out = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
                                 capture_output=True, text=True, check=True).stdout
            sid = next(csv.reader(io.StringIO(out.strip())))[-1]
            if not sid.startswith('S-1-'):
                raise LoginError('local_user_sid_unavailable')
            subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
                            '*' + sid + ':(F)'], capture_output=True, check=True)
        else:
            os.chmod(path, 0o600)
    except Exception:
        path.unlink(missing_ok=True)  # still empty, created only by this operation
        raise LoginError('private_file_permissions_failed') from None


def save_bili_cookies(jar, target):
    selected = http.cookiejar.MozillaCookieJar(str(target))
    for cookie in jar:
        if bili_domain(cookie.domain):
            selected.set_cookie(copy.copy(cookie))
    if not any(c.name == 'SESSDATA' and c.value and not c.is_expired() for c in selected):
        raise LoginError('login_cookie_missing_or_expired')
    prepare_private_file(target)
    selected.save(ignore_discard=True, ignore_expires=False)
    check = http.cookiejar.MozillaCookieJar(str(target))
    check.load(ignore_discard=True, ignore_expires=False)
    if not any(c.name == 'SESSDATA' and c.value for c in check):
        raise LoginError('saved_cookie_verification_failed')
    return len(list(check))


PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>B站本机采集登录</title>
<style>body{margin:0;background:#f4f7fa;color:#172b3b;font:18px/1.7 system-ui}
main{max-width:600px;margin:5vh auto;padding:34px;background:white;border-radius:18px;text-align:center}
h1{font-size:27px}img{width:300px;height:300px}p{margin:18px 0}.muted{font-size:15px;color:#62707c}
#status{font-weight:bold;color:#087b9e}code{word-break:break-all}</style>
<main><h1>用哔哩哔哩 App 扫码登录</h1><p>请在手机中核对并确认这次电脑端登录。</p>
<img src="qr.png" alt="B站官方扫码登录二维码"><p id="status">等待扫码</p>
<p class="muted">登录成功后，会话仅保存到本机指定目录，供社区研究脚本使用。<br>
这会获得普通网页登录会话；采集脚本只发送读取请求。</p></main><script src="page.js"></script></html>'''

JS = '''async function tick(){try{let r=await fetch('status',{cache:'no-store'});let s=await r.json();
document.getElementById('status').textContent=s.message;if(s.done)return;}catch(e){}setTimeout(tick,2000)}tick();'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--control', required=True, help='Local URL/status metadata; contains no credentials')
    parser.add_argument('--lib', help='Directory containing the qrcode package')
    args = parser.parse_args()
    target = Path(args.output).resolve()
    control = Path(args.control).resolve()
    if target.exists():
        raise LoginError('output_exists_no_overwrite')
    if args.lib:
        sys.path.insert(0, str(Path(args.lib).resolve()))
    import qrcode
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), BiliOnlyRedirect())
    generated = request_json(opener, 'https://passport.bilibili.com/x/passport-login/web/qrcode/generate')
    qrurl, qrkey = generated.get('url'), generated.get('qrcode_key')
    if not qrurl or not qrkey:
        raise LoginError('qr_schema_changed')
    qrhost = urllib.parse.urlsplit(qrurl)
    if qrhost.scheme != 'https' or not bili_domain(qrhost.hostname or ''):
        raise LoginError('unexpected_qr_destination')
    image = io.BytesIO()
    qrcode.make(qrurl).save(image, format='PNG')
    image_bytes = image.getvalue()
    route = '/' + secrets.token_urlsafe(18) + '/'
    state = {'status': 'waiting', 'message': '等待扫码', 'done': False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
                self.send_error(403)
                return
            resources = {
                route: ('text/html; charset=utf-8', PAGE.encode()),
                route + 'page.js': ('text/javascript; charset=utf-8', JS.encode()),
                route + 'qr.png': ('image/png', image_bytes),
                route + 'status': ('application/json; charset=utf-8', json.dumps(state, ensure_ascii=False).encode()),
            }
            resource = resources.get(self.path)
            if not resource:
                self.send_error(404)
                return
            mime, data = resource
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}{route}'

    def set_state(status, message, done=False, **metadata):
        state.update(status=status, message=message, done=done)
        control.write_text(json.dumps(dict(state, url=url, output=str(target), **metadata),
                                      ensure_ascii=False, indent=2), encoding='utf-8')

    set_state('waiting', '等待扫码')
    print(json.dumps({'status': 'waiting', 'url': url}, ensure_ascii=False), flush=True)
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            time.sleep(2)
            result = request_json(opener, 'https://passport.bilibili.com/x/passport-login/web/qrcode/poll', {'qrcode_key': qrkey})
            code = result.get('code')
            if code == 86101:
                continue
            if code == 86090:
                set_state('scanned', '已扫码，请在手机上确认登录')
                continue
            if code == 86038:
                set_state('expired', '二维码已过期，尚未保存会话', True)
                break
            if code != 0:
                raise LoginError('unexpected_qr_status')
            nav = request_json(opener, 'https://api.bilibili.com/x/web-interface/nav')
            if nav.get('isLogin') is not True:
                raise LoginError('authenticated_session_not_verified')
            count = save_bili_cookies(jar, target)
            set_state('saved', '登录已核验，会话文件已保存。可以继续采集。', True, cookie_count=count)
            print(json.dumps({'status': 'saved', 'cookie_count': count, 'path': str(target)}, ensure_ascii=False), flush=True)
            break
        else:
            set_state('expired', '二维码已过期，尚未保存会话', True)
    except LoginError as exc:
        set_state('error', '登录未完成：' + str(exc), True)
        print(json.dumps({'status': 'error', 'reason': str(exc)}), flush=True)
    except Exception:
        set_state('error', '本机登录程序错误，未确认成功', True)
        print('{"status":"error","reason":"local_error"}', flush=True)
    finally:
        # Leave the result visible briefly; no indefinite background service.
        time.sleep(20)
        server.shutdown()


if __name__ == '__main__':
    try:
        main()
    except LoginError as exc:
        print(json.dumps({'status': 'error', 'reason': str(exc)}), flush=True)
        sys.exit(1)
