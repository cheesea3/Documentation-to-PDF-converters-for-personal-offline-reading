#!/usr/bin/env python3

import os
import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# pdfkit: pip install pdfkit
# Requires wkhtmltopdf installed on your system
import pdfkit

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

START_URL = "https://mariadb.com/docs/server/"  # The top-level “Server” docs
DOMAIN = "mariadb.com"
OUTPUT_DIR = "mariadb_docs_pdf"  # Folder to store the PDFs
CRAWL_LIMIT = 200  # Safety limit for # of pages to crawl (prevent infinite loops)

# Patterns that define "valid" doc links under /docs/server
DOC_PATH_REGEX = re.compile(r"^/docs/server/.*", re.IGNORECASE)

# Convert to single PDF or multiple? If single, we merge at the end (optional).
CREATE_SINGLE_PDF = False

# If merging, name of final PDF
MERGED_PDF_NAME = "MariaDB_Server_Docs_Merged.pdf"


# --------------------------------------------------
# CRAWLER SETUP
# --------------------------------------------------

visited = set()
to_visit = [START_URL]

# Create output directory if not exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def is_valid_link(href):
    """
    Decide if the link is a valid docs link:
      - belongs to the same domain
      - matches the /docs/server/ pattern
    """
    if not href:
        return False
    # Must be same domain
    parsed = urlparse(href)
    if parsed.netloc and parsed.netloc != DOMAIN:
        return False
    # Must match /docs/server/ path
    if not DOC_PATH_REGEX.search(parsed.path):
        return False
    return True

# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def fetch_and_cleanup_html(url):
    """
    Fetch HTML content from `url`, remove unwanted nav sections or CSS,
    return a 'clean' HTML string that’s ready for PDF conversion.
    """
    print(f"   -> GET {url}")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Example: remove top nav, sidebars, footers if they clutter PDF
    # You might adapt these to match real classes/IDs in the actual HTML
    for nav_tag in soup.select(".Left-Nav, .Right-Nav, footer, .modal-overlay, .Controls"):
        nav_tag.decompose()

    # Potentially remove "hide_if_..." or other conditionally hidden content
    # or remove script/style tags:
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()

    # Return a string of the <body> or entire doc
    body_content = soup.find("div", class_="Document")
    if body_content:
        cleaned_html = str(body_content)
    else:
        # fallback if not found
        cleaned_html = str(soup)

    return cleaned_html

def convert_html_to_pdf(html_str, pdf_path):
    """
    Convert the given HTML string to a PDF file using pdfkit.
    """
    # pdfkit can convert from a raw string using the "pdfkit.from_string" method
    pdfkit.from_string(html_str, pdf_path)

def merge_pdfs(pdf_list, output_pdf):
    """
    Merge multiple PDFs into a single PDF using PyPDF2, if desired.
    """
    from PyPDF2 import PdfFileMerger

    merger = PdfFileMerger()
    for pdf_file in pdf_list:
        merger.append(pdf_file)

    merger.write(output_pdf)
    merger.close()

# --------------------------------------------------
# MAIN CRAWLER LOGIC
# --------------------------------------------------

def main():
    pdf_files = []

    while to_visit and len(visited) < CRAWL_LIMIT:
        url = to_visit.pop()
        if url in visited:
            continue

        visited.add(url)
        print(f"[Crawl] {url}")

        # Scrape links from this page
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"   !! Error fetching {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # Enqueue valid links
        for a_tag in soup.find_all("a", href=True):
            link_url = urljoin(url, a_tag["href"])
            if is_valid_link(link_url) and link_url not in visited:
                to_visit.append(link_url)

        # Prepare PDF name from path
        # e.g. /docs/server/deploy/best-practices -> server-deploy-best-practices.pdf
        path_part = urlparse(url).path.strip("/").replace("/", "-")
        if not path_part:
            path_part = "index"  # for base page
        pdf_filename = path_part + ".pdf"
        pdf_output_path = os.path.join(OUTPUT_DIR, pdf_filename)

        # Grab cleaned HTML from the real final URL
        try:
            cleaned_html = fetch_and_cleanup_html(url)
            convert_html_to_pdf(cleaned_html, pdf_output_path)
            pdf_files.append(pdf_output_path)
        except Exception as e:
            print(f"   !! Error converting page to PDF: {e}")

    # Optionally merge all PDFs into one big file
    if CREATE_SINGLE_PDF and pdf_files:
        merged_path = os.path.join(OUTPUT_DIR, MERGED_PDF_NAME)
        print(f"[*] Merging {len(pdf_files)} PDFs into {merged_path}")
        merge_pdfs(pdf_files, merged_path)

    print("Done!")
    print(f"Visited {len(visited)} pages, output in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
