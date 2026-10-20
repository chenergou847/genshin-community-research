import http.cookiejar
from pathlib import Path
import tempfile
import time
import unittest

from local_bili_login import LoginError, bili_domain, save_bili_cookies, request_json


def cookie(domain, name, value='synthetic-test-value', expired=False):
    return http.cookiejar.Cookie(0, name, value, None, False, domain, True,
                                 domain.startswith('.'), '/', True, True,
                                 int(time.time()) + (-10 if expired else 300),
                                 False, None, None, {'HttpOnly': None}, False)


class LocalLoginTests(unittest.TestCase):
    def test_exact_service_scope(self):
        self.assertTrue(bili_domain('.bilibili.com'))
        self.assertTrue(bili_domain('api.bilibili.com'))
        self.assertFalse(bili_domain('evilbilibili.com'))
        self.assertFalse(bili_domain('bilibili.com.example.org'))

    def test_save_roundtrip_filters_other_services(self):
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(cookie('.bilibili.com', 'SESSDATA'))
        jar.set_cookie(cookie('.bilibili.com', 'bili_jct'))
        jar.set_cookie(cookie('.example.org', 'other'))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'cookies.txt'
            self.assertEqual(save_bili_cookies(jar, p), 2)
            restored = http.cookiejar.MozillaCookieJar(str(p))
            restored.load(ignore_discard=True)
            self.assertEqual({c.name for c in restored}, {'SESSDATA', 'bili_jct'})

    def test_no_overwrite(self):
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(cookie('.bilibili.com', 'SESSDATA'))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'cookies.txt'
            p.write_text('existing synthetic file')
            with self.assertRaises(FileExistsError):
                save_bili_cookies(jar, p)
            self.assertEqual(p.read_text(), 'existing synthetic file')

    def test_expired_session_not_saved(self):
        jar = http.cookiejar.CookieJar()
        jar.set_cookie(cookie('.bilibili.com', 'SESSDATA', expired=True))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'cookies.txt'
            with self.assertRaises(LoginError):
                save_bili_cookies(jar, p)
            self.assertFalse(p.exists())

    def test_non_bili_destination_blocked_before_network(self):
        with self.assertRaises(LoginError):
            request_json(None, 'https://example.org/x')
        with self.assertRaises(LoginError):
            request_json(None, 'http://passport.bilibili.com/x')


if __name__ == '__main__':
    unittest.main()
