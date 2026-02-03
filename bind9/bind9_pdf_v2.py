#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import json
import time
import random
import datetime
import requests

from playwright.sync_api import sync_playwright

# NEW for merging PDFs
try:
    from PyPDF2 import PdfMerger, PdfReader
except ImportError:
    print("[ERROR] PyPDF2 is not installed. Please install it via 'pip install PyPDF2'.")
    sys.exit(1)


################################################################################
# CONFIGURATION
################################################################################

BASE_ARTICLE_URL = "https://kb.isc.org/docs"

# The Document360 Project ID and version ID gleaned from site logs or HTML
PROJECT_ID = "956e37e2-5ec0-4942-8b27-35533899f099"
PROJECT_VERSION_ID = "c8128481-2ed5-44b5-abba-44e290850c4d"

# “Global” or “project-level” ID often found on every page that we want to exclude
GLOBAL_ID = PROJECT_VERSION_ID.lower()

# Random delay between each step to avoid hammering the server
REQUEST_DELAY_SECS = (3.0, 7.0)

# Filenames for caching partial progress
SLUG_CACHE_FILE = "slug_cache.json"    # Each slug -> { "articleId": "...", ... }
PDF_TRACKER_FILE = "pdf_tracker.json"  # Each articleId -> path
FAILED_SLUGS_FILE = "failed_slugs.json"# [ "slug1", "slug2", ...]

# Final name of the merged PDF
FINAL_MERGED_PDF = "ALL_MERGED.pdf"

# Headers to mimic a real browser
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/108.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;"
              "q=0.9,image/avif,image/webp,image/apng,*/*;"
              "q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
}

# The giant list of article slugs, in the exact order we want in our final PDF
ARTICLE_SLUGS = [
    "isc-packages-for-bind-9",
    "aa-01310",
    "supported-platforms",
    "policy-for-removing-namedconf-options",
    "aa-00577",
    "aa-00552",
    "edns-compatibility-dig-queries",
    "aa-00510",
    "aa-00435",
    "aa-00509",
    "aa-01589",
    "aa-01219",
    "aa-00897",
    "aa-00817",
    "aa-01640",
    "what-is-an-empty-non-terminal",
    "axfr-style-ixfr-explained",
    "aa-00203",
    "aa-01009",
    "aa-01526",
    "aa-01123",
    "aa-00822",
    "aa-01342",
    "aa-00341",
    "dns-cookies-on-servers-in-anycast-clusters",
    "aa-00704",
    "aa-00723",
    "aa-00363",
    "aa-00851",
    "aa-00973",
    "aa-01182",
    "aa-01208",
    "aa-00769",
    "aa-00289",
    "aa-00653",
    "aa-01525",
    "aa-00374",
    "aa-00995",
    "aa-01309",
    "aa-01386",
    "aa-01387",
    "aa-00503",
    "aa-00296",
    "aa-00295",
    "aa-01190",
    "aa-00302",
    "aa-01149",
    "aa-00359",
    "aa-00835",
    "aa-00768",
    "aa-00206",
    "aa-00648",
    "aa-00291",
    "aa-00356",
    "aa-01540",
    "changes-to-be-aware-of-when-moving-from-bind-916-to-918",
    "changes-to-be-aware-of-when-moving-from-911-to-916",
    "aa-00800",
    "aa-00538",
    "aa-00608",
    "aa-01401",
    "aa-00626",
    "aa-01467",
    "rate-limiters-for-authoritative-zone-propagation",
    "aa-01313",
    "promoting-a-secondary-server-to-primary",
    "managing-manual-multi-master",
    "aa-00331",
    "bind-best-practices-authoritative",
    "aa-00546",
    "aa-00492",
    "why-does-my-authoritative-server-make-recursive-queries",
    "proxyv2-support-in-bind-9",
    "bind-best-practices-recursive",
    "aa-01304",
    "aa-01316",
    "aa-00463",
    "aa-00912",
    "aa-01534",
    "aa-01547",
    "aa-01418",
    "aa-00482",
    "aa-01528",
    "aa-01122",
    "the-umbrella-feature-in-detail",
    "aa-00913",
    "cve-2024-4076",
    "cve-2024-1975",
    "cve-2024-1737",
    "cve-2024-0760",
    "cve-2023-50868",
    "cve-2023-50387",
    "cve-2023-6516",
    "cve-2023-5680",
    "cve-2023-5679",
    "cve-2023-5517",
    "cve-2023-4408",
    "cve-2023-4236",
    "cve-2023-3341",
    "cve-2023-2911",
    "cve-2023-2829",
    "cve-2023-2828",
    "cve-2022-38178",
    "cve-2022-38177",
    "cve-2022-3924",
    "cve-2022-3736",
    "cve-2022-3488",
    "cve-2022-3094",
    "cve-2022-3080",
    "cve-2022-2906",
    "cve-2022-2881",
    "cve-2022-2795",
    "cve-2022-1183",
    "cve-2022-0667",
    "cve-2022-0635",
    "cve-2022-0396",
    "cve-2021-25220",
    "bind-9-security-vulnerability-matrix-916",
    "bind-9-security-vulnerability-matrix-915",
    "bind-9-security-vulnerability-matrix-914",
    "bind-9-security-vulnerability-matrix-913",
    "bind-9-security-vulnerability-matrix-912",
    "bind-9-security-vulnerability-matrix-911",
    "bind-9-security-vulnerability-matrix-911-s",
    "bind-9-security-vulnerability-matrix-910-s",
    "bind-9-security-vulnerability-matrix-910",
    "bind-9-security-vulnerability-matrix-99-s",
    "bind-99-matrix",
    "aa-01586",
    "aa-01585",
    "aa-01584",
    "aa-01583",
    "aa-01582",
    "aa-01581",
    "aa-01580",
    "aa-01579",
    "aa-01577",
    "cve-2021-25219",
    "cve-2021-25218",
    "cve-2021-25216",
    "cve-2021-25215",
    "cve-2021-25214",
    "cve-2020-8625",
    "cve-2020-8624",
    "cve-2020-8623",
    "cve-2020-8622",
    "cve-2020-8621",
    "cve-2020-8620",
    "cve-2020-8619",
    "cve-2020-8618",
    "cve-2020-8617-faq-and-supplemental-information",
    "cve-2020-8617",
    "cve-2020-8616",
    "cve-2019-6477",
    "cve-2019-6476",
    "cve-2019-6475",
    "cve-2019-6471",
    "cve-2019-6469",
    "cve-2019-6468",
    "cve-2019-6467",
    "cve-2019-6465",
    "cve-2018-5745",
    "cve-2018-5744",
    "cve-2018-5743",
    "cve-2018-5741",
    "aa-01639",
    "aa-01616",
    "aa-01606",
    "aa-01602",
    "aa-01562",
    "aa-01542",
    "aa-01503",
    "aa-01504",
    "aa-01496",
    "aa-01495",
    "aa-01471",
    "aa-01466",
    "aa-01465",
    "aa-01453",
    "aa-01442",
    "aa-01441",
    "aa-01440",
    "aa-01434",
    "aa-01439",
    "aa-01433",
    "aa-01419",
    "aa-01393",
    "aa-01351",
    "aa-01353",
    "aa-01352",
    "aa-01348",
    "aa-01336",
    "aa-01335",
    "aa-01319",
    "aa-01317",
    "aa-01291",
    "aa-01287",
    "aa-01272",
    "aa-01267",
    "aa-01235",
    "aa-01217",
    "aa-01216",
    "aa-01166",
    "aa-01161",
    "aa-01078",
    "aa-01085",
    "aa-01063",
    "aa-01062",
    "aa-01015",
    "aa-01016",
    "aa-00967",
    "aa-00997",
    "aa-00871",
    "aa-00879",
    "aa-00855",
    "aa-00801",
    "aa-00807",
    "aa-00778",
    "aa-00730",
    "aa-00729",
    "aa-00828",
    "aa-00766",
    "aa-00698",
    "aa-00703",
    "aa-00691",
    "aa-00544",
    "aa-00549",
    "aa-00458",
    "aa-00457",
    "aa-00459",
    "aa-00460",
    "aa-00461",
    "aa-00935",
    "aa-00937",
    "aa-00938",
    "aa-00934",
    "aa-00933",
    "aa-00932",
    "aa-00936",
    "aa-00931",
    "aa-00926",
    "aa-00924",
    "aa-00923",
    "aa-00921",
    "aa-00920",
    "aa-00919",
    "aa-00918",
    "cve-2006-4096",
    "aa-00916",
    "aa-00958",
    "aa-00950",
    "aa-00959",
    "aa-00922",
    "aa-00957",
    "aa-00956",
    "aa-00954",
    "aa-00953",
    "aa-00955",
    "aa-00951",
    "aa-00947",
    "aa-00949",
    "aa-00948",
    "aa-00946",
    "aa-00944",
    "aa-00945",
    "aa-00941",
    "aa-00940",
    "aa-00943",
    "aa-00942",
    "aa-00939",
    "a-note-about-bind-release-notes",
    "bind-911-branch",
    "bind-9-end-of-life-dates",
    "aa-00301",
    "aa-00706",
    "aa-01213",
    "aa-00204",
    "aa-00434",
    "aa-00305",
    "aa-00716",
    "aa-00309",
    "aa-00300",
    "aa-00297",
    "aa-00299",
    "aa-00298",
    "aa-00303",
    "aa-00508",
    "aa-00765",
    "aa-00464",
    "aa-00903",
    "aa-00804",
    "aa-00548",
    "aa-00345",
    "aa-00304",
    "aa-00708",
    "aa-00823",
    "aa-00722",
    "aa-00282",
    "aa-00279",
    "aa-01338",
    "aa-00717",
    "aa-00537",
    "dnssec-policy-requires-dynamic-dns-or-inline-signing",
    "aa-00208",
    "aa-00285",
    "aa-01641",
    "aa-01249",
    "aa-01140",
    "aa-00269",
    "aa-00904",
    "aa-00280",
    "aa-00914",
    "aa-00420",
    "aa-00419",
    "aa-00640",
    "aa-00307",
    "aa-00281",
    "aa-00287",
    "aa-00290",
    "aa-00310",
    "aa-00308",
    "aa-00803",
    "stub-zones-dont-work-when-primaries-are-configured-for-minimal-responses-yes",
    "aa-00311",
    "aa-01148",
    "aa-00994",
    "aa-01000",
    "aa-01150",
    "aa-00376",
    "aa-00971",
    "aa-00821",
    "aa-00711",
    "aa-00205",
    "dns-flag-day-will-it-affect-you",
    "aa-01127",
    "916-dnssec-validation-automatic-trust-anchor-management",
    "aa-00725",
    "aa-00576",
    "aa-01463",
    "aa-01113",
    "how-does-tcp-clients-work",
    "aa-00620",
    "ednscomp-tests-and-status-codes",
    "aa-00213",
    "aa-01420",
    "aa-01118",
    "aa-00547",
    "aa-01349",
    "aa-01059",
    "aa-00610",
    "aa-01220",
    "aa-01152",
    "using-response-policy-zones-to-disable-mozilla-doh-by-default",
    "aa-01350",
    "aa-00306",
    "enabling-audit-logs-in-bind-9",
    "logrotate-settings-in-bind-9",
    "aa-00559",
    "aa-01315",
    "aa-01183",
    "iscs-dnssec-look-aside-validation-registry",
    "hardware-security-modules-that-work-with-bind-9",
    "aa-01002",
    "dns-flag-day-notes-for-authoritative-zones",
    "aa-00726",
    "bind-9-pkcs11",
    "disable-dnssec-lookaside-dlv-now-heres-how",
    "aa-01314",
    "exporting-statistics-to-prometheus",
    "serve-stale-implementation-details",
    "rrl-on-queries-to-the-built-in-bind-view",
    "setting-journal-size-for-secondary-servers",
    "dnssec-key-and-signing-policy",
    "monitoring-recommendations-for-bind-9",
    "aa-00836",
    "bind-9-technical-contributors-guide",
    "aa-01454",
    "checkhints-unable-to-get-root-ns-rrset-from-cache-not-found",
    "lame-servers-what-are-they-and-how-does-bind-deal-with-them",
    "ixfr-from-differences-pitfalls-and-genuine-use-cases",
    "using-private-name-space",
    "collecting-client-queries-for-dns-server-testing",
    "bind-option-reuseport",
    "edns-client-subnet-ecs-for-resolver-operators-getting-started",
    "qname-minimization-and-spamhaus",
]



################################################################################
# HELPER FUNCTIONS
################################################################################

def load_json_dict(filepath: str) -> dict:
    """Load a JSON object from a file; if not found or invalid, return {}."""
    if os.path.isfile(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            print(f"[WARN] Could not parse {filepath}. Using empty dict.")
    return {}

def save_json_dict(data: dict, filepath: str):
    """Save dict data to a JSON file with indentation."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as ex:
        print(f"[ERROR] Could not write to {filepath}: {ex}")

def load_json_list(filepath: str) -> list:
    """Load a JSON list from a file; if not found or invalid, return []"""
    if os.path.isfile(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            print(f"[WARN] Could not parse {filepath}. Using empty list.")
    return []

def save_json_list(data: list, filepath: str):
    """Save list data to a JSON file with indentation."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as ex:
        print(f"[ERROR] Could not write to {filepath}: {ex}")

def do_random_delay():
    """Sleep for a random number of seconds within REQUEST_DELAY_SECS."""
    if REQUEST_DELAY_SECS:
        low, high = REQUEST_DELAY_SECS
        secs = random.uniform(low, high)
        print(f"  (sleeping ~{secs:.1f} seconds to slow down...)")
        time.sleep(secs)

def find_real_article_id(html_text: str) -> str or None:
    """
    In the page content, find all "articleId":"<uuid>", skip the known global one,
    and return the first unique match.
    """
    pattern = r'"articleId"\s*:\s*"([0-9a-f-]{36})"'
    matches = re.findall(pattern, html_text, flags=re.IGNORECASE)
    # Filter out the global ID
    filtered = [m for m in matches if m.lower() != GLOBAL_ID]
    return filtered[0] if filtered else None

def debug_log_page(page):
    """
    If we get e.g. a 403, we can dump some info for debugging:
    - page.url
    - snippet of HTML
    """
    print("  [DEBUG] Page final URL:", page.url)
    snippet = page.content()[:500]
    print(f"  [DEBUG] Content snippet:\n{'-'*40}\n{snippet}\n{'-'*40}")


################################################################################
# PDF-GENERATION/STATUS
################################################################################

def poll_task_status(task_id: str, session: requests.Session, max_tries=30):
    """
    Poll the doc360 tasks/web/status/<taskId> endpoint until we see
    isComplete = True or we exhaust max_tries. Return final JSON.
    """
    status_url = f"https://api.document360.io/api/tasks/web/status/{task_id}"
    for attempt in range(1, max_tries + 1):
        print(f"  [poll_task_status] Attempt {attempt}/{max_tries}...")
        do_random_delay()
        try:
            r = session.get(status_url, headers=HEADERS, timeout=30)
            if not r.ok:
                print(f"  !! poll_task_status: HTTP {r.status_code} error.")
                continue
            data = r.json()
            st = data.get("taskStatus", {})
            if st.get("isComplete"):
                print("  [poll_task_status] isComplete == True!")
                return data
            else:
                print(f"  [poll_task_status] status={st.get('status')} (not complete).")
        except Exception as ex:
            print(f"  [poll_task_status] Exception: {ex}")
    print("  [poll_task_status] Gave up after max_tries; returning {}.")
    return {}

def generate_single_article_pdf(article_id: str, file_name: str, session: requests.Session) -> str or None:
    """
    Request a PDF for one article (articleIds=[article_id]),
    poll until done, then return the final PDF URL, or None if fails.
    """
    url = f"https://api.document360.io/api/tasks/web/generate-pdf/{PROJECT_ID}"

    payload = {
        "fileName": file_name,
        "langCode": "en",
        "projectVersionId": PROJECT_VERSION_ID,
        "articleIds": [article_id],  # single article
        "isPreview": False,
        "currentArticleVersionNumber": "2"
    }

    print(f"  => POST generate PDF for articleId={article_id}")
    try:
        do_random_delay()
        r = session.post(url, json=payload, headers=HEADERS, timeout=30)
        if not r.ok:
            print(f"  !! generate_single_article_pdf: HTTP {r.status_code} error.")
            return None
        resp_json = r.json()
    except Exception as ex:
        print(f"  !! Exception in generate_single_article_pdf: {ex}")
        return None

    data_block = resp_json.get("data", {})
    task_id = data_block.get("taskId")
    if not task_id:
        print("  !! No taskId in response. Possibly an error.")
        return None

    # Now poll for completion
    status_data = poll_task_status(task_id, session)
    st = status_data.get("taskStatus", {})
    if not st.get("isComplete"):
        print(f"  !! PDF generation never completed for articleId={article_id}.")
        return None

    # Extract the PDF URL from "result"
    for item in st.get("result", []):
        if item.get("name") == "url":
            return item.get("value")

    print("  !! Completed but no PDF url found in 'result'.")
    return None

def download_pdf_file(pdf_url: str, output_path: str, session: requests.Session) -> bool:
    """Download the PDF from pdf_url to output_path. Returns True if success."""
    print(f"  [download_pdf_file] Downloading {pdf_url} -> {output_path}")
    try:
        do_random_delay()
        r = session.get(pdf_url, headers=HEADERS, timeout=60)
        if r.ok:
            with open(output_path, "wb") as f:
                f.write(r.content)
            return True
        else:
            print(f"  !! HTTP {r.status_code} error on PDF download.")
    except Exception as ex:
        print(f"  !! Exception in download_pdf_file: {ex}")
    return False


################################################################################
# MAIN
################################################################################

def main():
    # 1) Load caches
    slug_cache = load_json_dict(SLUG_CACHE_FILE)  # each slug-> {articleId, etc.}
    pdf_tracker = load_json_dict(PDF_TRACKER_FILE)  # each articleId -> local .pdf filename
    failed_slugs = set(load_json_list(FAILED_SLUGS_FILE))

    print("=== Step A: Ensure we have articleIds for all slugs ===")
    start_time = datetime.datetime.now()

    # --------------------------------------------------------------------------
    # Step A.1: Use Playwright to find articleIds if missing
    # --------------------------------------------------------------------------
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page = context.new_page()

        for slug in ARTICLE_SLUGS:
            # skip if we already failed or have an articleId
            if slug in failed_slugs:
                continue
            if slug in slug_cache and slug_cache[slug].get("articleId"):
                continue

            print(f"\n>>> Attempting slug: {slug}")
            do_random_delay()

            url = f"{BASE_ARTICLE_URL}/{slug}"
            print(f"  => Navigating to {url}")
            try:
                response = page.goto(url, timeout=60000)
            except Exception as ex:
                print(f"  !! Exception: {ex}")
                failed_slugs.add(slug)
                save_json_list(sorted(failed_slugs), FAILED_SLUGS_FILE)
                continue

            slug_cache.setdefault(slug, {})
            slug_cache[slug]["lastChecked"] = time.strftime("%Y-%m-%d %H:%M:%S")

            if not response:
                print("  !! No response. Marking as failed.")
                slug_cache[slug]["articleId"] = None
                slug_cache[slug]["lastStatusCode"] = 999
                failed_slugs.add(slug)
                save_json_list(sorted(failed_slugs), FAILED_SLUGS_FILE)
                save_json_dict(slug_cache, SLUG_CACHE_FILE)
                continue

            status_code = response.status
            slug_cache[slug]["lastStatusCode"] = status_code

            if status_code == 200:
                html_text = page.content()
                if html_text:
                    found_id = find_real_article_id(html_text)
                    if found_id:
                        print(f"  >> Found articleId={found_id}")
                        slug_cache[slug]["articleId"] = found_id
                    else:
                        print("  !! 200 but no articleId found. Marking fail.")
                        slug_cache[slug]["articleId"] = None
                        failed_slugs.add(slug)
                else:
                    print("  !! 200 but empty content. Marking fail.")
                    slug_cache[slug]["articleId"] = None
                    failed_slugs.add(slug)
            else:
                print(f"  !! HTTP {status_code}. Marking fail.")
                slug_cache[slug]["articleId"] = None
                failed_slugs.add(slug)

            # Save after each slug
            save_json_dict(slug_cache, SLUG_CACHE_FILE)
            save_json_list(sorted(failed_slugs), FAILED_SLUGS_FILE)

        browser.close()

    # --------------------------------------------------------------------------
    # Step B: Generate and download single-article PDFs
    # --------------------------------------------------------------------------
    print("\n=== Step B: Generate & download single-article PDFs ===")
    with requests.Session() as session:
        for slug in ARTICLE_SLUGS:
            if slug in failed_slugs:
                continue

            info = slug_cache.get(slug, {})
            art_id = info.get("articleId")
            if not art_id:
                # We never got an ID
                continue

            # If we already have a PDF path for this articleId, skip
            if art_id in pdf_tracker:
                pdf_file_already = pdf_tracker[art_id]
                if os.path.isfile(pdf_file_already):
                    # It's actually on disk, so skip
                    continue
                else:
                    print(f"[WARN] pdf_tracker says {art_id} -> {pdf_file_already}, "
                          "but that file is missing. We'll re-download.")
                    del pdf_tracker[art_id]  # force re-download

            # Attempt generation
            print(f"\n=== Attempting single-article PDF for slug={slug}, articleId={art_id} ===")
            do_random_delay()
            pdf_url = generate_single_article_pdf(art_id, slug, session)
            if pdf_url:
                out_name = f"{slug}.pdf"
                ok = download_pdf_file(pdf_url, out_name, session)
                if ok:
                    pdf_tracker[art_id] = out_name
                    print(f"  [SUCCESS] {slug} => {out_name}")
                else:
                    print(f"  [FAIL] {slug} => download error.")
            else:
                print(f"  [FAIL] {slug} => no PDF URL from doc360.")

            # Save after each attempt
            save_json_dict(pdf_tracker, PDF_TRACKER_FILE)

    # --------------------------------------------------------------------------
    # Step C: Merge all single PDFs into one final PDF, in slug order
    # --------------------------------------------------------------------------
    print("\n=== Step C: Merge single-article PDFs into one final PDF ===")
    merger = PdfMerger()

    missing_slugs = []       # Slugs whose PDF is missing on disk
    merge_failed_slugs = []  # Slugs that had a local PDF but failed to append

    for slug in ARTICLE_SLUGS:
        # If slug is in the failed list, skip
        if slug in failed_slugs:
            # We'll consider that "missing" for the final doc
            missing_slugs.append(slug)
            continue

        art_id = slug_cache.get(slug, {}).get("articleId")
        if not art_id:
            # Means no ID found at all
            missing_slugs.append(slug)
            continue

        pdf_path = pdf_tracker.get(art_id)
        if not pdf_path or not os.path.isfile(pdf_path):
            # We never downloaded, or file doesn't exist
            missing_slugs.append(slug)
            continue

        print(f"  [MERGE] Appending PDF for slug='{slug}' => {pdf_path}")
        try:
            # Instead of merger.append(pdf_path) we do:
            #   1. read into a PdfReader (which opens the file)
            #   2. merge that
            #   3. close it
            with open(pdf_path, "rb") as f_in:
                reader = PdfReader(f_in)
                merger.append(reader)
        except Exception as ex:
            print(f"  !! Could not append {pdf_path}: {ex}")
            merge_failed_slugs.append(slug)

    # Now write out the merged PDF
    if merger.pages:
        try:
            with open(FINAL_MERGED_PDF, "wb") as f_out:
                merger.write(f_out)
            print(f"\n[SUCCESS] Merged {len(merger.pages)} PDFs into '{FINAL_MERGED_PDF}'.")
        except Exception as ex:
            print(f"[ERROR] Could not write merged PDF '{FINAL_MERGED_PDF}': {ex}")
    else:
        print("[WARN] No PDFs were appended, so we did not create a merged file.")

    # --------------------------------------------------------------------------
    # Final summary
    # --------------------------------------------------------------------------
    end_time = datetime.datetime.now()
    delta = end_time - start_time
    print("\n=== FINISHED ===")
    print(f"Started: {start_time}")
    print(f"Ended:   {end_time}")
    print(f"Elapsed: {delta}\n")

    # If we had missing or merge-failed
    if missing_slugs or merge_failed_slugs:
        print("[INFO] Some PDFs were missing or failed to merge.")
        if missing_slugs:
            print("  >> Missing PDFs (slug):")
            for s in missing_slugs:
                print("     -", s)
        if merge_failed_slugs:
            print("  >> Merge-failed PDFs (slug):")
            for s in merge_failed_slugs:
                print("     -", s)
    else:
        print("[INFO] All PDFs present and merged successfully. Check your merged file!")

    print("Check slug_cache.json for article IDs and pdf_tracker.json for downloaded PDFs.")


if __name__ == "__main__":
    main()
