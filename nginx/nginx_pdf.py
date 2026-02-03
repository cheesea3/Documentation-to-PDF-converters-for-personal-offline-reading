#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import pdfkit
import os
import time
import sys
from PyPDF2 import PdfReader, PdfWriter
import subprocess
import logging

################################################################################
# CONFIG
################################################################################

# If you know the exact path to wkhtmltopdf, set it here. Otherwise, pdfkit will
# look in your PATH. On macOS with Homebrew cask, it's usually /usr/local/bin/wkhtmltopdf
WKHTMLTOPDF_PATH = "/usr/local/bin/wkhtmltopdf"

# You can pass extra options to wkhtmltopdf for debugging or forced SSL:
PDFKIT_OPTIONS = {
    # "ssl-protocol": "TLSv1.2",       # In some older versions you might try forcibly setting TLS.
    # "debug-javascript": None,        # If you want JS debug
    # "enable-local-file-access": None # Sometimes needed for local assets
}

# How many seconds to wait between each request (to be polite / avoid hammering)
REQUEST_DELAY = 1

URLS_IN_ORDER = [
    # Introduction
    "https://nginx.org/en/docs/install.html",
    "https://nginx.org/en/docs/configure.html",
    "https://nginx.org/en/docs/beginners_guide.html",
    "https://docs.nginx.com/nginx/admin-guide/",  # Admin’s Guide (external site)
    "https://nginx.org/en/docs/control.html",
    "https://nginx.org/en/docs/events.html",
    "https://nginx.org/en/docs/hash.html",
    "https://nginx.org/en/docs/debugging_log.html",
    "https://nginx.org/en/docs/syslog.html",
    "https://nginx.org/en/docs/syntax.html",
    "https://nginx.org/en/docs/switches.html",
    "https://nginx.org/en/docs/windows.html",
    "https://nginx.org/en/docs/quic.html",

    # Next chunk
    "https://nginx.org/en/docs/http/request_processing.html",
    "https://nginx.org/en/docs/http/server_names.html",
    "https://nginx.org/en/docs/http/load_balancing.html",
    "https://nginx.org/en/docs/http/configuring_https_servers.html",

    # TCP/UDP processing
    "https://nginx.org/en/docs/stream/stream_processing.html",

    # njs
    "https://nginx.org/en/docs/njs/index.html",

    # “Chapter nginx in The Architecture of Open Source Applications”
    #  (This is an external link: http://www.aosabook.org/en/nginx.html)
    "http://www.aosabook.org/en/nginx.html",

    # How-To
    "https://nginx.org/en/docs/howto_build_on_win32.html",
    "https://docs.nginx.com/nginx/admin-guide/installing-nginx/installing-nginx-plus-amazon-web-services/",
    "https://nginx.org/en/docs/nginx_dtrace_pid_provider.html",
    "https://nginx.org/en/docs/http/converting_rewrite_rules.html",
    "https://nginx.org/en/docs/http/websocket.html",

    # Development
    "https://nginx.org/en/docs/contributing_changes.html",
    "https://nginx.org/en/docs/dev/development_guide.html",

    # Modules Reference - We include each in the order found on the docs page:
    "https://nginx.org/en/docs/dirindex.html",
    "https://nginx.org/en/docs/varindex.html",
    "https://nginx.org/en/docs/ngx_core_module.html",

    # Then each “ngx_http_*_module.html”, “ngx_mail_*_module.html”,
    # “ngx_stream_*_module.html”, etc. in the same order:
    "https://nginx.org/en/docs/http/ngx_http_core_module.html",
    "https://nginx.org/en/docs/http/ngx_http_access_module.html",
    "https://nginx.org/en/docs/http/ngx_http_addition_module.html",
    "https://nginx.org/en/docs/http/ngx_http_api_module.html",
    "https://nginx.org/en/docs/http/ngx_http_auth_basic_module.html",
    "https://nginx.org/en/docs/http/ngx_http_auth_jwt_module.html",
    "https://nginx.org/en/docs/http/ngx_http_auth_request_module.html",
    "https://nginx.org/en/docs/http/ngx_http_autoindex_module.html",
    "https://nginx.org/en/docs/http/ngx_http_browser_module.html",
    "https://nginx.org/en/docs/http/ngx_http_charset_module.html",
    "https://nginx.org/en/docs/http/ngx_http_dav_module.html",
    "https://nginx.org/en/docs/http/ngx_http_empty_gif_module.html",
    "https://nginx.org/en/docs/http/ngx_http_f4f_module.html",
    "https://nginx.org/en/docs/http/ngx_http_fastcgi_module.html",
    "https://nginx.org/en/docs/http/ngx_http_flv_module.html",
    "https://nginx.org/en/docs/http/ngx_http_geo_module.html",
    "https://nginx.org/en/docs/http/ngx_http_geoip_module.html",
    "https://nginx.org/en/docs/http/ngx_http_grpc_module.html",
    "https://nginx.org/en/docs/http/ngx_http_gunzip_module.html",
    "https://nginx.org/en/docs/http/ngx_http_gzip_module.html",
    "https://nginx.org/en/docs/http/ngx_http_gzip_static_module.html",
    "https://nginx.org/en/docs/http/ngx_http_headers_module.html",
    "https://nginx.org/en/docs/http/ngx_http_hls_module.html",
    "https://nginx.org/en/docs/http/ngx_http_image_filter_module.html",
    "https://nginx.org/en/docs/http/ngx_http_index_module.html",
    "https://nginx.org/en/docs/http/ngx_http_internal_redirect_module.html",
    "https://nginx.org/en/docs/http/ngx_http_js_module.html",   # example shown above
    "https://nginx.org/en/docs/http/ngx_http_keyval_module.html",
    "https://nginx.org/en/docs/http/ngx_http_limit_conn_module.html",
    "https://nginx.org/en/docs/http/ngx_http_limit_req_module.html",
    "https://nginx.org/en/docs/http/ngx_http_log_module.html",
    "https://nginx.org/en/docs/http/ngx_http_map_module.html",
    "https://nginx.org/en/docs/http/ngx_http_memcached_module.html",
    "https://nginx.org/en/docs/http/ngx_http_mirror_module.html",
    "https://nginx.org/en/docs/http/ngx_http_mp4_module.html",
    "https://nginx.org/en/docs/http/ngx_http_perl_module.html",
    "https://nginx.org/en/docs/http/ngx_http_proxy_module.html",
    "https://nginx.org/en/docs/http/ngx_http_proxy_protocol_vendor_module.html",
    "https://nginx.org/en/docs/http/ngx_http_random_index_module.html",
    "https://nginx.org/en/docs/http/ngx_http_realip_module.html",
    "https://nginx.org/en/docs/http/ngx_http_referer_module.html",
    "https://nginx.org/en/docs/http/ngx_http_rewrite_module.html",
    "https://nginx.org/en/docs/http/ngx_http_scgi_module.html",
    "https://nginx.org/en/docs/http/ngx_http_secure_link_module.html",
    "https://nginx.org/en/docs/http/ngx_http_session_log_module.html",
    "https://nginx.org/en/docs/http/ngx_http_slice_module.html",
    "https://nginx.org/en/docs/http/ngx_http_split_clients_module.html",
    "https://nginx.org/en/docs/http/ngx_http_ssi_module.html",
    "https://nginx.org/en/docs/http/ngx_http_ssl_module.html",
    "https://nginx.org/en/docs/http/ngx_http_status_module.html",
    "https://nginx.org/en/docs/http/ngx_http_stub_status_module.html",
    "https://nginx.org/en/docs/http/ngx_http_sub_module.html",
    "https://nginx.org/en/docs/http/ngx_http_upstream_module.html",
    "https://nginx.org/en/docs/http/ngx_http_upstream_conf_module.html",
    "https://nginx.org/en/docs/http/ngx_http_upstream_hc_module.html",
    "https://nginx.org/en/docs/http/ngx_http_userid_module.html",
    "https://nginx.org/en/docs/http/ngx_http_uwsgi_module.html",
    "https://nginx.org/en/docs/http/ngx_http_v2_module.html",
    "https://nginx.org/en/docs/http/ngx_http_v3_module.html",
    "https://nginx.org/en/docs/http/ngx_http_xslt_module.html",

    # mail modules
    "https://nginx.org/en/docs/mail/ngx_mail_core_module.html",
    "https://nginx.org/en/docs/mail/ngx_mail_auth_http_module.html",
    "https://nginx.org/en/docs/mail/ngx_mail_proxy_module.html",
    "https://nginx.org/en/docs/mail/ngx_mail_realip_module.html",
    "https://nginx.org/en/docs/mail/ngx_mail_ssl_module.html",
    "https://nginx.org/en/docs/mail/ngx_mail_imap_module.html",
    "https://nginx.org/en/docs/mail/ngx_mail_pop3_module.html",
    "https://nginx.org/en/docs/mail/ngx_mail_smtp_module.html",

    # stream modules
    "https://nginx.org/en/docs/stream/ngx_stream_core_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_access_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_geo_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_geoip_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_js_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_keyval_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_limit_conn_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_log_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_map_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_mqtt_preread_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_mqtt_filter_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_pass_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_proxy_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_proxy_protocol_vendor_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_realip_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_return_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_set_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_split_clients_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_ssl_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_ssl_preread_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_upstream_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_upstream_hc_module.html",
    "https://nginx.org/en/docs/stream/ngx_stream_zone_sync_module.html",

    # google perf, mgmt, otel
    "https://nginx.org/en/docs/ngx_google_perftools_module.html",
    "https://nginx.org/en/docs/ngx_mgmt_module.html",
    "https://nginx.org/en/docs/ngx_otel_module.html",
]

OUTPUT_DIR = "nginx_docs_pdfs"
MERGED_PDF_FILENAME = "nginx_docs_merged.pdf"

################################################################################
# LOGGING SETUP
################################################################################

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

################################################################################
# HELPER: check wkhtmltopdf
################################################################################

def check_wkhtmltopdf_version():
    """
    Prints wkhtmltopdf version details and warns if it's old or missing SSL.
    """
    try:
        cmd = [WKHTMLTOPDF_PATH, "--version"]
        ver_output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8", "replace")
        logging.info(f"wkhtmltopdf version info:\n{ver_output}")
        # Optional: parse the version if needed
    except Exception as ex:
        logging.warning("Could not run wkhtmltopdf --version. Make sure it's installed and the path is correct.")
        logging.warning(str(ex))

################################################################################
# MAIN
################################################################################

def main():
    check_wkhtmltopdf_version()

    # 1) Prepare pdfkit configuration
    pdfkit_config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

    # 2) Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    downloaded_pdfs = []

    # 3) For each URL, attempt from_url => fallback to from_string
    for i, url in enumerate(URLS_IN_ORDER, start=1):
        safe_base = url.split("/")[-1]
        if not safe_base:
            # e.g. trailing slash => use "index"
            safe_base = "index"
        safe_name = f"{i:03d}_{safe_base.replace('.html','')}.pdf"
        out_path = os.path.join(OUTPUT_DIR, safe_name)

        logging.info(f"({i}/{len(URLS_IN_ORDER)}) Converting: {url} -> {out_path}")

        if os.path.isfile(out_path):
            logging.info(f"   Already exists, skipping. Delete it if you want to rebuild.")
            downloaded_pdfs.append(out_path)
            continue

        try:
            # Method 1: Directly from_url (let wkhtmltopdf fetch)
            pdfkit.from_url(
                url,
                out_path,
                configuration=pdfkit_config,
                options=PDFKIT_OPTIONS
            )
            downloaded_pdfs.append(out_path)
            logging.info(f"   Success via from_url()")
        except Exception as e_url:
            logging.warning(f"   from_url() failed: {e_url}")
            logging.info("   Trying from_string() fallback...")

            # Fallback: use requests to fetch HTML, then pass it to pdfkit.from_string()
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                html_content = resp.text

                pdfkit.from_string(
                    html_content,
                    out_path,
                    configuration=pdfkit_config,
                    options=PDFKIT_OPTIONS
                )
                downloaded_pdfs.append(out_path)
                logging.info(f"   Success via from_string() fallback")
            except Exception as e_str:
                logging.error(f"   Fallback also failed for {url}: {e_str}")
                continue  # skip adding out_path

        # Sleep a bit between downloads
        time.sleep(REQUEST_DELAY)

    # 4) Merge all PDFs
    logging.info(f"Starting merge of {len(downloaded_pdfs)} PDFs into '{MERGED_PDF_FILENAME}'...")
    writer = PdfWriter()
    for pdf_file in downloaded_pdfs:
        try:
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                writer.add_page(page)
        except Exception as e:
            logging.error(f"   Error merging {pdf_file}: {e}")

    with open(MERGED_PDF_FILENAME, "wb") as f:
        writer.write(f)

    logging.info("All done!")
    logging.info(f"Final merged PDF is: {MERGED_PDF_FILENAME}")


if __name__ == "__main__":
    main()
