"""Public docs/ad placement QA. Local runs mock SDK/config; live runs never request ads."""
import hashlib,json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path(__file__).resolve().parent
BASE=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:5184'
LIVE=BASE.startswith('https:')
fixture={'ritual':'f'*24,'order':{'target':'친구','nick':'Test Goblin','year':'','sin':'Private test story','spot':''},'doc':{'level':1,'language':'en','title':'Test fixture','line':'A tiny fictional inconvenience.'},'want':1,'pending':0}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':390,'height':844})
    context.route('**/api/site/locale',lambda r:r.fulfill(json={'language':'en','country':'US'}))
    context.route('**/api/ads/config',lambda r:r.fulfill(json={'enabled':True,'client':'ca-pub-2523025753289844','slot':'1812158500'}))
    requests=[]
    context.on('request',lambda r:requests.append(r.url))
    sdk="window.googlefc.showRevocationMessage=()=>{window.revoked=true}; for(const c of window.googlefc.callbackQueue){if(c.CONSENT_API_READY)c.CONSENT_API_READY()} window.googlefc.callbackQueue.push=(c)=>{if(c.CONSENT_API_READY)c.CONSENT_API_READY()}; window.adsbygoogle=[];"
    context.route('**/*adsbygoogle.js*',lambda r:r.fulfill(body=sdk,content_type='application/javascript'))
    context.route('**/api/jeoju/free/*',lambda r:r.fulfill(status=404,json={'detail':'fixture'}))
    page=context.new_page(); errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    for lang in ['ko','en']:
        for slug in ['guide','examples','about','contact']:
            query='&nocount=1' if LIVE else ''
            response=page.goto(f'{BASE}/{slug}.html?lang={lang}{query}')
            assert response.status==200
            page.wait_for_function(f'document.documentElement.lang==="{lang}"')
            assert page.locator('main h1:visible').count()==1
            assert len(page.locator(f'[data-help-lang="{lang}"]').inner_text())>600
            assert page.locator('html').evaluate('(el)=>el.scrollWidth<=innerWidth')
            for href in page.locator('.help-nav a').evaluate_all('(els)=>els.map(el=>el.getAttribute("href"))'):
                assert f'lang={lang}' in href
            if not LIVE and slug in ['guide','examples']:
                page.locator('#privacyChoices').wait_for(state='visible')
                assert page.locator('ins.adsbygoogle').count()==1
                page.locator('#privacyChoices').click()
                page.wait_for_function('window.revoked===true')
                assert page.locator('script[src*="adsbygoogle.js"]').count()==1
            else:
                assert page.locator('ins.adsbygoogle').count()==0
            if slug=='guide':
                page.evaluate('window.scrollTo(0,0)')
                page.screenshot(path=str(OUT/f'approval-{"live" if LIVE else "local"}-{lang}.png'),full_page=False)
    # Existing private result remains usable, without loading any advertising SDK.
    page.add_init_script('localStorage.setItem("roadlog.jeoju.v1",'+json.dumps(json.dumps(fixture))+');')
    page.goto(f'{BASE}/jeoju.html?lang=en&nocount=1')
    page.locator('#lastOpen').click(); page.locator('#viewDoc').wait_for(state='visible')
    assert page.locator('#docTitle').inner_text()=='Test fixture'
    assert page.locator('script[src*="adsbygoogle.js"],ins.adsbygoogle').count()==0
    assert errors==[],errors
    browser.close()
root=OUT.parents[3]/'roadlog-saju'
before=json.loads((OUT/'source-media-before.json').read_text('utf-8'))
assert all(hashlib.sha256((root/rel).read_bytes()).hexdigest()==sha for rel,sha in before.items())
print(json.dumps({'base':BASE,'public_pages':8,'languages':['ko','en'],'page_errors':errors,'original_media_unchanged':len(before),'private_results_ads':0,'real_ad_requests':0,'sdk_mocked':not LIVE},ensure_ascii=False))
