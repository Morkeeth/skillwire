"""Exercise the built app locally with synthetic vote replies; no production writes.

Run after scripts/build_site.py. Uses the installed Python Playwright and headless
Chrome with a fresh profile. SKILLWIRE_QA_OUT selects the screenshot receipt folder.
"""
import copy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ['SKILLWIRE_QA_OUT'])
SITE = Path(os.environ.get('SKILLWIRE_TEST_SITE', ROOT / 'dist')).resolve()


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main():
    catalog = json.loads((SITE / 'catalog.json').read_text())
    public = {s['id']: s for s in catalog['skills'] if not s.get('local_bundle')}
    ids = [sid for sid in catalog['popular_ids'] if sid in public][:4]
    assert len(ids) == 4
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(SITE)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:' + str(server.server_port)
    results = []
    try:
        with sync_playwright() as pw:
            for width in (1440, 390):
                state = {'csrf': 'fixture-csrf', 'has_identity': False,
                         'counts': {sid: {'up': n, 'down': 0, 'score': n} for sid, n in zip(ids, (8, 4, 3, 2))},
                         'mine': {}, 'ranking': [], 'total': 17, 'updated_at': '2026-11-01T17:00:00Z'}
                posts, errors = [], []
                fail = [False]

                def api(route):
                    path = route.request.url.split(base)[-1]
                    if path == '/api/directions':
                        route.fulfill(json=copy.deepcopy(state))
                    elif path == '/api/direction':
                        body = route.request.post_data_json
                        posts.append(body)
                        if fail[0]:
                            route.fulfill(status=503, json={'error': 'Fixture service unavailable'})
                            return
                        assert body['csrf'] == 'fixture-csrf'
                        sid, value = body['skill_id'], body['value']
                        assert sid in public and value in (-1, 0, 1)
                        old = state['mine'].get(sid, 0)
                        counts = state['counts'].setdefault(sid, {'up': 0, 'down': 0, 'score': 0})
                        if old:
                            counts['up' if old == 1 else 'down'] -= 1
                        if value:
                            counts['up' if value == 1 else 'down'] += 1
                            state['mine'][sid] = value
                        else:
                            state['mine'].pop(sid, None)
                        counts['score'] = counts['up'] - counts['down']
                        state['total'] = sum(v['up'] + v['down'] for v in state['counts'].values())
                        state['has_identity'] = True
                        route.fulfill(json=copy.deepcopy(state))
                    elif path.startswith('/api/analytics'):
                        route.fulfill(json={'ok': True})
                    else:
                        route.fulfill(status=404, json={'error': 'Offline fixture: route not enabled'})

                context = pw.chromium.launch_persistent_context(
                    tempfile.mkdtemp(prefix='skillwire-local-votes-'),
                    executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                    headless=True, viewport={'width': width, 'height': 1600},
                    args=['--disable-gpu', '--no-first-run'])
                try:
                    page = context.pages[0]
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    # All app API routes are synthetic; external requests are refused.
                    page.route('**/*', lambda route: api(route) if route.request.url.startswith(base + '/api/')
                               else route.continue_() if route.request.url.startswith(base + '/') else route.abort())
                    page.goto(base, wait_until='networkidle')
                    page.locator('#landing-vote-ranking .community-file').nth(3).wait_for(state='attached')
                    assert page.locator('#oscar-picks').is_visible()
                    assert page.locator('#results tr').count() == 150
                    assert page.locator('#full-view').get_attribute('aria-pressed') == 'true'
                    assert page.locator('#landing-community').is_hidden()
                    assert page.get_by_role('button', name='Refresh counts', exact=True).count() == 0
                    page.locator('#oscar-picks-preview .oscar-pick').nth(2).wait_for()
                    page.screenshot(path=str(OUT / f'FULL-LIST-{width}.png'))
                    page.locator('.secondary-community > summary').click()
                    assert page.locator('#landing-community').is_visible()
                    assert page.locator('#content-votes').is_hidden()
                    assert page.locator('#landing-vote-ranking .community-file').count() == 4
                    board = page.locator('#landing-community').bounding_box()
                    assert board['height'] > 0, 'disclosed community board must be visible'
                    for row in page.locator('#landing-vote-ranking .community-file').all():
                        box = row.bounding_box()
                        assert box['y'] >= board['y'] and box['y'] + box['height'] <= board['y'] + board['height'] + 1, 'vote row falls outside landing board'
                    assert page.locator('#landing-vote-ranking [data-direction-id]').evaluate_all('(els)=>els.map(e=>e.dataset.directionId)') == ids
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'horizontal page overflow'
                    for button in page.locator('#landing-vote-ranking .direction-vote button').all():
                        rect = button.bounding_box()
                        if width > 600:
                            assert 22 <= rect['height'] <= 28 and rect['width'] <= 28, 'desktop arrows must match compact classic buttons'
                        else:
                            assert rect['width'] >= 44 and rect['height'] >= 44, 'phone targets remain usable'
                    page.screenshot(path=str(OUT / f'LANDING-{width}.png'))
                    sid = ids[0]
                    landing = page.locator(f'#landing-vote-ranking [data-direction-id="{sid}"]')
                    full = page.locator(f'#vote-ranking [data-direction-id="{sid}"]')
                    landing.locator('[data-value="1"]').click()
                    page.wait_for_function("document.querySelector('#landing-vote-status').textContent.includes('Your vote is saved')")
                    assert len(posts) == 1 and posts[-1]['value'] == 1
                    assert landing.locator('[data-value="1"]').get_attribute('aria-pressed') == 'true'
                    page.locator('#landing-vote-all').click()
                    assert full.locator('[data-value="1"]').get_attribute('aria-pressed') == 'true'
                    if width > 600:
                        reference = page.locator('#vote-browse').bounding_box()
                        control = full.locator('button').first.bounding_box()
                        assert control['height'] == reference['height'], 'vote button must match the existing classic button height'
                        assert page.locator('#vote-ranking .community-file').evaluate_all('(rows)=>rows.every(row=>row.getBoundingClientRect().height<80)'), 'desktop rows are too tall'
                    page.screenshot(path=str(OUT / f'COMMUNITY-{width}.png'))
                    full.locator('[data-value="-1"]').click()
                    page.wait_for_function("document.querySelector('#vote-status').textContent.includes('Your vote is saved')")
                    page.get_by_role('button', name='Search', exact=True).first.click()
                    assert landing.locator('[data-value="-1"]').get_attribute('aria-pressed') == 'true'
                    landing.locator('[data-value="-1"]').click()
                    page.wait_for_function("document.querySelector('#landing-vote-status').textContent.includes('Your vote was removed')")
                    assert state['mine'].get(sid, 0) == 0 and posts[-1]['value'] == 0
                    fail[0] = True
                    landing.locator('[data-value="1"]').click()
                    page.wait_for_function("document.querySelector('#landing-vote-status').textContent.includes('Fixture service unavailable')")
                    assert landing.locator('[data-value="1"]').is_disabled()
                    assert page.locator('#vote-status').inner_text() == page.locator('#landing-vote-status').inner_text()
                    fail[0] = False
                    page.wait_for_timeout(5100)
                    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
                    page.wait_for_function("!document.querySelector('#landing-vote-ranking button[data-value=" + '"1"' + "]').disabled")
                    assert len(posts) == 4, 'automatic refresh must not cast a vote'
                    page.locator('#landing-vote-details').click()
                    assert page.locator('#content-votes details').get_attribute('open') is not None
                    assert not errors, errors
                    results.append({'width': width, 'pass': True, 'checks': ['landing visible', 'same top-four ranking', 'compact desktop / usable mobile targets', 'no overflow', 'vote sync both ways', 'undo', 'shared 503 error', 'automatic refresh without POST', 'counting details'], 'posts': len(posts), 'page_errors': errors})
                finally:
                    context.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    (OUT / 'BROWSER-QA.json').write_text(json.dumps({'scope': 'real built app, synthetic API replies, no DB or external calls', 'results': results}, indent=2))
    print(json.dumps({'passed': len(results), 'results': results}))


if __name__ == '__main__':
    main()
