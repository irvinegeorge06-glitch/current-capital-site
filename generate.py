#!/usr/bin/env python3
"""Generate a static HTML page for the Current Capital news site.

This script downloads one or more public RSS feeds, produces concise
summaries of each article and writes an ``index.html`` file into the
current directory. The generated page includes links back to the
original sources to respect copyright and provide full context.

Because the script only uses Python's standard library it requires no
third‑party dependencies. To update the news on your site, simply run
the script again; it will recreate ``index.html`` with the latest
stories.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
import textwrap
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from typing import Iterable, List, Dict


def fetch_rss(url: str, user_agent: str = "Mozilla/5.0") -> str:
    """Download an RSS feed.

    Args:
        url: Full URL to the RSS feed.
        user_agent: Optional user‑agent string to send in the request.

    Returns:
        Raw XML as a string. If the download fails the function returns
        an empty string and prints an error to stderr.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": user_agent})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        print(f"Error fetching {url}: {exc}")
        return ""


def parse_feed(xml_data: str) -> Iterable[Dict[str, str]]:
    """Parse RSS or Atom XML into a stream of articles.

    Each article dictionary contains a title, link, description and
    publication date. Missing fields default to empty strings.
    """
    if not xml_data:
        return []
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        print(f"XML parsing error: {exc}")
        return []

    channel = root.find("channel")
    if channel is not None:
        items = channel.findall("item")
    else:
        items = root.findall("entry")

    for item in items:
        title = item.findtext("title", default="").strip()
        link = item.findtext("link", default="").strip()
        if not link:
            link_elem = item.find("link")
            if link_elem is not None:
                link = link_elem.get("href", "").strip()
        description = item.findtext("description", default="").strip()
        if not description:
            description = item.findtext("content", default="").strip()
        pub_date = item.findtext("pubDate", default="").strip()
        if not pub_date:
            pub_date = item.findtext("updated", default="").strip()
        yield {
            "title": title,
            "link": link,
            "description": description,
            "pub_date": pub_date,
        }


def summarise(text: str, max_words: int = 50) -> str:
    """Return a short summary of a block of text.

    The summary is produced by removing HTML tags, unescaping entities
    and truncating the result to a maximum number of words. If the
    original contains more words than ``max_words`` an ellipsis is
    appended.
    """
    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", "", text)
    clean = unescape(clean)
    words = clean.split()
    summary_words = words[:max_words]
    summary = " ".join(summary_words)
    if len(words) > max_words:
        summary += "..."
    return summary


def build_articles(feed_urls: Iterable[str]) -> List[Dict[str, str]]:
    """Collect and summarise articles from multiple RSS feeds."""
    articles: List[Dict[str, str]] = []
    for url in feed_urls:
        xml = fetch_rss(url)
        for item in parse_feed(xml):
            if not item["title"] or not item["link"]:
                continue
            summary = summarise(item["description"] or item["title"])
            pub_date_str = item["pub_date"]
            pub_datetime: _dt.datetime | None = None
            if pub_date_str:
                for fmt in (
                    "%a, %d %b %Y %H:%M:%S %Z",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%dT%H:%M:%S%z",
                ):
                    try:
                        pub_datetime = _dt.datetime.strptime(pub_date_str, fmt)
                        break
                    except Exception:
                        continue
            articles.append({
                "title": item["title"],
                "link": item["link"],
                "summary": summary,
                "pub_date": pub_datetime,
            })
    # Sort by publication date descending; unknown dates go last
    articles.sort(key=lambda a: a["pub_date"] or _dt.datetime.fromtimestamp(0), reverse=True)
    return articles


HTML_TEMPLATE = textwrap.dedent("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Current Capital – Business &amp; Finance News Summaries</title>
        <link rel="stylesheet" href="style.css">
    </head>
    <body>
        <header class="site-header">
            <h1 class="site-title">Current Capital</h1>
            <p class="tagline">Concise business and finance news with source links</p>
        </header>
        <main class="content">
            {articles_section}
        </main>
        <footer class="site-footer">
            <p>&copy; {year} Current Capital. All rights reserved.</p>
            <p class="credits">News summaries sourced from public feeds such as the BBC and The Guardian.</p>
        </footer>
    </body>
    </html>
""")


def render_articles(articles: List[Dict[str, str]]) -> str:
    """Render the list of articles into an HTML unordered list."""
    if not articles:
        return "<p>No articles available at this time. Please try again later.</p>"
    parts = ["<ul class=\"article-list\">"]
    for article in articles:
        pub_str = ""
        if article["pub_date"]:
            pub_str = article["pub_date"].strftime("%d %b %Y %H:%M")
        parts.append("""
        <li class="article">
            <h2 class="article-title"><a href="{link}" target="_blank" rel="noopener">{title}</a></h2>
            <p class="article-meta">{pub}</p>
            <p class="article-summary">{summary}</p>
            <p class="article-source"><a href="{link}" target="_blank" rel="noopener">Read the full story</a></p>
        </li>
        """.format(link=article["link"], title=article["title"], pub=pub_str, summary=article["summary"]))
    parts.append("</ul>")
    return "\n".join(parts)


def main() -> None:
    """Generate the index.html file."""
    # Define the RSS feeds you want to aggregate. Feel free to add more
    # feeds to this list. Ensure the feeds are public and that you have
    # permission to summarise their content.
    feed_urls = [
        "https://feeds.theguardian.com/theguardian/uk/business/rss",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ]

    articles = build_articles(feed_urls)
    html_articles = render_articles(articles)
    html_output = HTML_TEMPLATE.format(articles_section=html_articles, year=_dt.datetime.now().year)

    # Write the generated page to index.html in the current directory
    output_path = pathlib.Path(__file__).resolve().parent / "index.html"
    output_path.write_text(html_output, encoding="utf-8")
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()