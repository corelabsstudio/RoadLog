"""회원 방문 구분: 중복, 로그인 전환, 과거 기록, KST 날짜 경계."""
import json
import ast
import asyncio
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock

from scripts.test_admin_stats_funnel import stats


class VisitKindsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / 'visits.json'
        self.file_patch = patch.object(stats, 'VISITS_JSON', self.file)
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)
        self.clock = patch.object(stats, 'now_kst', return_value=datetime(2026, 10, 3, 23, 59, tzinfo=stats.KST))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        stats._MEMBER_VISITS.clear()
        stats._MEMBER_VISITS_DAY = ''

    def test_guest_login_and_reload_count_once(self):
        stats.hit('a', 'Mozilla Chrome', '/')
        stats.hit('a', 'Mozilla Chrome', '/')
        stats.hit('b', 'Mozilla Chrome', '/')
        stats.member_visit('a', 'Mozilla Chrome')
        stats.member_visit('a', 'Mozilla Chrome')
        stats.hit('a', 'Mozilla Chrome', '/')
        row = stats._visits()['2026-10-03']
        self.assertEqual((row['uv'], row['member_uv'], row['guest_uv'], row['unknown_uv']), (2, 1, 1, 0))
        self.assertEqual(row['pv'], 4)

    def test_internal_and_api_only_do_not_add_visitors(self):
        stats.hit('a', 'Mozilla Chrome', '/pay.html', 'https://roadlog.co.kr/', 'roadlog.co.kr')
        stats.member_visit('a', 'Mozilla Chrome')
        self.assertEqual(stats._visits()['2026-10-03']['uv'], 0)

    def test_legacy_record_is_unknown_and_member_can_be_recognized(self):
        fp = stats._fingerprint('a', 'Mozilla Chrome', '2026-10-03')
        self.file.write_text(json.dumps({'2026-10-03': {'uv': [fp, 'old'], 'pv': 2, 'src': {}}}), encoding='utf-8')
        row = stats._visits()['2026-10-03']
        self.assertEqual((row['member_uv'], row['guest_uv'], row['unknown_uv']), (0, 0, 2))
        stats.member_visit('a', 'Mozilla Chrome')
        row = stats._visits()['2026-10-03']
        self.assertEqual((row['member_uv'], row['guest_uv'], row['unknown_uv']), (1, 0, 1))

    def test_new_kst_day_and_overview(self):
        stats.hit('a', 'Mozilla Chrome', '/')
        stats.member_visit('a', 'Mozilla Chrome')
        with patch.object(stats, 'now_kst', return_value=datetime(2026, 10, 4, 0, 1, tzinfo=stats.KST)):
            stats.hit('a', 'Mozilla Chrome', '/')
            with (patch.object(stats, '_charges', return_value=[]), patch.object(stats, '_spends', return_value=[]),
                  patch.object(stats, '_signups', return_value=[]), patch.object(stats, 'members', return_value=[]),
                  patch.object(stats, '_via_funnel', return_value=[])):
                result = stats.overview(2)
            self.assertEqual(result['today']['guest_uv'], 1)
            self.assertEqual(result['today']['member_uv'], 0)
            self.assertEqual(result['month']['member_uv'], 1)
            self.assertEqual(result['month']['guest_uv'], 1)
            for row in result['daily']:
                self.assertEqual(row['uv'], row['member_uv'] + row['guest_uv'] + row['unknown_uv'])


class MiddlewareKindsTest(unittest.TestCase):
    def test_member_requires_valid_session_and_success(self):
        source = (Path(__file__).resolve().parents[1] / 'server.py').read_text(encoding='utf-8')
        function = next(n for n in ast.parse(source).body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_count_visit')
        function.decorator_list = []
        collector = Mock()
        namespace = {'Request': object, 'stats_ops': collector, '_sessions': {'valid': {'email': 'test@example.invalid'}},
                     '_BOT': ('bot',), '_client_ip': lambda request: 'test'}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'visit_middleware', 'exec'), namespace)
        for token, status, expected in [('valid', 200, True), ('fake', 200, False), ('valid', 401, False), ('valid', 500, False)]:
            collector.reset_mock()
            request = types.SimpleNamespace(url=types.SimpleNamespace(path='/api/ping'),
                                            headers={'user-agent': 'Mozilla Chrome', 'authorization': 'Bearer ' + token},
                                            query_params={}, cookies={}, method='GET')
            response = types.SimpleNamespace(status_code=status)
            async def next_handler(request):
                return response
            asyncio.run(namespace['_count_visit'](request, next_handler))
            self.assertEqual(collector.member_visit.called, expected)
            self.assertEqual(collector.live_touch.call_args.args[2], expected)
        for path, ua, cookies in [('/api/admin/stats', 'Mozilla Chrome', {}), ('/api/ping', 'Mozilla bot', {}),
                                  ('/api/ping', 'Mozilla Chrome', {'rl_nocount': '1'})]:
            collector.reset_mock()
            request.url.path = path
            request.headers['user-agent'] = ua
            request.cookies = cookies
            asyncio.run(namespace['_count_visit'](request, next_handler))
            collector.member_visit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
