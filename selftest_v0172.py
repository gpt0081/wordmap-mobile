#!/usr/bin/env python3

import launch


def main():
    html = launch.wordmap_mobile.HTML
    assert 'wuChatPatch0172' in html
    assert 'wuDeleteHistoryBtn' in html
    assert '대화내역 삭제' in html
    assert 'overflow-wrap:anywhere' in html
    assert 'flex-wrap:wrap' in html
    assert "api('/api/dialogue/start','POST'" in html
    assert 'Utility Workspace · v0.17.2' in html
    print('WordMap v0.17.2 chat history/wrapping self-test: OK')


if __name__ == '__main__':
    main()
