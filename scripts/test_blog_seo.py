"""Published database posts remain discoverable and carry matching article metadata."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modules.marketing_blog import BlogPublisher


class FakeRepository:
    def blog_sitemap_posts(self):
        return [{'slug': 'ai-7', 'published_at': '2026-09-29T00:00:00+00:00'},
                {'slug': 'draft-8', 'published_at': '2026-09-29T00:00:00+00:00'}]

    def blog_post(self, slug):
        if slug != 'ai-7':
            return None
        return {'title': '다시 만난 뒤 살필 것', 'hook': '같은 다툼을 돌아봅니다.',
                'body': '첫 문단입니다.', 'cta': '같은 이별 재방송 확률 보기',
                'tracking_url': 'https://roadlog.co.kr/saju/loop.html',
                'published_at': '2026-09-29T00:00:00+00:00'}


class BlogSeoTest(unittest.TestCase):
    def test_sitemap_and_article_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sitemap.xml').write_text(
                '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>https://roadlog.co.kr/</loc></url></urlset>', encoding='utf-8')
            (root / 'blog').mkdir()
            source = Path(__file__).resolve().parent.parent / 'web' / 'blog' / 'first-time-saju.html'
            (root / 'blog' / 'first-time-saju.html').write_bytes(source.read_bytes())
            publisher = BlogPublisher(FakeRepository(), root, 'https://roadlog.co.kr')
            xml = ET.fromstring(publisher.render_sitemap())
            locations = [node.text for node in xml.iter() if node.tag.endswith('}loc')]
            self.assertIn('https://roadlog.co.kr/blog/ai-7.html', locations)
            self.assertNotIn('https://roadlog.co.kr/blog/draft-8.html', locations)
            page = publisher.render('ai-7')
            self.assertIn('<meta property="og:type" content="article"', page)
            self.assertIn('<link rel="canonical" href="https://roadlog.co.kr/blog/ai-7.html"', page)
            payload = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
            self.assertIsNotNone(payload)
            graph = json.loads(payload.group(1))['@graph']
            article = next(item for item in graph if item['@type'] == 'BlogPosting')
            self.assertEqual(article['headline'], '다시 만난 뒤 살필 것')
            self.assertEqual(article['url'], 'https://roadlog.co.kr/blog/ai-7.html')
            self.assertEqual(article['datePublished'], '2026-09-29T00:00:00+00:00')


if __name__ == '__main__':
    unittest.main()
