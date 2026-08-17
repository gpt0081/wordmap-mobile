#!/usr/bin/env python3

from types import SimpleNamespace

import workspace_ui


def main():
    dummy = SimpleNamespace(
        HTML="""<!doctype html><html><head><title>x</title></head><body><main><h1>x</h1><section class='card'><h2>Vault</h2></section><section class='card'><h2>1. 말뭉치 → WordMap</h2></section><section class='card'><h2>2. 질문 → 연결 단어</h2><textarea id='q'></textarea><div id='results'></div></section></main></body></html>"""
    )
    workspace_ui.apply(dummy)
    html = dummy.HTML
    assert workspace_ui.VERSION == "0.17.0"
    assert 'id="wuStyles"' in html
    assert 'id="wuScript"' in html
    assert "Utility Workspace" in html
    assert "wordmap_ui_tab" in html
    assert "wuBottomNav" in html
    assert "wuChatHero" in html
    assert "wuDebugDetails" in html
    assert "내부 분석 보기" in html
    assert "Ctrl" not in html or "askQ" in html
    assert "workspace_ui" not in html.lower()
    print("WordMap v0.17.0 utility workspace UI self-test: OK")


if __name__ == "__main__":
    main()
