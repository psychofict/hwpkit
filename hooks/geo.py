"""Build-time helpers for the site's search and AI-answer data.

MkDocs runs this through `hooks:` in mkdocs.yml. It adds nothing to the build's
dependencies: only the standard library.

* The home page's FAQ is written once, as `<details class="faq-item">` entries in
  docs/index.md. The FAQPage data is read back out of that rendered HTML, so the
  structured data cannot say anything the visitor does not see.
* `dateModified` is the date of the last commit that touched a page's source file.
  It is never the build date: the docs are redeployed on every push to main, and a
  rebuild that changes a page must not make every other page look newly edited. When
  git history is not available the field is left out rather than guessed.
* /feed.xml lists the blog posts, each dated by its own front matter `date`.
"""

from __future__ import annotations

import datetime as dt
import html
import re
import subprocess
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

# `question` is Material's own admonition class, which gives each entry its "?" icon.
FAQ_ITEM = re.compile(
    r'<details class="faq-item[^"]*">\s*<summary>(.*?)</summary>\s*<p>(.*?)</p>\s*</details>', re.S
)
_posts: dict[str, dict] = {}


def _plain(fragment: str) -> str:
    """The text a visitor reads: tags dropped, entities decoded, whitespace folded."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def _last_commit_date(config, source: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(source)],
            cwd=Path(config.config_file_path).parent,
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out or None


def _as_date(value) -> dt.date | None:
    if isinstance(value, dict):  # the blog plugin may nest it as {created: ...}
        value = value.get("created") or next(iter(value.values()), None)
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def on_page_content(content, page, config, files):
    items = [{"q": _plain(q), "a": _plain(a)} for q, a in FAQ_ITEM.findall(content)]
    if items:
        page.meta["faq"] = items
    modified = _last_commit_date(config, Path(page.file.abs_src_path))
    if modified:
        page.meta["modified"] = modified
    return content


def on_page_context(context, page, config, nav):
    if page.file.src_uri.startswith("blog/posts/"):
        published = _as_date(page.meta.get("date"))
        if published:
            _posts[page.canonical_url] = {
                "title": page.title,
                "url": page.canonical_url,
                "date": published,
                "description": page.meta.get("description", ""),
            }
    return context


def on_post_build(config):
    # Google never read /sitemap.xml after it was submitted on 2026-10-05, although it
    # serves 200 and valid XML; the same file under a second name is submitted as well.
    sitemap = Path(config.site_dir) / "sitemap.xml"
    if sitemap.exists():
        (Path(config.site_dir) / "sitemap-pages.xml").write_bytes(sitemap.read_bytes())

    posts = sorted(_posts.values(), key=lambda p: (p["date"], p["url"]), reverse=True)
    out = Path(config.site_dir) / "feed.xml"
    if len(posts) < 2:  # a feed of one entry is not worth advertising
        out.unlink(missing_ok=True)
        return
    stamp = lambda d: format_datetime(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc), usegmt=True)
    base = config.site_url
    items = "\n".join(
        f"  <item>\n    <title>{escape(p['title'])}</title>\n    <link>{escape(p['url'])}</link>\n"
        f"    <guid isPermaLink=\"true\">{escape(p['url'])}</guid>\n    <pubDate>{stamp(p['date'])}</pubDate>\n"
        f"    <description>{escape(_plain(p['description']))}</description>\n  </item>"
        for p in posts
    )
    out.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n<channel>\n'
        f"  <title>{escape(config.site_name)}</title>\n  <link>{escape(base)}</link>\n"
        f"  <description>{escape(_plain(config.site_description))}</description>\n"
        f"  <language>en</language>\n  <lastBuildDate>{stamp(posts[0]['date'])}</lastBuildDate>\n"
        f'  <atom:link href="{escape(base)}feed.xml" rel="self" type="application/rss+xml"/>\n'
        f"{items}\n</channel>\n</rss>\n",
        encoding="utf-8",
    )
