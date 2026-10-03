"""OAuth failures return to the signup UI without leaking provider response data."""
import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock
from urllib.parse import quote


class AuthFailure(Exception):
    pass


class NetworkFailure(Exception):
    pass


class SocialReturnTest(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).parents[1] / 'server.py').read_text(encoding='utf-8'))
        names = {'google_callback', 'kakao_callback', '_google_callback', '_kakao_callback'}
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        for fn in functions:
            fn.decorator_list = []
        self.events = Mock()
        self.scope = {
            'Request': object, 'HTTPException': AuthFailure,
            'httpx': types.SimpleNamespace(HTTPError=NetworkFailure),
            'SITE_ORIGIN': 'https://roadlog.co.kr', 'quote': quote,
            '_funnel_from': self.events,
            'RedirectResponse': lambda url, status_code: (url, status_code),
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'server.py', 'exec'), self.scope)

    def test_provider_cancel_is_recorded_and_returns_to_auth(self):
        for provider in ('google', 'kakao'):
            result = self.scope[provider + '_callback']('browser', error='access_denied')
            self.assertEqual(result, ('https://roadlog.co.kr/#social_error=access_denied', 302))
        self.assertEqual(self.events.call_count, 2)

    def test_expected_failures_return_generic_error_without_sensitive_details(self):
        for provider in ('google', 'kakao'):
            for error in (AuthFailure('private response'), NetworkFailure('secret'), ValueError('email')):
                self.scope['_' + provider + '_callback'] = Mock(side_effect=error)
                result = self.scope[provider + '_callback']('browser', code='code', state='state')
                self.assertEqual(result, ('https://roadlog.co.kr/#social_error=retry', 302))
        self.assertEqual(self.events.call_count, 6)

    def test_success_is_unchanged_and_does_not_emit_failure(self):
        self.scope['_google_callback'] = Mock(return_value='successful response')
        self.assertEqual(self.scope['google_callback']('browser', 'code', 'state'), 'successful response')
        self.scope['_google_callback'].assert_called_once_with('browser', 'code', 'state', '')
        self.events.assert_not_called()


if __name__ == '__main__':
    unittest.main()
