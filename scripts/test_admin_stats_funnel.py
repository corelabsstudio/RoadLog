"""Regression for the admin stats response after signup funnel tracking."""
import sys
import types
import unittest
from unittest.mock import patch


if "dotenv" not in sys.modules:
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv

from modules import stats


class AdminStatsFunnelTest(unittest.TestCase):
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
