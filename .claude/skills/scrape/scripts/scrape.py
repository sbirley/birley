#!/usr/bin/env python3
"""Fetch web pages and turn them into clean Markdown, plain text, or JSON.

Standard library only. Respects robots.txt by default, can crawl links within
a site, and can save each page to its own file (handy for NotebookLM sources).
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
import zlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

DEFAULT_UA = 'Mozilla/5.0 (compatible; birley-scrape/0.1; +https://github.com/sbirley/birley)'
MAX_BYTES = 15 * 1024 * 1024

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
        'param', 'source', 'track', 'wbr'}
DROP = {'script', 'style', 'noscript', 'template', 'svg', 'canvas', 'iframe', 'object',
        'head', 'button', 'select', 'textarea', 'input'}
BLOCK = {'address', 'article', 'aside', 'blockquote', 'details', 'dialog', 'dd', 'div',
         'dl', 'dt', 'fieldset', 'figcaption', 'figure', 'footer', 'form', 'h1', 'h2',
         'h3', 'h4', 'h5', 'h6', 'header', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'pre',
         'section', 'summary', 'table', 'ul'}
# Opening one of these closes an open element of the same group (li closes li, etc.).
AUTO_CLOSE = {'li': {'li'}, 'dt': {'dt', 'dd'}, 'dd': {'dt', 'dd'}, 'tr': {'tr'},
              'td': {'td', 'th'}, 'th': {'td', 'th'}, 'option': {'option'}}
SCOPE_STOP = {'ul', 'ol', 'dl', 'table', 'tbody', 'thead', 'tfoot', 'select'}
BOILERPLATE_HINT = re.compile(
    r'(^|[\s_-])(nav|navbar|menu|breadcrumbs?|cookie|consent|banner|sidebar|footer|'
    r'share|social|newsletter|subscribe|advert|ads?|promo|related|comments?|modal|popup|'
    r'skip-link|sr-only|visually-hidden|screen-reader-text|noprint|no-print|mw-editsection|'
    r'ambox|navbox|headerlink|anchor-link|heading-anchor)'
    r'($|[\s_-])', re.I)


# --------------------------------------------------------------------------- DOM

class Node:
    __slots__ = ('tag', 'attrs', 'children', 'parent')

    def __init__(self, tag: str, attrs: dict | None = None, parent: Node | None = None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list[Node | str] = []
        self.parent = parent

    def iter(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.iter()

    def text(self) -> str:
        parts = []
        for child in self.children:
            parts.append(child if isinstance(child, str) else child.text())
        return ''.join(parts)

    @property
    def classes(self) -> list[str]:
        return (self.attrs.get('class') or '').split()


class TreeBuilder(HTMLParser):
    """Forgiving HTML -> Node tree. Handles void tags and common implicit closes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#root')
        self.stack = [self.root]

    @property
    def cur(self) -> Node:
        return self.stack[-1]

    def _close_until(self, index: int):
        del self.stack[index:]

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        closes = AUTO_CLOSE.get(tag)
        if closes:
            for i in range(len(self.stack) - 1, 0, -1):
                t = self.stack[i].tag
                if t in closes:
                    self._close_until(i)
                    break
                if t in SCOPE_STOP:
                    break
        if tag in BLOCK:
            for i in range(len(self.stack) - 1, 0, -1):
                if self.stack[i].tag == 'p':
                    self._close_until(i)
                    break
                if self.stack[i].tag in BLOCK:
                    break
        node = Node(tag, {k.lower(): (v or '') for k, v in attrs}, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID and self.cur.tag == tag.lower():
            self.stack.pop()

    def handle_endtag(self, tag):
        tag = tag.lower()
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self._close_until(i)
                return

    def handle_data(self, data):
        if data:
            self.cur.children.append(data)


def parse_html(html: str) -> Node:
    builder = TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


# ------------------------------------------------------------------ selectors

LIST_ITEM = re.compile(r'^(-|\d+\.) ')
_SIMPLE = re.compile(r'^([a-zA-Z][\w-]*)?((?:[#.][\w-]+)*)$')


def _matches(node: Node, simple: str) -> bool:
    m = _SIMPLE.match(simple)
    if not m:
        raise ValueError(f'Unsupported selector part: {simple!r}')
    tag, rest = m.group(1), m.group(2)
    if tag and node.tag != tag.lower():
        return False
    for kind, name in re.findall(r'([#.])([\w-]+)', rest):
        if kind == '#' and node.attrs.get('id') != name:
            return False
        if kind == '.' and name not in node.classes:
            return False
    return True


def validate_selector(selector: str) -> None:
    parts = [part for group in selector.split(',') for part in group.split()]
    if not parts:
        raise ValueError('empty selector')
    for part in parts:
        if not _SIMPLE.match(part):
            raise ValueError(f'unsupported selector part {part!r} '
                             '(use tag, .class, #id, tag.class, descendants, commas)')


def select(root: Node, selector: str) -> list[Node]:
    """Tiny CSS subset: `tag`, `.class`, `#id`, `tag.a.b`, descendant (space), lists (comma)."""
    results: list[Node] = []
    taken: set[int] = set()
    for group in selector.split(','):
        parts = group.split()
        if not parts:
            continue
        current = [root]
        for part in parts:
            found, ids = [], set()
            for base in current:
                for node in base.iter():
                    if node is not base and id(node) not in ids and _matches(node, part):
                        ids.add(id(node))
                        found.append(node)
            current = found
        for node in current:
            if id(node) not in taken:
                taken.add(id(node))
                results.append(node)
    return results


# ------------------------------------------------------------------ extraction

def _is_boilerplate(node: Node) -> bool:
    """Navigation, site chrome, cookie banners and the like. Errs on the side of keeping text."""
    attrs = node.attrs
    if attrs.get('aria-hidden') == 'true' or 'hidden' in attrs:
        return True
    if re.search(r'display\s*:\s*none', attrs.get('style', ''), re.I):
        return True
    role = attrs.get('role', '')
    if node.tag == 'nav' or role in ('navigation', 'search', 'dialog'):
        return True
    semantic = node.tag in ('header', 'footer', 'aside') or role in (
        'banner', 'contentinfo', 'complementary')
    hinted = bool(BOILERPLATE_HINT.search(' '.join(node.classes + [attrs.get('id', '')])))
    if not (semantic or hinted):
        return False
    # An article's own <header> usually holds its title; never drop real content wrappers.
    if any(n.tag in ('main', 'article', 'h1') for n in node.iter() if n is not node):
        return False
    # Class names are only a hint ("page-with-sidebar"); keep big blocks of text.
    return semantic or len(node.text()) < 3000


def find_main(root: Node) -> Node:
    body = next((n for n in root.iter() if n.tag == 'body'), root)
    candidates = [n for n in root.iter() if n.tag in ('main', 'article') or n.attrs.get('role') == 'main']
    if candidates:
        best = max(candidates, key=lambda n: len(n.text()))
        # Some sites wrap only a sliver of the page in <main>; fall back to the body then.
        main_len, body_len = len(best.text().strip()), len(body.text().strip())
        if main_len >= 500 or main_len >= 0.25 * body_len:
            return best
    return body


def page_meta(root: Node) -> dict:
    meta = {'title': '', 'description': '', 'canonical': '', 'lang': ''}
    titles = select(root, 'title')
    if titles:
        meta['title'] = ' '.join(titles[0].text().split())
    for node in root.iter():
        if node.tag == 'meta':
            key = (node.attrs.get('name') or node.attrs.get('property') or '').lower()
            content = node.attrs.get('content', '').strip()
            if key in ('description', 'og:description') and not meta['description']:
                meta['description'] = content
            elif key == 'og:title' and not meta['title']:
                meta['title'] = content
        elif node.tag == 'link' and 'canonical' in node.attrs.get('rel', '').lower().split():
            meta['canonical'] = node.attrs.get('href', '')
        elif node.tag == 'html' and node.attrs.get('lang'):
            meta['lang'] = node.attrs['lang']
    if not meta['title']:
        h1 = select(root, 'h1')
        if h1:
            meta['title'] = ' '.join(h1[0].text().split())
    return meta


def page_links(root: Node, base: str) -> list[dict]:
    seen, links = set(), []
    for node in root.iter():
        if node.tag != 'a':
            continue
        href = node.attrs.get('href', '').strip()
        if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
            continue
        url = urldefrag(urljoin(base, href))[0]
        if urlparse(url).scheme not in ('http', 'https') or url in seen:
            continue
        seen.add(url)
        links.append({'url': url, 'text': ' '.join(node.text().split())})
    return links


# ------------------------------------------------------------------ rendering

class MarkdownRenderer:
    def __init__(self, base: str, keep_boilerplate: bool = False, images: bool = True,
                 plain: bool = False):
        self.base = base
        self.keep_boilerplate = keep_boilerplate
        self.images = images
        self.plain = plain

    def url(self, href: str) -> str:
        return urljoin(self.base, href.strip()) if href else ''

    # inline ----------------------------------------------------------------
    def inline(self, node: Node | str, pre: bool = False) -> str:
        if isinstance(node, str):
            return node if pre else re.sub(r'\s+', ' ', node)
        tag = node.tag
        if tag in DROP or (not self.keep_boilerplate and _is_boilerplate(node)):
            return ''
        if tag == 'br':
            return '\n'
        if tag == 'img':
            if not self.images or self.plain:
                return node.attrs.get('alt', '')
            src = self.url(node.attrs.get('src') or node.attrs.get('data-src', ''))
            return f'![{node.attrs.get("alt", "").strip()}]({src})' if src else ''
        inner = ''.join(self.inline(c, pre) for c in node.children)
        if pre or self.plain:
            return inner
        stripped = inner.strip()
        if not stripped:
            return inner
        lead = ' ' if inner[:1].isspace() else ''
        trail = ' ' if inner[-1:].isspace() else ''
        if tag == 'a':
            href = node.attrs.get('href', '')
            if href and not href.startswith(('javascript:', '#')):
                return f'{lead}[{stripped}]({self.url(href)}){trail}'
        elif tag in ('strong', 'b'):
            return f'{lead}**{stripped}**{trail}'
        elif tag in ('em', 'i'):
            return f'{lead}*{stripped}*{trail}'
        elif tag in ('del', 's', 'strike'):
            return f'{lead}~~{stripped}~~{trail}'
        elif tag == 'code' and not pre:
            tick = '``' if '`' in stripped else '`'
            return f'{lead}{tick}{stripped}{tick}{trail}'
        return inner

    # blocks ----------------------------------------------------------------
    def blocks(self, node: Node) -> list[str]:
        """Render children of `node` into a list of Markdown blocks."""
        out: list[str] = []
        buf: list[str] = []

        def flush():
            text = ''.join(buf)
            text = '\n'.join(line.strip() for line in text.split('\n'))
            text = re.sub(r'[ \t]+', ' ', text).strip()
            if text:
                out.append(text)
            buf.clear()

        for child in node.children:
            if isinstance(child, str) or (child.tag not in BLOCK and child.tag not in
                                          ('pre', 'table', 'tr', 'td', 'th', 'tbody', 'thead',
                                           'body', 'html', 'center')):
                buf.append(self.inline(child))
                continue
            flush()
            out.extend(self.block(child))
        flush()
        return out

    def block(self, node: Node) -> list[str]:
        tag = node.tag
        if tag in DROP or (not self.keep_boilerplate and _is_boilerplate(node)):
            return []
        if re.fullmatch(r'h[1-6]', tag):
            text = ' '.join(self.inline(node).split())
            if not text:
                return []
            return [text if self.plain else f'{"#" * int(tag[1])} {text}']
        if tag == 'hr':
            return [] if self.plain else ['---']
        if tag == 'pre':
            code = ''.join(self.inline(c, pre=True) for c in node.children).strip('\n')
            if not code.strip():
                return []
            if self.plain:
                return [code]
            lang = ''
            for n in node.iter():
                for cls in n.classes:
                    if cls.startswith(('language-', 'lang-')):
                        lang = cls.split('-', 1)[1]
                        break
            fence = '````' if '```' in code else '```'
            return [f'{fence}{lang}\n{code}\n{fence}']
        if tag in ('ul', 'ol'):
            return self.list_block(node)
        if tag == 'blockquote':
            inner = self.blocks(node)
            if self.plain:
                return inner
            text = '\n\n'.join(inner)
            return ['\n'.join('> ' + line if line else '>' for line in text.split('\n'))] if text else []
        if tag == 'table':
            return self.table_block(node)
        if tag == 'dl':
            items = []
            for child in node.children:
                if not isinstance(child, Node) or child.tag not in ('dt', 'dd'):
                    continue
                text = ' '.join(self.inline(child).split())
                if not text:
                    continue
                if child.tag == 'dd':
                    items.append(f': {text}')
                else:
                    items.append(text if self.plain else f'**{text}**')
            return ['\n'.join(items)] if items else []
        return self.blocks(node)

    def list_block(self, node: Node) -> list[str]:
        # Each item renders independently; nested lists are indented under their marker.
        lines = []
        index = int(node.attrs.get('start') or 1) if node.tag == 'ol' else 0
        for child in node.children:
            if not isinstance(child, Node) or child.tag != 'li':
                continue
            marker = '-' if node.tag == 'ul' else f'{index}.'
            if node.tag == 'ol':
                index += 1
            parts = self.blocks(child)
            if not parts:
                continue
            text = parts[0]
            for part in parts[1:]:
                text += ('\n' if LIST_ITEM.match(part) else '\n\n') + part
            pad = ' ' * (len(marker) + 1)
            first, *rest = text.split('\n')
            lines.append(f'{marker} {first}')
            lines.extend(pad + line if line else '' for line in rest)
        return ['\n'.join(lines)] if lines else []

    def table_block(self, node: Node) -> list[str]:
        rows = []
        for tr in node.iter():
            if tr.tag != 'tr':
                continue
            # skip rows of nested tables
            p = tr.parent
            while p is not None and p.tag != 'table':
                p = p.parent
            if p is not node:
                continue
            cells = [c for c in tr.children if isinstance(c, Node) and c.tag in ('td', 'th')]
            if cells:
                texts = [' '.join(self.inline(c).split()) for c in cells]
                rows.append(texts if self.plain else [t.replace('|', '\\|') for t in texts])
        if not rows:
            return []
        if self.plain:
            return ['\n'.join('\t'.join(r) for r in rows)]
        width = max(len(r) for r in rows)
        rows = [r + [''] * (width - len(r)) for r in rows]
        lines = ['| ' + ' | '.join(rows[0]) + ' |', '|' + ' --- |' * width]
        lines += ['| ' + ' | '.join(r) + ' |' for r in rows[1:]]
        return ['\n'.join(lines)]

    def render(self, node: Node) -> str:
        if node.tag in ('ul', 'ol', 'table', 'pre', 'blockquote', 'dl') or re.fullmatch(r'h[1-6]', node.tag):
            parts = self.block(node)
        else:
            parts = self.blocks(node)
        text = '\n\n'.join(p for p in parts if p.strip())
        return re.sub(r'\n{3,}', '\n\n', text).strip() + '\n'


# ------------------------------------------------------------------ fetching

@dataclass
class Page:
    url: str
    final_url: str = ''
    status: int = 0
    content_type: str = ''
    title: str = ''
    description: str = ''
    lang: str = ''
    content: str = ''
    links: list = field(default_factory=list)
    fetched_at: str = ''
    error: str = ''


def decode_body(raw: bytes, content_type: str) -> str:
    m = re.search(r'charset=["\']?([\w-]+)', content_type, re.I)
    charset = m.group(1) if m else None
    if not charset:
        head = raw[:4096].decode('ascii', errors='ignore')
        m = re.search(r'<meta[^>]+charset=["\']?([\w-]+)', head, re.I)
        charset = m.group(1) if m else 'utf-8'
    try:
        return raw.decode(charset, errors='replace')
    except LookupError:
        return raw.decode('utf-8', errors='replace')


def fetch(url: str, user_agent: str, timeout: float) -> tuple[int, str, str, bytes]:
    req = urllib.request.Request(url, headers={
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en;q=0.9,*;q=0.5',
    })
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        resp = exc
    with resp:
        raw = resp.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError(f'response larger than {MAX_BYTES // (1024 * 1024)} MB')
        encoding = (resp.headers.get('Content-Encoding') or '').lower()
        if encoding == 'gzip':
            raw = gzip.decompress(raw)
        elif encoding == 'deflate':
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        return resp.status, resp.geturl(), resp.headers.get('Content-Type', ''), raw


class Robots:
    def __init__(self, user_agent: str, timeout: float, enabled: bool):
        self.user_agent, self.timeout, self.enabled = user_agent, timeout, enabled
        self.cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        if not self.enabled:
            return True
        parts = urlparse(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in self.cache:
            parser = urllib.robotparser.RobotFileParser()
            try:
                status, _, _, raw = fetch(origin + '/robots.txt', self.user_agent, self.timeout)
                if status >= 400:
                    parser = None  # no robots.txt (or unreadable): allow
                else:
                    parser.parse(raw.decode('utf-8', errors='replace').splitlines())
            except Exception:
                parser = None
            self.cache[origin] = parser
        parser = self.cache[origin]
        return parser is None or parser.can_fetch(self.user_agent, url)


def to_page(url: str, final_url: str, status: int, ctype: str, body: str, opts) -> Page:
    page = Page(url=url, final_url=final_url, status=status, content_type=ctype.split(';')[0],
                fetched_at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    if 'html' not in ctype and not body.lstrip().lower().startswith(('<!doctype html', '<html')):
        page.content = body
        return page
    root = parse_html(body)
    meta = page_meta(root)
    page.title, page.description, page.lang = meta['title'], meta['description'], meta['lang']
    page.links = page_links(root, final_url)
    if opts.format == 'html':
        page.content = body
        return page
    if opts.select:
        targets = select(root, opts.select)
        if not targets:
            page.error = f'selector {opts.select!r} matched nothing'
    elif opts.full_page:
        body_nodes = select(root, 'body')
        targets = body_nodes[:1] or [root]
    else:
        targets = [find_main(root)]
    renderer = MarkdownRenderer(final_url, keep_boilerplate=opts.full_page or bool(opts.select),
                                images=not opts.no_images, plain=opts.format == 'text')
    content = '\n'.join(renderer.render(t) for t in targets).strip()
    page.content = content + '\n' if content else ''
    return page


def scrape(urls: list[str], opts, log=lambda msg: print(msg, file=sys.stderr)) -> list[Page]:
    robots = Robots(opts.user_agent, opts.timeout, not opts.ignore_robots)
    include = re.compile(opts.include) if opts.include else None
    exclude = re.compile(opts.exclude) if opts.exclude else None
    start_hosts = {urlparse(u).netloc for u in urls}
    queue = [(u, 0) for u in urls]
    seen: set[str] = set()
    pages: list[Page] = []
    last_fetch = 0.0
    while queue and len(pages) < opts.max_pages:
        url, depth = queue.pop(0)
        url = urldefrag(url)[0]
        if url in seen:
            continue
        seen.add(url)
        if not robots.allowed(url):
            log(f'skip (robots.txt): {url}')
            pages.append(Page(url=url, error='disallowed by robots.txt'))
            continue
        wait = opts.delay - (time.monotonic() - last_fetch)
        if last_fetch and wait > 0:
            time.sleep(wait)
        last_fetch = time.monotonic()
        log(f'fetch [{len(pages) + 1}] {url}')
        try:
            status, final_url, ctype, raw = fetch(url, opts.user_agent, opts.timeout)
        except Exception as exc:  # network errors, timeouts, decode failures
            log(f'  error: {exc}')
            pages.append(Page(url=url, error=f'{type(exc).__name__}: {exc}'))
            continue
        if status >= 400:
            log(f'  HTTP {status}')
        if 'pdf' in ctype or raw[:5] == b'%PDF-':
            pages.append(Page(url=url, final_url=final_url, status=status, content_type='application/pdf',
                              error='PDF: not converted (download it and use a PDF tool)'))
            continue
        page = to_page(url, final_url, status, ctype, decode_body(raw, ctype), opts)
        if status >= 400 and not page.error:
            page.error = f'HTTP {status}'
        pages.append(page)
        seen.add(urldefrag(final_url)[0])
        if depth == 0:  # follow redirects like example.com -> www.example.com
            start_hosts.add(urlparse(final_url).netloc)
        if opts.crawl and depth < opts.depth and status < 400:
            for link in page.links:
                target = link['url']
                if target in seen:
                    continue
                if not opts.any_domain and urlparse(target).netloc not in start_hosts:
                    continue
                if include and not include.search(target):
                    continue
                if exclude and exclude.search(target):
                    continue
                if re.search(r'\.(jpe?g|png|gif|webp|svg|ico|css|js|zip|gz|mp[34]|mov|avi|woff2?)(\?|$)',
                             target, re.I):
                    continue
                queue.append((target, depth + 1))
    return pages


# ------------------------------------------------------------------ output

def as_markdown(page: Page, links: bool) -> str:
    if page.error and not page.content:
        return f'<!-- {page.url}: {page.error} -->\n'
    header = []
    if page.title and not page.content.startswith(f'# {page.title}\n'):
        header.append(f'# {page.title}')
    header.append(f'Source: {page.final_url or page.url}')
    if page.description:
        header.append(f'> {page.description}')
    out = '\n\n'.join(header) + '\n\n' + page.content
    if links and page.links:
        out += '\n## Links\n\n' + '\n'.join(
            f'- [{l["text"] or l["url"]}]({l["url"]})' for l in page.links) + '\n'
    return out


def as_text(page: Page, links: bool) -> str:
    if page.error and not page.content:
        return f'[{page.url}: {page.error}]\n'
    out = (f'{page.title}\n' if page.title else '') + f'Source: {page.final_url or page.url}\n\n'
    out += page.content
    if links and page.links:
        out += '\nLinks:\n' + '\n'.join(f'{l["url"]}  {l["text"]}' for l in page.links) + '\n'
    return out


def slug(url: str) -> str:
    parts = urlparse(url)
    path = parts.path.strip('/') or 'index'
    if parts.query:
        path += '-' + parts.query
    name = re.sub(r'[^\w.-]+', '-', f'{parts.netloc}-{path}').strip('-')
    return name[:150] or 'page'


def write_outputs(pages: list[Page], opts) -> None:
    ext = {'markdown': 'md', 'text': 'txt', 'json': 'json', 'html': 'html'}[opts.format]
    render = {'markdown': as_markdown, 'text': as_text}.get(opts.format)

    def body(page: Page) -> str:
        if opts.format == 'json':
            data = asdict(page)
            if not opts.links:
                data.pop('links')
            return json.dumps(data, ensure_ascii=False, indent=2) + '\n'
        if opts.format == 'html':
            return page.content
        return render(page, opts.links)

    if opts.out:
        out_dir = Path(opts.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        used: set[str] = set()
        index = []
        for page in pages:
            if page.error and not page.content:
                index.append({'url': page.url, 'error': page.error})
                continue
            name = slug(page.final_url or page.url)
            base, n = name, 2
            while name in used:
                name, n = f'{base}-{n}', n + 1
            used.add(name)
            path = out_dir / f'{name}.{ext}'
            path.write_text(body(page), encoding='utf-8')
            index.append({'url': page.url, 'file': str(path), 'title': page.title,
                          **({'error': page.error} if page.error else {})})
        (out_dir / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n',
                                            encoding='utf-8')
        print(json.dumps({'saved': sum('file' in i for i in index), 'failed':
                          sum('file' not in i for i in index), 'dir': str(out_dir),
                          'index': str(out_dir / 'index.json')}, indent=2))
        return

    if opts.format == 'json':
        data = [json.loads(body(p)) for p in pages]
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        sep = '\n\n' + ('-' * 72) + '\n\n'
        print(sep.join(body(p).rstrip('\n') for p in pages))


# ------------------------------------------------------------------ CLI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='scrape.py', description='Scrape web pages into clean Markdown, text, or JSON.')
    p.add_argument('urls', nargs='*', help='page URLs (http/https)')
    p.add_argument('-i', '--input', help='file with one URL per line (# comments allowed)')
    p.add_argument('-f', '--format', choices=('markdown', 'text', 'json', 'html'), default='markdown')
    p.add_argument('-s', '--select', help='CSS-like selector to extract, e.g. "article", ".post-body", "#main h2"')
    p.add_argument('--full-page', action='store_true', help='keep the whole <body>, including nav/header/footer')
    p.add_argument('--links', action='store_true', help='include a list of links found on each page')
    p.add_argument('--no-images', action='store_true', help='drop images from Markdown output')
    p.add_argument('-o', '--out', help='directory to save one file per page (plus index.json)')
    crawl = p.add_argument_group('crawling')
    crawl.add_argument('--crawl', action='store_true', help='follow links from the start pages')
    crawl.add_argument('--depth', type=int, default=1, help='link depth when crawling (default 1)')
    crawl.add_argument('--max-pages', type=int, default=None, help='stop after N pages (default: 1 per URL, or 25 when crawling)')
    crawl.add_argument('--include', help='only follow links matching this regex')
    crawl.add_argument('--exclude', help='never follow links matching this regex')
    crawl.add_argument('--any-domain', action='store_true', help='follow links to other domains too')
    net = p.add_argument_group('network')
    net.add_argument('--delay', type=float, default=1.0, help='seconds between requests (default 1.0)')
    net.add_argument('--timeout', type=float, default=20.0, help='per-request timeout in seconds')
    net.add_argument('--user-agent', default=DEFAULT_UA)
    net.add_argument('--ignore-robots', action='store_true', help='do not check robots.txt')
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
        except (AttributeError, OSError, ValueError):
            pass
    parser = build_parser()
    opts = parser.parse_args(argv)
    urls = list(opts.urls)
    if opts.input:
        lines = Path(opts.input).read_text(encoding='utf-8').splitlines()
        urls += [l.strip() for l in lines if l.strip() and not l.lstrip().startswith('#')]
    if not urls:
        parser.error('give at least one URL (or --input FILE)')
    for i, url in enumerate(urls):
        if '://' not in url:
            urls[i] = url = 'https://' + url
        if urlparse(url).scheme not in ('http', 'https'):
            parser.error(f'not an http(s) URL: {url}')
    if opts.depth < 0 or (opts.max_pages is not None and opts.max_pages < 1):
        parser.error('--depth must be >= 0 and --max-pages >= 1')
    if opts.max_pages is None:
        opts.max_pages = 25 if opts.crawl else len(urls)
    if opts.select:
        try:
            validate_selector(opts.select)
        except ValueError as exc:
            parser.error(str(exc))
    pages = scrape(urls, opts)
    write_outputs(pages, opts)
    return 0 if any(not p.error or p.content for p in pages) else 1


if __name__ == '__main__':
    sys.exit(main())
