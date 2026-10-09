"""Regression for the admin stats response after signup funnel tracking."""
import sys
import types
import tempfile
import json
from pathlib import Path
import unittest
from unittest.mock import patch


if "dotenv" not in sys.modules:
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv

from modules import stats


class AdminStatsFunnelTest(unittest.TestCase):
    def test_signup_path_requires_order_deduplicates_and_preserves_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'visits.json'
            with patch.object(stats, 'VISITS_JSON', file), patch.object(stats, '_today', return_value='2026-10-05'):
                ip, ua = '192.0.2.77', 'Mozilla Signup Test'
                # A signup before visiting cannot fabricate a complete journey.
                stats.funnel('signup_email', ip, ua)
                stats.funnel('path_visit', ip, ua)
                stats.funnel('path_auth', ip, ua)
                stats.funnel('path_product', ip, ua)
                stats.funnel('path_auth', ip, ua)
                stats.funnel('signup_social', ip, ua)
                stats.funnel('signup_social', ip, ua)
                stats.funnel('path_visit', '192.0.2.78', ua)
                raw = file.read_text(encoding='utf-8')
                result = stats._signup_path_sum(stats._visits(), '2026-09-01')
            self.assertEqual(result['daily'], [dict(day='2026-10-05', visit=2, product=1, auth=1, signup=1)])
            self.assertEqual(result['since'], '2026-10-05')
            self.assertNotIn(ip, raw)
            self.assertNotIn(ua, raw)

    def test_signup_path_does_not_infer_historical_or_cross_day_completion(self):
        visits = {'2026-10-04': {'signup_path': {'old': 4}},
                  '2026-10-05': {'signup_path': {'a': 2}},
                  '2026-10-06': {'signup_path': {'a': 1}, 'fun': {'signup_email': ['a']}}}
        self.assertEqual(stats._signup_path_sum(visits, '2026-09-01')['daily'],
                         [dict(day='2026-10-05', visit=1, product=1, auth=0, signup=0),
                          dict(day='2026-10-06', visit=1, product=0, auth=0, signup=0)])

    def test_conversion_home_cohort_uses_intersection_and_signup_union(self):
        vis = {
            '2026-10-03': {'fun': {'landing_guest': ['old']}},
            '2026-10-04': {'fun': {
                'landing_guest': ['a', 'b'], 'input_start': ['a', 'outside'],
                'signup_cta': ['b', 'outside'], 'signup_email': ['b'],
                'signup_social': ['b', 'outside'], 'dream_complete': ['member'],
            }},
            '2026-10-05': {'fun': {'landing_guest': ['a'], 'signup_social': ['a']}},
        }
        result = stats._conversion_sum(vis, '2026-09-01')
        self.assertEqual(result['since'], '2026-10-04')
        self.assertEqual(result['homeCohort'], {'landing': 3, 'input': 1, 'auth': 1, 'signup': 2})
        counts = {r['key']: r['n'] for r in result['events']}
        self.assertEqual(counts['input_start'], 2)
        self.assertEqual(counts['dream_complete'], 1)

    def test_conversion_deduplicates_and_stores_no_raw_client_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'visits.json'
            with patch.object(stats, 'VISITS_JSON', file), patch.object(stats, '_today', return_value='2026-10-04'):
                stats.funnel('landing_guest', '192.0.2.51', 'Mozilla Test Client')
                stats.funnel('landing_guest', '192.0.2.51', 'Mozilla Test Client')
                stats.funnel('email_error', '192.0.2.51', 'Mozilla Test Client')
                stats.funnel('private_email@example.org', '192.0.2.51', 'Mozilla Test Client')
                raw = file.read_text(encoding='utf-8')
            fun = json.loads(raw)['2026-10-04']['fun']
            self.assertEqual(len(fun['landing_guest']), 1)
            self.assertEqual(set(fun), {'landing_guest', 'email_error'})
            self.assertNotIn('192.0.2.51', raw)
            self.assertNotIn('Mozilla Test Client', raw)
            self.assertNotIn('@example.org', raw)

    def test_real_uv_counts_only_js_visits_and_funnel_has_js_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'visits.json'
            with patch.object(stats, 'VISITS_JSON', file), patch.object(stats, '_today', return_value='2026-10-09'):
                stats.funnel('path_visit', '192.0.2.1', 'ua')
                stats.funnel('path_visit', '192.0.2.2', 'ua')
                stats.funnel('path_visit', '192.0.2.2', 'ua')
                # 봇은 path_visit 을 안 보낸다 — uv 에만 들어간다
                data = stats._read(file, {}); data['2026-10-09']['uv'] = ['a', 'b', 'c', 'd', 'e']
                stats._write(file, data)
                vis = stats._visits()
                self.assertEqual(vis['2026-10-09']['real_uv'], 2)
                self.assertEqual(vis['2026-10-09']['uv'], 5)
                rows = stats._funnel_sum(vis, '2026-09-01')
            self.assertEqual(rows[0]['key'], 'visit'); self.assertEqual(rows[0]['n'], 5)
            self.assertEqual(rows[1]['key'], 'visit_js'); self.assertEqual(rows[1]['n'], 2)

    def test_funnel_excludes_visits_before_tracking_started(self):
        visits = {
            '2026-09-28': {'uv': 100, 'fun': {}},
            '2026-09-29': {'uv': 8, 'fun': {'product': ['a', 'b']}},
            '2026-09-30': {'uv': 5, 'fun': {'product': ['c']}},
        }
        counts = {row['key']: row['n'] for row in stats._funnel_sum(visits, '2026-09-01')}
        self.assertEqual(counts['visit'], 13)
        self.assertEqual(counts['product'], 3)
        recent = {row['key']: row['n'] for row in stats._funnel_sum(visits, '2026-09-30')}
        self.assertEqual(recent['visit'], 5)
        self.assertEqual(recent['product'], 1)

    def test_overview_counts_normalized_visits_and_funnel_steps(self):
        day = stats._today()
        raw = {
            day: {
                "pv": 4,
                "uv": ["a", "b", "c"],
                "src": {"검색": 2, "사이트 안": 1},
                "fun": {"product": ["a", "b"], "auth_open": ["a"]},
            }
        }
        with (
            patch.object(stats, "_read", return_value=raw),
            patch.object(stats, "_charges", return_value=[]),
            patch.object(stats, "_spends", return_value=[]),
            patch.object(stats, "_signups", return_value=[]),
            patch.object(stats, "members", return_value=[]),
            patch.object(stats, "_via_funnel", return_value=[]),
        ):
            result = stats.overview(days=1)

        funnel = {row["key"]: row["n"] for row in result["funnel"]}
        self.assertEqual(result["today"]["uv"], 2)
        self.assertEqual(funnel["visit"], 2)
        self.assertEqual(funnel["product"], 2)
        self.assertEqual(funnel["auth_open"], 1)


if __name__ == "__main__":
    unittest.main()
