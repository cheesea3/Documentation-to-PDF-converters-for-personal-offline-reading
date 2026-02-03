#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import requests
from bs4 import BeautifulSoup

# Either import pdfkit or WeasyPrint (choose one):
import pdfkit
# from weasyprint import HTML

# --------------------------------------------------------------------------------------
# 1) CONFIGURATION
# --------------------------------------------------------------------------------------

BASE_URL = "https://redis.io"
SECTION_HOME = "https://redis.io/docs/latest/operate/oss_and_stack/"

# We only want links that live under "/docs/latest/operate/oss_and_stack"
# This pattern helps us filter out everything else.
VALID_URL_PATTERN = re.compile(r"^/docs/latest/operate/oss_and_stack")


# --------------------------------------------------------------------------------------
# 2) HELPER FUNCTIONS
# --------------------------------------------------------------------------------------

def get_soup(url):
    """
    Fetch a URL and return a BeautifulSoup object.
    """
    print(f"Fetching {url}")
    resp = requests.get(url)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def clean_html(soup):
    """
    Remove extraneous elements from the page (nav bars, footers, sidebars, search bars, etc.)
    so we get a cleaner PDF for personal references.
    """
    # We'll specify a bunch of selectors that typically contain navigation, sidebars, ads, etc.
    # Adjust these as needed if you find any important content is removed or new nav elements appear.
    selectors_to_remove = [
        "header",
        "footer",
        "#sidebar",
        ".sticky",
        "nav#TableOfContents",
        "nav",
        "section.hidden.xl\\:block",  # The big right-side block in wide screens
        "div.sr-only",                # The hidden search overlay container
        "div#search-container",       # Another search overlay container
        "#page-feedback",             # Rate this page form
        ".menu-toggle",
        ".bg-redis-neutral-200",      # Some of the right nav blocks / footer blocks
    ]

    # Remove all matching elements for each selector
    for selector in selectors_to_remove:
        for tag in soup.select(selector):
            tag.decompose()

    # Also remove any scripts, leftover if any
    for script_tag in soup.find_all("script"):
        script_tag.decompose()

    return soup


def extract_links(soup):
    """
    From a page's HTML, extract all links that belong to the
    "Redis Community Edition and Stack" section, i.e. /docs/latest/operate/oss_and_stack
    Return them as absolute URLs.
    """
    found_urls = []
    for a_tag in soup.select("a[href]"):
        href = a_tag["href"].strip()
        # If it's a relative link like '/docs/latest/operate/oss_and_stack/...'
        if VALID_URL_PATTERN.match(href):
            abs_url = BASE_URL + href
            found_urls.append(abs_url)
    return found_urls


# --------------------------------------------------------------------------------------
# 3) MAIN CRAWLER
# --------------------------------------------------------------------------------------

def crawl_redis_docs(start_url):
    """
    Starting from the Redis Community Edition and Stack overview page,
    recursively crawl to find *all* pages in that section.
    """
    to_visit = [start_url]
    visited = set()
    all_pages = []

    while to_visit:
        url = to_visit.pop()
        if url in visited:
            continue
        visited.add(url)

        soup = get_soup(url)
        all_pages.append(url)

        # find sub-links in this page
        sub_links = extract_links(soup)
        for link in sub_links:
            if link not in visited:
                to_visit.append(link)

        # optional: be nice to the server
        time.sleep(0.5)

    return all_pages


# --------------------------------------------------------------------------------------
# 4) SCRAPE CONTENT, COMPILE HTML, AND CONVERT TO PDF
# --------------------------------------------------------------------------------------

def scrape_and_build_combined_html(urls):
    """
    Go through each URL, fetch its HTML, strip out unneeded parts,
    then build a big combined HTML string to feed into PDF generation.
    """
    combined_html_parts = []
    combined_html_parts.append("<html><head><meta charset='UTF-8'></head><body>")

    for url in urls:
        soup = get_soup(url)

        # Clean up the HTML to remove nav, footers, scripts, sidebars, etc.
        soup = clean_html(soup)

        # We'll try to identify the main content: 
        # 'main.docs' or 'section.prose' often contain the page's primary content.
        # If neither is found, fallback to the entire <body>.
        main_content = soup.select_one("main.docs") or soup.select_one("section.prose") or soup.find("body")

        # Page heading:
        title_tag = soup.find("title")
        page_title = title_tag.get_text(strip=True) if title_tag else url
        combined_html_parts.append(f"<h1>{page_title}</h1>")

        # Insert main content or fallback to entire soup if none found
        if main_content:
            combined_html_parts.append(str(main_content))
        else:
            combined_html_parts.append(str(soup))

        # Insert a page break so each doc page starts on a fresh PDF page
        combined_html_parts.append("<div style='page-break-after: always;'></div>")

    combined_html_parts.append("</body></html>")
    return "\n".join(combined_html_parts)


def generate_pdf_from_html(html_string, output_pdf="redis_community_stack_docs.pdf"):
    """
    Save the big combined HTML into a single PDF file using pdfkit or WeasyPrint.
    """
    # Option 1: pdfkit
    pdfkit.from_string(html_string, output_pdf)
    print(f"PDF generated: {output_pdf}")

    # Option 2: WeasyPrint (uncomment if you prefer it)
    # HTML(string=html_string).write_pdf(output_pdf)
    # print(f"PDF generated: {output_pdf}")


# --------------------------------------------------------------------------------------
# 5) RUN IT ALL
# --------------------------------------------------------------------------------------

if __name__ == "__main__":
    # 1) Crawl all relevant sub-pages
    print("Crawling for all pages in Redis Community Edition and Stack...")
    all_section_urls = crawl_redis_docs(SECTION_HOME)
    print(f"\nFound {len(all_section_urls)} pages under {SECTION_HOME}.\n")

    # 2) Scrape each page, accumulate HTML
    print("Building combined HTML...")
    final_html = scrape_and_build_combined_html(sorted(all_section_urls))

    # 3) Convert combined HTML to single PDF
    print("Generating PDF...")
    generate_pdf_from_html(final_html, output_pdf="redis_community_stack_docs.pdf")

    print("\nDone! Check redis_community_stack_docs.pdf for your combined, cleaned docs.")
