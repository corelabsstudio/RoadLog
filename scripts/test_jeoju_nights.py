"""저주 밤 기록: 제목이 잠긴 동안에도 보이고, 6단계부터 첫 밤이 바로 열린다. (모의 LLM · 돈 안 든다)"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())

from modules import jeoju, saju_writer  # noqa: E402

ORDER = {"target": "친구", "nick": "시험이", "year": "1990", "sin": "약속을 한 시간 전에 취소한다", "spot": "입"}
NOW = 1791650000000


def fake_call(_system, prompt, **kw):
    props = kw["schema"]["properties"]
    out = {}
    for key in props:
        if key == "charm":
            out[key] = {"hanja": "斷緣塞路", "read": "단연색로", "mean": "길을 막는다."}
        elif key == "nights":
            n = int(props[key]["description"].split("정확히 ")[1].split("장")[0])
            out[key] = [{"title": "제목 %d" % (i + 1), "text": "본문 %d" % (i + 1)} for i in range(n)]
        else:
            out[key] = key + " 글"
    return {"text": json.dumps(out, ensure_ascii=False)}


class NightTest(unittest.TestCase):
    def setUp(self):
        self._orig = saju_writer._call
        saju_writer._call = fake_call

    def tearDown(self):
        saju_writer._call = self._orig

    def test_level7_first_night_open_and_titles_visible(self):
        doc = jeoju.write(ORDER, 7, now_ms=NOW)
        self.assertEqual(len(doc["nights"]), 13)
        out = jeoju.veil(doc, NOW + 1000)
        first, rest = out["nights"][0], out["nights"][1:]
        self.assertTrue(first["open"])
        self.assertEqual(first["text"], "본문 1")
        self.assertTrue(all(not n["open"] and n["text"] == "" for n in rest))
        self.assertTrue(all(n["title"].startswith("제목") for n in out["nights"]))
        # 저장본은 건드리지 않는다
        self.assertEqual(doc["nights"][5]["text"], "본문 6")

    def test_level5_still_waits_for_2am(self):
        doc = jeoju.write(ORDER, 5, now_ms=NOW)
        out = jeoju.veil(doc, NOW + 1000)
        self.assertFalse(out["nights"][0]["open"])
        self.assertEqual(out["nights"][0]["text"], "")
        self.assertEqual(out["nights"][0]["title"], "제목 1")
        later = jeoju.veil(doc, doc["nights"][0]["at"] + 1)
        self.assertEqual(later["nights"][0]["text"], "본문 1")

    def test_old_doc_without_titles_and_upgrade_keeps_old_nights(self):
        old = {"level": 6, "title": "t", "line": "l", "scene": "s", "script": "x", "undo": "u",
               "charm": {"hanja": "a", "read": "b", "mean": "c"}, "doll": "d", "nightStart": NOW,
               "nights": [{"day": d, "at": jeoju._night_at(NOW, d), "text": "옛 %d" % d} for d in range(1, 8)]}
        out = jeoju.veil(old, NOW + 1000)
        self.assertEqual(out["nights"][0]["text"], "옛 1")
        self.assertEqual(out["nights"][0]["title"], "")
        up = jeoju.write(ORDER, 7, old, now_ms=NOW)
        self.assertEqual(len(up["nights"]), 13)
        self.assertEqual(up["nights"][6]["text"], "옛 7")
        self.assertEqual(up["nights"][7]["title"], "제목 1")
        self.assertTrue(up["seal"])

    def test_due_notices_once_and_skips_first_night_of_high_levels(self):
        doc7 = jeoju.write(ORDER, 7, now_ms=NOW)
        doc5 = jeoju.write(ORDER, 5, now_ms=NOW)
        jeoju.save("a@example.com", "a" * 32, "b" * 32, ORDER, doc7)
        jeoju.save("a@example.com", "c" * 32, "d" * 32, ORDER, doc5)
        first = doc7["nights"][0]["at"]
        # 첫 새벽 2시 직후: 7단계 첫 밤은 이미 열어 줬으니 안 보내고, 5단계 첫 밤만 보낸다
        got = jeoju.due_notices(first + 60_000)
        self.assertEqual([(x["ritual"][0], x["day"]) for x in got], [("c", 1)])
        self.assertTrue(got[0]["last"])
        self.assertEqual(jeoju.due_notices(first + 120_000), [])
        # 둘째 새벽: 7단계 2번째 밤
        got = jeoju.due_notices(doc7["nights"][1]["at"] + 60_000)
        self.assertEqual([(x["ritual"][0], x["day"], x["last"]) for x in got], [("a", 2, False)])
        # 오래 쉬었다 깨면 밀린 것은 표시만 하고 보내지 않는다
        self.assertEqual(jeoju.due_notices(doc7["nights"][6]["at"] + 40 * 3600 * 1000), [])
        # 저장된 본문은 그대로다
        self.assertEqual(jeoju.get("a@example.com", "a" * 32)["doc"]["nights"][3]["text"], "본문 4")


if __name__ == "__main__":
    unittest.main()
