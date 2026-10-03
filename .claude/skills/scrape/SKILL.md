---
name: scrape
description: Scrape web pages into clean Markdown, plain text, or JSON. Fetches one or more URLs (or crawls a site), strips navigation, ads, and cookie banners, keeps headings, lists, tables, code, links, and images. Respects robots.txt, rate-limits requests, and can save one file per page for NotebookLM sources or later reading. Use when the user asks to scrape, crawl, extract, archive, or pull the content/links/tables out of a website.
license: MIT
allowed-tools: Bash, Read
metadata:
  version: "0.1.0"
---

# /scrape

Run the bundled script. It uses only the Python 3.10+ standard library, so there is nothing to install.

`SKILL_DIR` is the absolute directory containing this SKILL.md; the script is `${SKILL_DIR}/scripts/scrape.py`.

## Quick reference

```bash
# One page -> Markdown on stdout (progress goes to stderr)
python3 "${SKILL_DIR}/scripts/scrape.py" https://example.com/article

# Several pages, or a file of URLs (one per line, # comments allowed)
python3 "${SKILL_DIR}/scripts/scrape.py" URL1 URL2 URL3
python3 "${SKILL_DIR}/scripts/scrape.py" --input urls.txt

# Just one part of the page (tag, .class, #id, tag.class, descendants, commas)
python3 "${SKILL_DIR}/scripts/scrape.py" URL --select "article"
python3 "${SKILL_DIR}/scripts/scrape.py" URL --select "table.prices"

# Structured output with every link on the page
python3 "${SKILL_DIR}/scripts/scrape.py" URL --format json --links

# Crawl a section of a site and save each page to its own file
python3 "${SKILL_DIR}/scripts/scrape.py" https://docs.example.com/guide/ \
  --crawl --depth 2 --max-pages 40 --include '/guide/' --out scraped/guide
```

## Options

| Option | Meaning |
| --- | --- |
| `-f, --format` | `markdown` (default), `text`, `json`, or `html` (raw page source) |
| `-s, --select` | Extract only matching elements. Supports `tag`, `.class`, `#id`, `tag.a.b`, descendant selectors (`div.post p`) and comma lists. No `>`, `:` or `[attr]`. |
| `--full-page` | Keep the whole `<body>`, including nav, header, footer, sidebars |
| `--links` | Append the page's links (Markdown/text) or include a `links` array (JSON) |
| `--no-images` | Drop images from Markdown |
| `-o, --out DIR` | Write one file per page plus `index.json` (url → file, title, error) |
| `--crawl` | Follow links found on the start pages |
| `--depth N` | How many links deep to crawl (default 1) |
| `--max-pages N` | Page cap (default: one per URL, or 25 when crawling) |
| `--include / --exclude REGEX` | Only follow / never follow links matching the regex |
| `--any-domain` | Let the crawl leave the starting site(s) |
| `--delay S` | Seconds between requests (default 1.0) |
| `--timeout S` | Per-request timeout (default 20) |
| `--user-agent UA` | Custom User-Agent |
| `--ignore-robots` | Skip robots.txt checks. Only use when the user owns the site or explicitly asks. |

The exit code is 0 if at least one page produced content, 1 if every page failed, and 2 for bad arguments.

## How to use it well

1. **Start small.** Scrape one page first and read the result before crawling. If the main content is missing or buried, retry with `--select` (look at `--format html` output to find the right container) or `--full-page`.
2. **Pick the format for the job.** Markdown when you or the user will read it; `json` when you need fields (`title`, `description`, `status`, `final_url`, `links`, `error`); `--select "table"` to pull tables out as Markdown tables.
3. **Crawl politely.** Always scope crawls with `--include` and `--max-pages`, and keep the default delay. Tell the user how many pages you plan to fetch before a crawl larger than about 50 pages.
4. **Large output goes to files.** For more than a few pages, use `--out` inside the working directory, then `Read` the files you need instead of flooding the conversation.
5. **Feeding NotebookLM.** Markdown files saved with `--out` can be added as NotebookLM sources (this project depends on `notebooklm-py`).

## Limits

- No JavaScript. Pages that build their content in the browser (many SPAs) come back empty or partial. Say so, and suggest the site's API, RSS feed, or sitemap, or a browser-based tool, instead of retrying.
- PDFs are detected and reported but not converted. Download them and use a PDF tool.
- Pages behind logins, paywalls, CAPTCHAs, or bot protection usually return 401/403 or a challenge page. Do not try to get around these.
- Responses over 15 MB are refused.

## Etiquette and legality

Respect robots.txt (on by default), the site's terms of service, and rate limits. Do not scrape personal data about private individuals, and do not republish copyrighted content wholesale. If the user's goal looks like it crosses those lines, say so before running anything.
