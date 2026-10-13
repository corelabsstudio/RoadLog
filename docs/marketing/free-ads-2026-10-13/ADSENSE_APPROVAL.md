# RoadLog AdSense approval preparation — 2026-10-13

Scope: display Google AdSense ads on RoadLog and receive advertising revenue. No paid promotion, purchased traffic, external advertising campaign or promotional post was requested or performed. Existing photos/videos and free guest rituals remain.

## Sources read directly

- [Google eligibility](https://support.google.com/adsense/answer/9724?hl=ko): original, interesting content and policy compliance.
- [Google site readiness](https://support.google.com/adsense/answer/7299563?hl=ko): unique value, usable navigation and original content. The listed criteria do not establish a fixed 20-post or 1,000-character rule.
- [Google Publisher Policies](https://support.google.com/publisherpolicies/answer/10502938?hl=en): no harassment, bullying or advocacy of harm; no ads on low-value/behaviour-only screens; no accidental clicks; privacy disclosures.
- [Google restrictions](https://support.google.com/publisherpolicies/answer/10437795?hl=en): shocking content, graphic violence and prominent profanity may restrict demand.
- [Personal experience, 2021](https://zoosso.tistory.com/842): three attempts, author says not all posts exceeded 1,000 characters. Historical anecdote, not current rules or causal proof.
- [Personal experience, 2023](https://perthfoodie.tistory.com/32): author used twenty longer posts; this does not establish a requirement or isolate the reason for approval.

Searches of Threads did not yield a directly verifiable relevant post; no Threads claim was used. Search snippets, community volunteer claims about tool sites being universally ineligible, and anecdotes about minimum post counts were not treated as official policy.

## Observed gaps and changes

1. Main value was an interactive generator; full results required submitting a story. Added four public HTML documents: guide (all levels, timing, browser storage, language), six edited fictional examples with explanations, operator/product information, and support/report/deletion instructions. Korean and English are present in the HTML; these are product documentation, not an unrelated approval blog. Existing withdrawn fortune pages stay withdrawn.
2. The one-line level-one result and raw visitor story were next to the ad placement. Removed advertising SDK loading from all generated results. Ads now accompany only the operator-written guide and examples, separated from actions. No ads on input/loading/ritual, about/contact/legal pages; no auto refresh, ad gating or click encouragement. No result is publicly published for crawling.
3. Added visible home navigation, fictional-example labelling, input reminders to use made-up nicknames and omit private information/threats.
4. Corrected the stale paid-level sentence in terms and described public-guide advertising in privacy disclosures. Existing purchase rights are preserved.
5. Server and generated sitemap now contain the same nine live public curse pages, excluding retired fortune/blog pages. No invented modification dates, fake reviews or traffic claims.
6. Public ad pages register the official Google CMP callback and show a privacy choices button only once the API is ready. Existing EEA/UK/Swiss ad guard remains active until real consent runtime is verified. Local callback tests do not prove Google CMP operation.

## Verification

- Full `ship.py --no-commit` checks and build passed; follow-up `ship.py --check` passed after sitemap alignment.
- Seven free-curse and four night-journal tests passed.
- `verify_approval.py` checked four pages in both languages at 390px, visible content, language-preserving links, no horizontal overflow/page errors, a single mocked ad SDK on guide/examples, mocked consent revocation, no SDK on a private fixture result.
- SHA256 of all 883 original source media files still matches the pre-conversion manifest.
- Local tests use a mocked Google SDK; no live ad clicks or manufactured impressions were generated. Live QA uses `nocount=1`.

## Limits

These changes address observed quality and placement issues, not a guarantee of approval. Site review was requested earlier; no rejection was observed and no redundant review request was submitted. Google decides approval and ad demand. Actual filled ad impressions/revenue and European CMP runtime remain unverified. Keeping the fictional curse subject may still affect Google's assessment; an entertainment disclaimer alone is not an exemption from publisher policies.
