"""Offline tests for the /scrape skill's HTML -> Markdown extraction."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.claude' / 'skills' / 'scrape' / 'scripts'))

import scrape  # noqa: E402

BASE = 'https://example.com/post'

PAGE = """<!doctype html><html lang="en"><head>
<title>Test Page</title><meta name="description" content="A description">
<script>var tracking = 1;</script><style>p { color: red }</style></head>
<body>
<nav class="navbar"><a href="/">Home</a></nav>
<div class="cookie-banner">We use cookies</div>
<form id="aspnetForm"><main><article>
<header><h1>Big Title</h1><p class="byline">By someone</p></header>
<p>First <b>bold</b> and <a href="/x?y=1#frag">a link</a>. <code>x = 1</code>
<p>Second paragraph
<ul><li>one<li>two<ul><li>nested a</li><li>nested b</li></ul><li>three</ul>
<ol start="3"><li>three</li><li>four</li></ol>
<pre><code class="language-python">def f():
    return 1</code></pre>
<table class="data"><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>x|y</td></tr></table>
<blockquote><p>Quoted</p></blockquote>
<img src="/img.png" alt="pic">
</article></main></form>
<footer>Copyright</footer>
</body></html>"""


def opts(**kw):
    defaults = dict(format='markdown', select=None, full_page=False, no_images=False)
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def page(html=PAGE, **kw):
    return scrape.to_page(BASE, BASE, 200, 'text/html; charset=utf-8', html, opts(**kw))


def test_metadata_and_links():
    p = page()
    assert p.title == 'Test Page'
    assert p.description == 'A description'
    assert p.lang == 'en'
    urls = [link['url'] for link in p.links]
    assert urls == ['https://example.com/', 'https://example.com/x?y=1']


def test_markdown_keeps_content_and_drops_chrome():
    md = page().content
    assert '# Big Title' in md  # article header is kept
    assert 'First **bold** and [a link](https://example.com/x?y=1#frag). `x = 1`' in md
    assert '- two\n  - nested a\n  - nested b\n- three' in md
    assert '3. three\n4. four' in md
    assert '```python\ndef f():\n    return 1\n```' in md
    assert '| A | B |\n| --- | --- |\n| 1 | x\\|y |' in md
    assert '> Quoted' in md
    assert '![pic](https://example.com/img.png)' in md
    for chrome in ('Home', 'cookies', 'Copyright', 'tracking', 'color: red'):
        assert chrome not in md


def test_text_format_has_no_markup():
    text = page(format='text').content
    assert 'First bold and a link. x = 1' in text
    assert '**' not in text and '](' not in text and '```' not in text
    assert 'A\tB\n1\tx|y' in text


def test_full_page_keeps_chrome():
    md = page(full_page=True).content
    assert 'Copyright' in md and 'Home' in md


def test_select():
    md = page(select='table.data, .byline').content
    assert md.startswith('| A | B |')
    assert md.rstrip().endswith('By someone')
    assert 'First' not in md


def test_select_no_match_reports_error():
    p = page(select='#missing')
    assert p.error and not p.content


def test_validate_selector():
    scrape.validate_selector('div.post p, #main, h2')
    with pytest.raises(ValueError):
        scrape.validate_selector('div > p')


def test_short_main_falls_back_to_body():
    html = '<body><main><p>Hi</p></main><div>' + 'Real content. ' * 100 + '</div></body>'
    assert 'Real content.' in page(html).content


def test_class_hint_does_not_drop_large_content():
    html = '<body><div class="page-with-sidebar"><p>' + 'Body text. ' * 400 + '</p></div></body>'
    assert 'Body text.' in page(html).content


def test_non_html_passthrough():
    p = scrape.to_page(BASE, BASE, 200, 'text/plain', 'just text', opts())
    assert p.content == 'just text'


def test_decode_body_uses_meta_charset():
    raw = '<meta charset="iso-8859-1"><p>café</p>'.encode('iso-8859-1')
    assert 'café' in scrape.decode_body(raw, 'text/html')


def test_slug():
    assert scrape.slug('https://example.com/a/b.html?x=1') == 'example.com-a-b.html-x-1'
    assert scrape.slug('https://example.com/') == 'example.com-index'
