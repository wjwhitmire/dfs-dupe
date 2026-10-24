"""Browser test of the published site: placeholders filled, served under /dfs-dupe/.

Skips when Playwright or Chromium is missing
(pip install playwright && python -m playwright install chromium).
"""

from __future__ import annotations

import json

import pytest

from pages_site import install_routes, pages_root, release_tree, serve, watch

sync_api = pytest.importorskip("playwright.sync_api")
NAME = "dfs-dupe"
POS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    tree = release_tree(tmp_path_factory.mktemp("release"), NAME)
    assert "{{" + "LIVE_URL}}" not in (tree / "README.md").read_text(encoding="utf-8")
    with serve(pages_root(tree), NAME) as url:
        yield url


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


def setv(page, i, v):
    page.evaluate("([i,v]) => { var e = document.getElementById(i); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); }", [i, v])


def test_example_numbers_and_remembered_contest(site, browser):
    errors: list = []
    ctx = browser.new_context()
    install_routes(ctx, site.split("/" + NAME)[0], errors)
    page = ctx.new_page()
    watch(page, errors)
    page.goto(site)
    page.wait_for_selector("#t-e")
    assert page.inner_text("#t-e") == "0.63" and page.inner_text("#t-u") == "53.1%"
    assert page.inner_text("#t-pay") == "$85,735.88"
    assert "once" in page.inner_text("#contest-note")
    setv(page, "field-n", "20000")
    setv(page, "prize-0", "200000")
    page.reload()
    page.wait_for_selector("#t-e")
    assert page.input_value("#field-n") == "20000" and page.input_value("#prize-0") == "200000"
    assert "last time" in page.inner_text("#contest-note")
    assert page.evaluate("() => window.__csp") == []
    assert errors == []
    ctx.close()


def test_json_file_with_bad_field_size_is_reported(site, browser, tmp_path):
    errors: list = []
    ctx = browser.new_context(viewport={"width": 400, "height": 800}, has_touch=True, is_mobile=True)
    install_routes(ctx, site.split("/" + NAME)[0], errors)
    page = ctx.new_page()
    watch(page, errors)
    page.goto(site)
    page.wait_for_selector("#t-e")
    players = [dict(name=f"J{i}", position=p, ownership=12, salary=5000) for i, p in enumerate(POS)]
    f = tmp_path / "lineup.json"
    f.write_text(json.dumps({"players": players, "field_size": "lots"}), encoding="utf-8")
    page.set_input_files("#file-in", str(f))
    page.wait_for_function("() => document.getElementById('status').classList.contains('bad')")
    assert "field_size" in page.inner_text("#status")
    f.write_text(json.dumps({"players": players, "field_size": 5000, "prizes": [1000, 500]}), encoding="utf-8")
    page.set_input_files("#file-in", str(f))
    page.wait_for_function("() => /Lineup is legal/.test(document.getElementById('status').textContent)")
    assert page.input_value("#field-n") == "5000"
    assert page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0
    assert errors == []
    ctx.close()
