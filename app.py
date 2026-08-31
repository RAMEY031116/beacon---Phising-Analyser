
import streamlit as st
import requests
import socket
import ssl
import os
import re
import io
import base64
import hashlib
from urllib.parse import urlparse
from datetime import datetime, timezone
from ipaddress import ip_address
from difflib import SequenceMatcher
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

import tldextract
from playwright.sync_api import sync_playwright

# Optional QR support
try:
    import cv2
    import numpy as np
    QR_SUPPORT = True
except Exception:
    QR_SUPPORT = False

# Optional clipboard QR support
try:
    from streamlit_paste_button import paste_image_button
    CLIPBOARD_QR_SUPPORT = True
except Exception:
    paste_image_button = None
    CLIPBOARD_QR_SUPPORT = False


# ------------------------------------------------------------
# PAGE SETUP
# ------------------------------------------------------------

st.set_page_config(
    page_title="Yeti Check",
    layout="wide"
)

MAX_LINKS_PER_CHECK = 8
USE_PHISHTANK = True
USE_OPENPHISH = True
OPENPHISH_FEED = "https://openphish.com/feed.txt"


def get_secret(name):
    """
    Read secrets safely from Streamlit Cloud first,
    then fall back to environment variables.
    """
    try:
        value = st.secrets.get(
            name,
            ""
        )
        if value:
            return str(value)
    except Exception:
        pass

    return os.getenv(
        name,
        ""
    )


GOOGLE_WEB_RISK_API_KEY = get_secret(
    "GOOGLE_WEB_RISK_API_KEY"
)

PHISHTANK_APP_KEY = get_secret(
    "PHISHTANK_APP_KEY"
)


# ------------------------------------------------------------
# THEME-SAFE STYLE
# ------------------------------------------------------------

st.markdown(
    """
    <style>
    /*
    Yeti follows the active Streamlit Light/Dark theme.
    These variables are provided by Streamlit itself.
    */
    :root {
        --yeti-bg: var(--background-color);
        --yeti-surface: var(--secondary-background-color);
        --yeti-text: var(--text-color);
        --yeti-accent: var(--primary-color);
        --yeti-border: color-mix(in srgb, var(--text-color) 18%, transparent);
        --yeti-muted: color-mix(in srgb, var(--text-color) 66%, transparent);
    }

    html, body, .stApp {
        background: var(--yeti-bg) !important;
        color: var(--yeti-text) !important;
    }

    .block-container {
        max-width: 1080px;
        padding-top: 1.2rem;
        padding-bottom: 3rem;
    }

    /*
    Remove Streamlit's dark top strip / decoration.
    The app still works normally without it.
    */
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 0 !important;
        min-height: 0 !important;
    }

    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"] {
        display: none !important;
    }

    #MainMenu,
    footer {
        visibility: hidden !important;
    }

    /* Header / Yeti logo */
    .yeti-header {
        display: flex;
        justify-content: center;
        margin: 0.15rem 0 0.2rem 0;
    }

    .yeti-home {
        display: inline-flex;
        align-items: center;
        gap: 0.7rem;
        text-decoration: none !important;
        padding: 0.35rem 0.55rem;
        border-radius: 12px;
        color: var(--yeti-text) !important;
    }

    .yeti-home:hover {
        background: var(--yeti-surface) !important;
    }

    .yeti-logo {
        width: 52px;
        height: 52px;
        flex: 0 0 52px;
    }

    .yeti-wordmark {
        font-size: 2.15rem;
        font-weight: 750;
        letter-spacing: -0.035em;
        color: var(--yeti-text) !important;
    }

    .yeti-subtitle {
        text-align: center;
        color: var(--yeti-muted) !important;
        margin-bottom: 1.15rem;
        font-size: 0.95rem;
    }

    /* Cards */
    .result-card {
        background: var(--yeti-surface) !important;
        border: 1px solid var(--yeti-border) !important;
        border-radius: 10px;
        padding: 0.8rem 0.95rem;
        margin: 0.65rem 0;
        color: var(--yeti-text) !important;
    }

    .result-card * {
        color: var(--yeti-text) !important;
    }

    .result-title {
        font-size: 1.08rem;
        font-weight: 700;
        color: var(--yeti-text) !important;
    }

    .muted {
        color: var(--yeti-muted) !important;
    }

    /* General text */
    .stApp p,
    .stApp span,
    .stApp label,
    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp h4,
    .stApp h5,
    .stApp h6 {
        color: var(--yeti-text) !important;
    }

    /* Inputs */
    .stTextArea textarea,
    .stTextInput input {
        background: var(--yeti-surface) !important;
        color: var(--yeti-text) !important;
        caret-color: var(--yeti-text) !important;
        border: 1px solid var(--yeti-border) !important;
        border-radius: 8px !important;
    }

    .stTextArea textarea::placeholder,
    .stTextInput input::placeholder {
        color: var(--yeti-muted) !important;
        opacity: 0.9 !important;
    }

    /* Metrics */
    div[data-testid="stMetric"] {
        background: var(--yeti-surface) !important;
        border: 1px solid var(--yeti-border) !important;
        border-radius: 9px !important;
        padding: 0.65rem !important;
    }

    div[data-testid="stMetric"] *,
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] * {
        color: var(--yeti-text) !important;
    }

    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] * {
        color: var(--yeti-muted) !important;
    }

    /* Expanders */
    div[data-testid="stExpander"] {
        background: var(--yeti-surface) !important;
        border: 1px solid var(--yeti-border) !important;
        border-radius: 9px !important;
        overflow: hidden !important;
    }

    div[data-testid="stExpander"] details,
    div[data-testid="stExpander"] summary {
        background: var(--yeti-surface) !important;
        color: var(--yeti-text) !important;
    }

    div[data-testid="stExpander"] summary:hover {
        background: color-mix(
            in srgb,
            var(--yeti-surface) 88%,
            var(--yeti-text) 12%
        ) !important;
    }

    div[data-testid="stExpander"] *,
    div[data-testid="stExpander"] svg {
        color: var(--yeti-text) !important;
        fill: currentColor !important;
    }

    /* Alerts */
    div[data-testid="stAlert"],
    div[data-testid="stNotification"] {
        color: var(--yeti-text) !important;
    }

    div[data-testid="stAlert"] *,
    div[data-testid="stNotification"] * {
        color: var(--yeti-text) !important;
    }

    /* Buttons - theme aware, always readable */
    .stButton > button,
    div[data-testid="stFormSubmitButton"] > button,
    div[data-testid="stDownloadButton"] button {
        background: var(--yeti-accent) !important;
        color: #ffffff !important;
        border: 1px solid var(--yeti-accent) !important;
        border-radius: 8px !important;
        font-weight: 650 !important;
        min-height: 2.55rem;
    }

    .stButton > button *,
    div[data-testid="stFormSubmitButton"] > button *,
    div[data-testid="stDownloadButton"] button * {
        color: #ffffff !important;
    }

    .stButton > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover,
    div[data-testid="stDownloadButton"] button:hover {
        filter: brightness(1.08);
        color: #ffffff !important;
    }

    /* Uploaders */
    section[data-testid="stFileUploaderDropzone"] {
        background: var(--yeti-surface) !important;
        color: var(--yeti-text) !important;
        border-color: var(--yeti-border) !important;
    }

    section[data-testid="stFileUploaderDropzone"] * {
        color: var(--yeti-text) !important;
    }

    section[data-testid="stFileUploaderDropzone"] button {
        background: var(--yeti-accent) !important;
        color: #ffffff !important;
        border: 1px solid var(--yeti-accent) !important;
    }

    section[data-testid="stFileUploaderDropzone"] button * {
        color: #ffffff !important;
    }

    /* Screenshot */
    div[data-testid="stImage"] {
        max-width: 820px;
        margin-left: auto;
        margin-right: auto;
    }

    div[data-testid="stImage"] img {
        border: 1px solid var(--yeti-border);
        border-radius: 10px;
        background: var(--yeti-surface);
    }

    hr {
        border-color: var(--yeti-border) !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# HEADER / CLICKABLE LOGO
# ------------------------------------------------------------

st.markdown(
    """
    <div class="yeti-header">
        <a class="yeti-home" href="./" target="_self" title="Reload Yeti Check">
            <svg class="yeti-logo" viewBox="0 0 64 64" aria-label="Yeti Check logo">
                <circle cx="32" cy="32" r="29" fill="#ffffff" stroke="#2e5f8a" stroke-width="3"/>
                <path d="M15 31 L23 18 L29 27 L35 15 L49 32"
                      fill="#dcebf5" stroke="#2e5f8a" stroke-width="2.5"
                      stroke-linejoin="round"/>
                <path d="M18 37 C20 26, 44 26, 46 37
                         C46 49, 39 55, 32 55
                         C25 55, 18 49, 18 37Z"
                      fill="#edf4f8" stroke="#224867" stroke-width="2.5"/>
                <circle cx="27" cy="38" r="2.5" fill="#17212b"/>
                <circle cx="37" cy="38" r="2.5" fill="#17212b"/>
                <path d="M28 46 Q32 49 36 46"
                      fill="none" stroke="#17212b" stroke-width="2.2"
                      stroke-linecap="round"/>
                <path d="M20 34 Q15 31 15 39"
                      fill="none" stroke="#224867" stroke-width="2.5"
                      stroke-linecap="round"/>
                <path d="M44 34 Q49 31 49 39"
                      fill="none" stroke="#224867" stroke-width="2.5"
                      stroke-linecap="round"/>
            </svg>
            <span class="yeti-wordmark">Yeti Check</span>
        </a>
    </div>
    <div class="yeti-subtitle">
        Check websites, messages, emails and QR codes before you trust them
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# WHAT YETI DOES
# ------------------------------------------------------------

with st.expander("What Yeti Check does"):
    st.write(
        "Yeti Check helps you investigate suspicious links before opening or trusting them. "
        "You can paste one link, several links, a whole message, upload an email file, "
        "or check a QR code."
    )
    st.write(
        "It checks where links really go, whether the website is working, domain age, "
        "HTTPS certificates, redirects, lookalike domains, phishing feeds, login forms, "
        "and other warning signs. It also tries to show a safe preview of the website."
    )
    st.write(
        "Yeti Check is an investigation aid. A low-risk result does not guarantee that a website is genuine."
    )


# ------------------------------------------------------------
# KNOWN BRANDS / SHORTENERS
# ------------------------------------------------------------

KNOWN_BRANDS = {
    "microsoft": ["microsoft.com", "live.com", "microsoftonline.com", "office.com", "outlook.com"],
    "google": ["google.com", "gmail.com", "youtube.com"],
    "apple": ["apple.com", "icloud.com"],
    "paypal": ["paypal.com"],
    "amazon": ["amazon.com", "amazon.co.uk"],
    "github": ["github.com"],
    "linkedin": ["linkedin.com"],
    "dropbox": ["dropbox.com"],
    "facebook": ["facebook.com"],
    "instagram": ["instagram.com"],
    "netflix": ["netflix.com"],
    "docusign": ["docusign.com", "docusign.net"]
}

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "cutt.ly", "rb.gy",
    "is.gd", "buff.ly", "ow.ly", "rebrand.ly", "shorturl.at"
}


# ------------------------------------------------------------
# URL EXTRACTION
# ------------------------------------------------------------

def clean_url(value):
    value = value.strip().strip(".,);]>}\"'")
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    return value


def extract_urls_from_text(text):
    """
    Supports:
    - one full URL
    - several URLs, one per line
    - bare domains such as tesco.com
    - URLs mixed into a full email or message
    """

    if not text:
        return []

    urls = []

    # Full http/https/www links anywhere in the pasted text.
    pattern = re.compile(
        r'(?:(?:https?://)|(?:www\.))[^\s<>"\']+',
        re.IGNORECASE
    )

    for item in pattern.findall(
        text
    ):
        item = clean_url(
            item
        )

        if item not in urls:
            urls.append(
                item
            )

    # Bare domains on separate lines.
    bare_pattern = re.compile(
        r'^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
        r'(?::\d+)?(?:/[^\s]*)?$'
    )

    for line in text.splitlines():
        candidate = line.strip().strip(
            ".,);]>}\"'"
        )

        if not candidate:
            continue

        if bare_pattern.match(
            candidate
        ):
            candidate = clean_url(
                candidate
            )

            if candidate not in urls:
                urls.append(
                    candidate
                )

    return urls


# ------------------------------------------------------------
# QR
# ------------------------------------------------------------

def decode_qr_codes(uploaded_file):
    if not QR_SUPPORT or uploaded_file is None:
        return []

    try:
        raw = uploaded_file.getvalue()
        arr = np.frombuffer(raw, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        if image is None:
            return []

        detector = cv2.QRCodeDetector()
        values = []

        try:
            ok, decoded, points, _ = detector.detectAndDecodeMulti(image)

            if ok:
                for item in decoded:
                    if item:
                        values.append(item.strip())
        except Exception:
            pass

        if not values:
            try:
                value, points, _ = detector.detectAndDecode(image)

                if value:
                    values.append(value.strip())
            except Exception:
                pass

        return values

    except Exception:
        return []


def decode_qr_from_pasted_image(image):
    if not QR_SUPPORT or image is None:
        return []

    try:
        rgb = np.array(image.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        detector = cv2.QRCodeDetector()
        values = []

        try:
            ok, decoded, points, _ = detector.detectAndDecodeMulti(bgr)

            if ok:
                for item in decoded:
                    if item:
                        values.append(item.strip())
        except Exception:
            pass

        if not values:
            try:
                value, points, _ = detector.detectAndDecode(bgr)

                if value:
                    values.append(value.strip())
            except Exception:
                pass

        return values

    except Exception:
        return []


# ------------------------------------------------------------
# EMAIL ANALYSIS
# ------------------------------------------------------------

class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_href = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.current_href = dict(attrs).get("href")
            self.current_text = []

    def handle_data(self, data):
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current_href is not None:
            text = " ".join(self.current_text).strip()

            self.links.append(
                {
                    "href": self.current_href,
                    "text": text
                }
            )

            self.current_href = None
            self.current_text = []


def get_email_address_domain(value):
    if not value:
        return ""

    match = re.search(r'@([A-Za-z0-9.-]+\.[A-Za-z]{2,})', value)

    if not match:
        return ""

    return match.group(1).lower()


def parse_authentication_results(message):
    combined = " ".join(
        message.get_all("Authentication-Results", [])
        + message.get_all("ARC-Authentication-Results", [])
    ).lower()

    result = {
        "spf": "Unknown",
        "dkim": "Unknown",
        "dmarc": "Unknown"
    }

    for name in ("spf", "dkim", "dmarc"):
        match = re.search(
            rf'\b{name}=(pass|fail|softfail|neutral|none|temperror|permerror)',
            combined
        )

        if match:
            result[name] = match.group(1).upper()

    return result


def analyse_eml(uploaded_file):
    result = {
        "urls": [],
        "from": "",
        "reply_to": "",
        "subject": "",
        "auth": {
            "spf": "Unknown",
            "dkim": "Unknown",
            "dmarc": "Unknown"
        },
        "warnings": [],
        "link_mismatches": []
    }

    if uploaded_file is None:
        return result

    try:
        message = BytesParser(
            policy=policy.default
        ).parsebytes(
            uploaded_file.getvalue()
        )

        result["from"] = str(
            message.get("From", "")
        )

        result["reply_to"] = str(
            message.get("Reply-To", "")
        )

        result["subject"] = str(
            message.get("Subject", "")
        )

        result["auth"] = parse_authentication_results(
            message
        )

        from_domain = get_email_address_domain(
            result["from"]
        )

        reply_domain = get_email_address_domain(
            result["reply_to"]
        )

        if (
            from_domain
            and reply_domain
            and from_domain != reply_domain
        ):
            result["warnings"].append(
                f"Reply-To uses {reply_domain}, which is different from the sender domain {from_domain}."
            )

        for name in ("spf", "dkim", "dmarc"):
            if result["auth"].get(name) == "FAIL":
                result["warnings"].append(
                    f"{name.upper()} is recorded as FAIL in the email authentication results."
                )

        text_parts = []
        html_parts = []

        if message.is_multipart():
            parts = message.walk()
        else:
            parts = [message]

        for part in parts:
            content_type = part.get_content_type()

            if content_type == "text/plain":
                try:
                    text_parts.append(
                        part.get_content()
                    )
                except Exception:
                    pass

            elif content_type == "text/html":
                try:
                    html_parts.append(
                        part.get_content()
                    )
                except Exception:
                    pass

        for text_part in text_parts:
            for url in extract_urls_from_text(text_part):
                if url not in result["urls"]:
                    result["urls"].append(url)

        for html_part in html_parts:
            parser = AnchorParser()

            try:
                parser.feed(html_part)
            except Exception:
                continue

            for item in parser.links:
                href = item.get("href") or ""
                visible = item.get("text") or ""

                if href.startswith(("http://", "https://", "www.")):
                    href = clean_url(href)

                    if href not in result["urls"]:
                        result["urls"].append(href)

                    visible_urls = extract_urls_from_text(
                        visible
                    )

                    if visible_urls:
                        visible_domain = get_registered_domain(
                            get_hostname(
                                visible_urls[0]
                            )
                        )

                        target_domain = get_registered_domain(
                            get_hostname(
                                href
                            )
                        )

                        if (
                            visible_domain
                            and target_domain
                            and visible_domain != target_domain
                        ):
                            result["link_mismatches"].append(
                                f"Visible link says {visible_domain}, but clicking it goes to {target_domain}."
                            )

        if result["link_mismatches"]:
            result["warnings"].extend(
                result["link_mismatches"]
            )

    except Exception as error:
        result["warnings"].append(
            f"The email file could not be fully analysed: {error}"
        )

    return result


# ------------------------------------------------------------
# DOMAIN / NETWORK
# ------------------------------------------------------------

def get_hostname(url):
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def get_registered_domain(hostname):
    if not hostname:
        return ""

    result = tldextract.extract(hostname)

    if not result.domain or not result.suffix:
        return hostname.lower()

    return f"{result.domain}.{result.suffix}".lower()


def get_domain_name_only(registered_domain):
    return tldextract.extract(
        registered_domain
    ).domain.lower()


def is_private_or_local_ip(value):
    try:
        address = ip_address(value)

        return (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        )

    except ValueError:
        return False


def resolve_ip(hostname):
    try:
        records = socket.getaddrinfo(
            hostname,
            None
        )

        values = []

        for record in records:
            address = record[4][0]

            if address not in values:
                values.append(address)

        return values

    except Exception:
        return []


def check_host_is_safe(hostname):
    if not hostname:
        return False, "Invalid hostname"

    if hostname.lower() in (
        "localhost",
        "localhost.localdomain"
    ):
        return False, "Local addresses are not allowed"

    addresses = resolve_ip(
        hostname
    )

    if not addresses:
        return False, "The hostname could not be resolved"

    for address in addresses:
        if is_private_or_local_ip(address):
            return False, "Private or local network addresses are not allowed"

    return True, ""


# ------------------------------------------------------------
# HTTP / REDIRECTS
# ------------------------------------------------------------

def safe_request(url):
    current_url = url
    redirects = []
    response = None

    for _ in range(8):
        hostname = get_hostname(
            current_url
        )

        safe, message = check_host_is_safe(
            hostname
        )

        if not safe:
            raise Exception(message)

        response = requests.get(
            current_url,
            timeout=15,
            allow_redirects=False,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )
            }
        )

        if response.status_code in (
            301, 302, 303, 307, 308
        ):
            location = response.headers.get(
                "Location"
            )

            if not location:
                break

            next_url = requests.compat.urljoin(
                current_url,
                location
            )

            redirects.append(
                next_url
            )

            current_url = next_url
            continue

        return response, current_url, redirects

    return response, current_url, redirects


def classify_http_status(status_code):
    if status_code is None:
        return "Unknown"

    if 200 <= status_code < 300:
        return "Working"

    if status_code in (401, 403):
        return "Access restricted"

    if status_code == 404:
        return "Not found"

    if status_code == 429:
        return "Rate limited"

    if 500 <= status_code < 600:
        return "Server error"

    if 300 <= status_code < 400:
        return "Redirect"

    return f"HTTP {status_code}"


def count_registered_domain_changes(
    original_url,
    redirects,
    final_url
):
    urls = [original_url] + list(redirects) + [final_url]
    domains = []

    for item in urls:
        domain = get_registered_domain(
            get_hostname(item)
        )

        if domain and (
            not domains
            or domain != domains[-1]
        ):
            domains.append(domain)

    return max(0, len(domains) - 1), domains


# ------------------------------------------------------------
# RDAP / CERTIFICATE
# ------------------------------------------------------------

def get_rdap_information(domain):
    result = {
        "registrar": "Unknown",
        "created": None,
        "age_days": None
    }

    if not domain:
        return result

    try:
        response = requests.get(
            f"https://rdap.org/domain/{domain}",
            timeout=12,
            headers={
                "User-Agent": "YetiCheck/1.0"
            }
        )

        if response.status_code != 200:
            return result

        data = response.json()

        for entity in data.get("entities", []):
            if "registrar" in entity.get("roles", []):
                vcard = entity.get(
                    "vcardArray",
                    []
                )

                if len(vcard) == 2:
                    for field in vcard[1]:
                        if (
                            len(field) >= 4
                            and field[0] == "fn"
                        ):
                            result["registrar"] = field[3]
                            break

        for event in data.get("events", []):
            action = event.get(
                "eventAction",
                ""
            ).lower()

            if action in (
                "registration",
                "registered",
                "creation",
                "created"
            ):
                date_text = event.get(
                    "eventDate"
                )

                if date_text:
                    created = datetime.fromisoformat(
                        date_text.replace(
                            "Z",
                            "+00:00"
                        )
                    )

                    result["created"] = created

                    result["age_days"] = (
                        datetime.now(timezone.utc)
                        - created
                    ).days

                    break

    except Exception:
        pass

    return result


def get_tls_information(hostname):
    result = {
        "valid": False,
        "issuer": "Unknown",
        "expires": "Unknown"
    }

    try:
        context = ssl.create_default_context()

        with socket.create_connection(
            (hostname, 443),
            timeout=8
        ) as sock:

            with context.wrap_socket(
                sock,
                server_hostname=hostname
            ) as secure_socket:

                certificate = secure_socket.getpeercert()

                result["valid"] = True

                issuer_names = []

                for group in certificate.get(
                    "issuer",
                    []
                ):
                    for key, value in group:
                        if key == "organizationName":
                            issuer_names.append(value)

                if issuer_names:
                    result["issuer"] = ", ".join(
                        issuer_names
                    )

                result["expires"] = certificate.get(
                    "notAfter",
                    "Unknown"
                )

    except Exception:
        pass

    return result


def certificate_days_left(expiry_text):
    if not expiry_text or expiry_text == "Unknown":
        return None

    try:
        expires = datetime.strptime(
            expiry_text,
            "%b %d %H:%M:%S %Y %Z"
        ).replace(
            tzinfo=timezone.utc
        )

        return (
            expires
            - datetime.now(timezone.utc)
        ).days

    except Exception:
        return None


# ------------------------------------------------------------
# PHISHING FEEDS
# ------------------------------------------------------------

@st.cache_data(
    ttl=1800,
    show_spinner=False
)
def get_openphish_feed():
    if not USE_OPENPHISH:
        return set()

    try:
        response = requests.get(
            OPENPHISH_FEED,
            timeout=15,
            headers={
                "User-Agent": "YetiCheck/1.0"
            }
        )

        if response.status_code != 200:
            return set()

        return {
            line.strip()
            for line in response.text.splitlines()
            if line.strip()
        }

    except Exception:
        return set()


def check_openphish(url):
    result = {
        "checked": False,
        "confirmed": False
    }

    feed = get_openphish_feed()

    if not feed:
        return result

    result["checked"] = True
    clean = url.rstrip("/")

    for item in feed:
        if item.rstrip("/") == clean:
            result["confirmed"] = True
            break

    return result



def check_google_webrisk(url):
    """
    Check Google's Web Risk live lookup service for phishing /
    social-engineering reports.

    A positive result is strong evidence that Google currently
    considers the URL unsafe. A negative result is NOT a guarantee
    that the site is genuine.
    """

    result = {
        "configured": bool(
            GOOGLE_WEB_RISK_API_KEY
        ),
        "checked": False,
        "confirmed": False,
        "threat_types": [],
        "error": ""
    }

    if not GOOGLE_WEB_RISK_API_KEY:
        return result

    try:
        response = requests.get(
            "https://webrisk.googleapis.com/v1/uris:search",
            params=[
                (
                    "threatTypes",
                    "SOCIAL_ENGINEERING"
                ),
                (
                    "uri",
                    url
                ),
                (
                    "key",
                    GOOGLE_WEB_RISK_API_KEY
                )
            ],
            timeout=12,
            headers={
                "User-Agent": "YetiCheck/1.0"
            }
        )

        if response.status_code == 200:
            result["checked"] = True

            data = response.json()

            threat = data.get(
                "threat"
            )

            if threat:
                result["confirmed"] = True
                result["threat_types"] = threat.get(
                    "threatTypes",
                    []
                )

        else:
            result["error"] = (
                f"Google Web Risk returned HTTP {response.status_code}"
            )

    except Exception as error:
        result["error"] = str(
            error
        )

    return result


def check_google_webrisk_chain(
    original_url,
    redirects,
    final_url
):
    """
    Check every important URL in the redirect chain, because a
    harmless-looking short link may redirect to a known phishing URL.
    """

    checked_urls = []

    for item in (
        [original_url]
        + list(redirects)
        + [final_url]
    ):
        if item and item not in checked_urls:
            checked_urls.append(
                item
            )

    overall = {
        "configured": bool(
            GOOGLE_WEB_RISK_API_KEY
        ),
        "checked": False,
        "confirmed": False,
        "matched_url": "",
        "threat_types": [],
        "error": ""
    }

    for item in checked_urls:
        result = check_google_webrisk(
            item
        )

        if result.get(
            "checked"
        ):
            overall["checked"] = True

        if result.get(
            "error"
        ):
            overall["error"] = result[
                "error"
            ]

        if result.get(
            "confirmed"
        ):
            overall["confirmed"] = True
            overall["matched_url"] = item
            overall["threat_types"] = result.get(
                "threat_types",
                []
            )
            break

    return overall


def check_phishtank(url):
    result = {
        "checked": False,
        "confirmed": False
    }

    if not USE_PHISHTANK:
        return result

    try:
        response = requests.post(
            "https://checkurl.phishtank.com/checkurl/",
            data={
                "url": url,
                "format": "json",
                **(
                    {
                        "app_key": PHISHTANK_APP_KEY
                    }
                    if PHISHTANK_APP_KEY
                    else {}
                )
            },
            timeout=10,
            headers={
                "User-Agent": "YetiCheck/1.0"
            }
        )

        if response.status_code != 200:
            return result

        details = response.json().get(
            "results",
            {}
        )

        result["checked"] = True

        in_database = str(
            details.get(
                "in_database",
                False
            )
        ).lower() in (
            "true", "yes", "1"
        )

        verified = str(
            details.get(
                "verified",
                False
            )
        ).lower() in (
            "true", "yes", "1"
        )

        valid = str(
            details.get(
                "valid",
                False
            )
        ).lower() in (
            "true", "yes", "1"
        )

        result["confirmed"] = (
            in_database
            and verified
            and valid
        )

    except Exception:
        pass

    return result


# ------------------------------------------------------------
# LOOKALIKE / BRAND
# ------------------------------------------------------------

def is_official_brand_domain(
    brand,
    registered_domain
):
    return registered_domain.lower() in KNOWN_BRANDS.get(
        brand,
        []
    )


def simple_edit_distance(first, second):
    rows = len(first) + 1
    columns = len(second) + 1

    table = [
        [0] * columns
        for _ in range(rows)
    ]

    for row in range(rows):
        table[row][0] = row

    for column in range(columns):
        table[0][column] = column

    for row in range(1, rows):
        for column in range(1, columns):
            cost = (
                0
                if first[row - 1] == second[column - 1]
                else 1
            )

            table[row][column] = min(
                table[row - 1][column] + 1,
                table[row][column - 1] + 1,
                table[row - 1][column - 1] + cost
            )

    return table[-1][-1]


def normalise_lookalike_text(value):
    replacements = {
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t"
    }

    value = value.lower()

    for old, new in replacements.items():
        value = value.replace(
            old,
            new
        )

    return value


def detect_lookalike_domain(
    registered_domain
):
    domain_name = get_domain_name_only(
        registered_domain
    )

    if not domain_name:
        return None

    normalised = normalise_lookalike_text(
        domain_name
    )

    for brand in KNOWN_BRANDS:
        if is_official_brand_domain(
            brand,
            registered_domain
        ):
            continue

        normal_brand = normalise_lookalike_text(
            brand
        )

        if normalised == normal_brand:
            return brand

        if (
            brand in domain_name
            and domain_name != brand
        ):
            return brand

        if len(brand) >= 5:
            distance = simple_edit_distance(
                normalised,
                normal_brand
            )

            similarity = SequenceMatcher(
                None,
                normalised,
                normal_brand
            ).ratio()

            if (
                distance == 1
                or similarity >= 0.88
            ):
                return brand

    return None


def detect_claimed_brand(
    hostname,
    page
):
    hostname_lower = hostname.lower()

    title = (
        page.get("title", "")
        or ""
    ).lower()

    site_name = (
        page.get("site_name", "")
        or ""
    ).lower()

    heading = (
        page.get("heading", "")
        or ""
    ).lower()

    password_field = page.get(
        "password_field",
        False
    )

    for brand in KNOWN_BRANDS:
        if brand in hostname_lower:
            return brand

        if (
            brand in site_name
            and site_name.strip()
        ):
            return brand

        phrases = [
            f"{brand} login",
            f"{brand} sign in",
            f"sign in to {brand}",
            f"log in to {brand}",
            f"{brand} account",
            f"{brand} verification",
            f"{brand} security"
        ]

        combined = title + " " + heading

        if any(
            phrase in combined
            for phrase in phrases
        ):
            return brand

        if (
            password_field
            and (
                brand in title
                or brand in heading
            )
        ):
            return brand

    return None


# ------------------------------------------------------------
# URL STRUCTURE
# ------------------------------------------------------------

def get_url_structure_findings(url):
    findings = []

    parsed = urlparse(
        url
    )

    hostname = parsed.hostname or ""

    registered_domain = get_registered_domain(
        hostname
    )

    if registered_domain in SHORTENERS:
        findings.append(
            (
                5,
                "The address uses a URL shortening service."
            )
        )

    if (
        parsed.username
        or parsed.password
    ):
        findings.append(
            (
                20,
                "The URL contains information before the hostname that may hide the real destination."
            )
        )

    if (
        hostname.startswith("xn--")
        or ".xn--" in hostname
    ):
        findings.append(
            (
                22,
                "The domain uses punycode, which can be used for lookalike domain names."
            )
        )

    try:
        ip_address(
            hostname
        )

        findings.append(
            (
                20,
                "The website uses an IP address instead of a normal domain name."
            )
        )

    except ValueError:
        pass

    extracted = tldextract.extract(
        hostname
    )

    if extracted.subdomain:
        parts = [
            item
            for item in extracted.subdomain.split(".")
            if item
        ]

        if len(parts) >= 4:
            findings.append(
                (
                    7,
                    "The address uses an unusually deep subdomain structure."
                )
            )

    if url.count("%") >= 5:
        findings.append(
            (
                5,
                "The URL contains a large amount of encoded text."
            )
        )

    if len(url) > 220:
        findings.append(
            (
                4,
                "The URL is unusually long."
            )
        )

    return findings


# ------------------------------------------------------------
# BROWSER PREVIEW
# ------------------------------------------------------------

def get_browser_path():
    for path in (
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium"
    ):
        if os.path.exists(path):
            return path

    return None


def inspect_page(browser_url):
    result = {
        "title": "Unknown",
        "site_name": "",
        "heading": "",
        "password_field": False,
        "email_field": False,
        "forms": [],
        "screenshot": None,
        "preview_status": "unknown",
        "preview_message": ""
    }

    file_id = hashlib.sha256(
        browser_url.encode(
            "utf-8",
            errors="ignore"
        )
    ).hexdigest()[:12]

    screenshot_path = f"yeti_{file_id}.png"

    try:
        with sync_playwright() as p:
            chromium_path = get_browser_path()

            launch_options = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage"
                ]
            }

            if chromium_path:
                launch_options["executable_path"] = chromium_path

            browser = p.chromium.launch(
                **launch_options
            )

            context = browser.new_context(
                viewport={
                    "width": 1366,
                    "height": 768
                },
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="en-GB",
                extra_http_headers={
                    "Accept-Language": "en-GB,en;q=0.9"
                }
            )

            page = context.new_page()

            response = page.goto(
                browser_url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            try:
                page.wait_for_timeout(
                    1800
                )
            except Exception:
                pass

            try:
                result["title"] = page.title()
            except Exception:
                pass

            body_text = ""

            try:
                body_text = page.locator(
                    "body"
                ).inner_text(
                    timeout=3000
                )
            except Exception:
                pass

            page_text = (
                (result["title"] or "")
                + " "
                + (body_text or "")
            ).lower()

            blocked_phrases = [
                "access denied",
                "you don't have permission to access",
                "request blocked",
                "errors.edgesuite.net"
            ]

            blocked = any(
                phrase in page_text
                for phrase in blocked_phrases
            )

            if response is not None:
                try:
                    if response.status in (
                        401,
                        403,
                        429
                    ):
                        blocked = True
                except Exception:
                    pass

            if blocked:
                result["preview_status"] = "blocked"

                result["preview_message"] = (
                    "The website blocked the automated preview. "
                    "This can happen on legitimate websites and is not counted as evidence of phishing."
                )

                context.close()
                browser.close()
                return result

            result["preview_status"] = "success"

            try:
                meta = page.locator(
                    'meta[property="og:site_name"]'
                )

                if meta.count() > 0:
                    result["site_name"] = (
                        meta.first.get_attribute(
                            "content"
                        )
                        or ""
                    )
            except Exception:
                pass

            try:
                heading = page.locator(
                    "h1"
                )

                if heading.count() > 0:
                    result["heading"] = (
                        heading.first.inner_text(
                            timeout=2000
                        )
                        or ""
                    )
            except Exception:
                pass

            try:
                result["password_field"] = (
                    page.locator(
                        'input[type="password"]'
                    ).count() > 0
                )
            except Exception:
                pass

            try:
                result["email_field"] = (
                    page.locator(
                        'input[type="email"], '
                        'input[name*="email" i], '
                        'input[name*="user" i]'
                    ).count() > 0
                )
            except Exception:
                pass

            try:
                forms = page.locator(
                    "form"
                )

                for i in range(
                    min(
                        forms.count(),
                        20
                    )
                ):
                    action = (
                        forms.nth(i)
                        .get_attribute(
                            "action"
                        )
                        or ""
                    )

                    if action:
                        action = requests.compat.urljoin(
                            page.url,
                            action
                        )

                    result["forms"].append(
                        action
                    )
            except Exception:
                pass

            # Viewport-only screenshot.
            # This avoids very tall images shrinking down and becoming unreadable.
            try:
                page.screenshot(
                    path=screenshot_path,
                    full_page=False
                )

                result["screenshot"] = screenshot_path
            except Exception:
                pass

            context.close()
            browser.close()

    except Exception:
        result["preview_status"] = "failed"

        result["preview_message"] = (
            "The website preview could not be loaded. "
            "The other checks can still be used."
        )

    return result


def render_clickable_preview(
    screenshot_path,
    caption="Website preview"
):
    """
    Show a fixed-size preview.
    Clicking it opens the screenshot at full browser size in a new tab.
    """

    if not screenshot_path or not os.path.exists(
        screenshot_path
    ):
        return

    try:
        image_bytes = Path(
            screenshot_path
        ).read_bytes()

        encoded = base64.b64encode(
            image_bytes
        ).decode(
            "ascii"
        )

        data_url = (
            "data:image/png;base64,"
            + encoded
        )

        st.markdown(
            f"""
            <div class="preview-wrap">
                <a href="{data_url}" target="_blank" title="Open larger screenshot">
                    <img src="{data_url}" alt="{caption}">
                </a>
                <div class="preview-note">
                    Click the preview to open it larger.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    except Exception:
        st.image(
            screenshot_path,
            caption=caption,
            use_container_width=True
        )


# ------------------------------------------------------------
# FORM SERVICE ALLOWLIST
# ------------------------------------------------------------

def is_known_auth_service(domain):
    return domain.lower() in {
        "microsoftonline.com",
        "live.com",
        "google.com",
        "okta.com",
        "auth0.com",
        "stripe.com",
        "paypal.com"
    }


# ------------------------------------------------------------
# ANALYSE URL
# ------------------------------------------------------------

def analyse_url(url):
    result = {
        "url": url,
        "score": 0,
        "reasons": [],
        "final_url": url,
        "status_code": None,
        "site_status": "Unknown",
        "content_type": "Unknown",
        "server": "Unknown",
        "redirects": [],
        "hostname": "",
        "registered_domain": "",
        "ip_addresses": [],
        "rdap": {},
        "tls": {},
        "page": {},
        "phish_tank": {},
        "openphish": {},
        "google_webrisk": {}
    }

    response, final_url, redirects = safe_request(
        url
    )

    result["final_url"] = final_url
    result["redirects"] = redirects

    if response is not None:
        result["status_code"] = response.status_code

        result["site_status"] = classify_http_status(
            response.status_code
        )

        result["content_type"] = response.headers.get(
            "Content-Type",
            "Unknown"
        )

        result["server"] = response.headers.get(
            "Server",
            "Unknown"
        )

    hostname = get_hostname(
        final_url
    )

    registered_domain = get_registered_domain(
        hostname
    )

    result["hostname"] = hostname
    result["registered_domain"] = registered_domain
    result["ip_addresses"] = resolve_ip(
        hostname
    )

    # Reputation databases
    result["google_webrisk"] = (
        check_google_webrisk_chain(
            url,
            redirects,
            final_url
        )
    )

    result["phish_tank"] = check_phishtank(
        final_url
    )

    result["openphish"] = check_openphish(
        final_url
    )

    if result["google_webrisk"].get(
        "confirmed"
    ):
        result["score"] += 90

        result["reasons"].append(
            "Google Web Risk reports this URL as a social-engineering/phishing threat."
        )

    if result["phish_tank"].get(
        "confirmed"
    ):
        result["score"] += 75

        result["reasons"].append(
            "The address appears in the PhishTank verified phishing database."
        )

    if result["openphish"].get(
        "confirmed"
    ):
        result["score"] += 75

        result["reasons"].append(
            "The address appears in the OpenPhish community phishing feed."
        )

    # Domain age
    result["rdap"] = get_rdap_information(
        registered_domain
    )

    age = result["rdap"].get(
        "age_days"
    )

    if age is not None:
        if age < 7:
            result["score"] += 20

            result["reasons"].append(
                "The domain was registered less than 7 days ago."
            )

        elif age < 30:
            result["score"] += 12

            result["reasons"].append(
                "The domain was registered less than 30 days ago."
            )

        elif age < 90:
            result["score"] += 5

            result["reasons"].append(
                "The domain was registered less than 3 months ago."
            )

    # HTTPS
    if final_url.startswith(
        "https://"
    ):
        result["tls"] = get_tls_information(
            hostname
        )

        if not result["tls"].get(
            "valid"
        ):
            result["score"] += 18

            result["reasons"].append(
                "Yeti Check could not validate the HTTPS certificate."
            )

    else:
        result["tls"] = {
            "valid": False,
            "issuer": "Unknown",
            "expires": "Unknown"
        }

        result["score"] += 15

        result["reasons"].append(
            "The final page is not using HTTPS."
        )

    # URL structure
    for points, reason in get_url_structure_findings(
        final_url
    ):
        result["score"] += points
        result["reasons"].append(
            reason
        )

    # Redirect changes
    changes, domains = count_registered_domain_changes(
        url,
        redirects,
        final_url
    )

    if changes == 1:
        result["score"] += 8

        result["reasons"].append(
            "The link redirected to a different registered domain."
        )

    elif changes >= 2:
        result["score"] += 16

        result["reasons"].append(
            "The link moved across several different registered domains."
        )

    # Lookalike
    lookalike = detect_lookalike_domain(
        registered_domain
    )

    if lookalike:
        result["score"] += 32

        result["reasons"].append(
            f"The domain name looks similar to {lookalike.title()}, "
            "but it is not one of that brand's known official domains."
        )

    # Page
    result["page"] = inspect_page(
        url
    )

    preview_ok = (
        result["page"].get(
            "preview_status"
        )
        == "success"
    )

    if preview_ok:
        brand = detect_claimed_brand(
            hostname,
            result["page"]
        )

        if (
            brand
            and not is_official_brand_domain(
                brand,
                registered_domain
            )
        ):
            result["score"] += 40

            result["reasons"].append(
                f"The page appears to identify as {brand.title()}, "
                f"but the registered domain is {registered_domain}."
            )

        password_field = result["page"].get(
            "password_field",
            False
        )

        if password_field:
            result["score"] += 3

            result["reasons"].append(
                "The page contains a password field."
            )

        for action in result["page"].get(
            "forms",
            []
        ):
            if not action:
                continue

            form_domain = get_registered_domain(
                get_hostname(action)
            )

            if (
                form_domain
                and registered_domain
                and form_domain != registered_domain
            ):
                if is_known_auth_service(
                    form_domain
                ):
                    continue

                if password_field:
                    result["score"] += 35

                    result["reasons"].append(
                        "The login form sends information to a different registered domain."
                    )

                else:
                    result["score"] += 12

                    result["reasons"].append(
                        "A form on the page sends information to a different registered domain."
                    )

                break

    if result["status_code"] == 404:
        result["reasons"].append(
            "The page returned HTTP 404 and appears not to exist."
        )

    elif (
        result["status_code"] is not None
        and 500 <= result["status_code"] < 600
    ):
        result["reasons"].append(
            "The website returned a server error."
        )

    result["score"] = min(
        result["score"],
        100
    )

    if result["score"] >= 70:
        result["verdict"] = "High Risk"

    elif result["score"] >= 40:
        result["verdict"] = "Suspicious"

    elif result["score"] >= 20:
        result["verdict"] = "Caution"

    else:
        result["verdict"] = "Low Risk"

    return result


# ------------------------------------------------------------
# RESET
# ------------------------------------------------------------

def reset_yeti():
    for key in (
        "yeti_text",
        "qr_upload",
        "eml_upload"
    ):
        if key in st.session_state:
            try:
                del st.session_state[key]
            except Exception:
                pass

    st.session_state["qr_reset_counter"] = (
        st.session_state.get(
            "qr_reset_counter",
            0
        )
        + 1
    )


if "qr_reset_counter" not in st.session_state:
    st.session_state["qr_reset_counter"] = 0


# ------------------------------------------------------------
# INPUT
# ------------------------------------------------------------

current_text = st.session_state.get(
    "yeti_text",
    ""
)

line_count = max(
    1,
    current_text.count("\n") + 1
)

text_height = min(
    280,
    max(
        92,
        65 + line_count * 24
    )
)

pasted_text = st.text_area(
    "Links or message",
    placeholder=(
        "Paste one link, several links one per line, "
        "or paste a whole suspicious email/message and Yeti will find the links"
    ),
    height=text_height,
    key="yeti_text",
    help="For several links, put one link on each line."
)

col_qr, col_email = st.columns(2)

with col_qr:
    st.write("QR code")

    pasted_qr_image = None

    if CLIPBOARD_QR_SUPPORT:
        paste_result = paste_image_button(
            label="Paste QR code",
            text_color="#ffffff",
            background_color="#224867",
            hover_background_color="#2e5f8a",
            key=f"paste_qr_{st.session_state['qr_reset_counter']}",
            errors="ignore"
        )

        if paste_result is not None:
            pasted_qr_image = getattr(
                paste_result,
                "image_data",
                None
            )

    qr_file = st.file_uploader(
        "Upload QR image",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp"
        ],
        key="qr_upload"
    )

with col_email:
    st.write("Email file")

    eml_file = st.file_uploader(
        "Upload .eml email",
        type=["eml"],
        key="eml_upload",
        help=(
            "Yeti can extract links and review sender, Reply-To, "
            "SPF, DKIM and DMARC results stored in the email headers."
        )
    )

button_col1, button_col2 = st.columns(2)

with button_col1:
    submitted = st.button(
        "Check",
        key="check_button",
        use_container_width=True
    )

with button_col2:
    st.button(
        "Reset",
        key="reset_button",
        on_click=reset_yeti,
        use_container_width=True
    )


# ------------------------------------------------------------
# RUN
# ------------------------------------------------------------

if submitted:
    urls = extract_urls_from_text(
        pasted_text
    )

    email_result = analyse_eml(
        eml_file
    )

    for item in email_result.get(
        "urls",
        []
    ):
        if item not in urls:
            urls.append(item)

    for value in decode_qr_from_pasted_image(
        pasted_qr_image
    ):
        for item in extract_urls_from_text(
            value
        ):
            if item not in urls:
                urls.append(item)

    for value in decode_qr_codes(
        qr_file
    ):
        qr_urls = extract_urls_from_text(
            value
        )

        if (
            not qr_urls
            and "." in value
        ):
            qr_urls = [
                clean_url(value)
            ]

        for item in qr_urls:
            if item not in urls:
                urls.append(item)

    if not urls:
        if (
            eml_file is not None
            and email_result.get(
                "warnings"
            )
        ):
            st.warning(
                "The email was analysed, but no website links were found."
            )

        elif (
            qr_file is not None
            or pasted_qr_image is not None
        ):
            st.warning(
                "No website link could be read from the QR code."
            )

        else:
            st.warning(
                "No website links were found. "
                "Paste one link per line or paste the whole message."
            )

        st.stop()

    if len(urls) > MAX_LINKS_PER_CHECK:
        st.warning(
            f"{len(urls)} links were found. "
            f"Yeti will check the first {MAX_LINKS_PER_CHECK}."
        )

        urls = urls[
            :MAX_LINKS_PER_CHECK
        ]

    # Email summary first if an .eml was supplied
    if eml_file is not None:
        with st.expander(
            "Email checks",
            expanded=True
        ):
            st.write(
                "From:",
                email_result.get(
                    "from",
                    "Unknown"
                )
            )

            st.write(
                "Reply-To:",
                email_result.get(
                    "reply_to",
                    "Not set"
                )
                or "Not set"
            )

            auth = email_result.get(
                "auth",
                {}
            )

            c1, c2, c3 = st.columns(3)

            with c1:
                st.metric(
                    "SPF",
                    auth.get(
                        "spf",
                        "Unknown"
                    )
                )

            with c2:
                st.metric(
                    "DKIM",
                    auth.get(
                        "dkim",
                        "Unknown"
                    )
                )

            with c3:
                st.metric(
                    "DMARC",
                    auth.get(
                        "dmarc",
                        "Unknown"
                    )
                )

            if email_result.get(
                "warnings"
            ):
                st.write(
                    "Email findings:"
                )

                for warning in email_result[
                    "warnings"
                ][:6]:
                    st.write(
                        warning
                    )

    results = []
    progress = st.progress(0)
    status = st.empty()

    for index, url in enumerate(
        urls,
        start=1
    ):
        status.write(
            f"Checking {index} of {len(urls)}"
        )

        try:
            result = analyse_url(
                url
            )

        except Exception as error:
            result = {
                "url": url,
                "final_url": url,
                "verdict": "Unable to Check",
                "score": 0,
                "site_status": "Unable to connect",
                "status_code": None,
                "registered_domain": get_registered_domain(
                    get_hostname(
                        url
                    )
                ),
                "reasons": [
                    str(error)
                ],
                "rdap": {},
                "tls": {},
                "page": {},
                "phish_tank": {},
                "openphish": {},
                "google_webrisk": {}
            }

        results.append(
            result
        )

        progress.progress(
            index / len(urls)
        )

    progress.empty()
    status.empty()

    order = {
        "High Risk": 0,
        "Suspicious": 1,
        "Caution": 2,
        "Unable to Check": 3,
        "Low Risk": 4
    }

    results = sorted(
        results,
        key=lambda item: (
            order.get(
                item["verdict"],
                9
            ),
            -item.get(
                "score",
                0
            )
        )
    )

    high = sum(
        item["verdict"] == "High Risk"
        for item in results
    )

    suspicious = sum(
        item["verdict"] == "Suspicious"
        for item in results
    )

    caution = sum(
        item["verdict"] == "Caution"
        for item in results
    )

    low = sum(
        item["verdict"] == "Low Risk"
        for item in results
    )

    st.subheader(
        "Results"
    )

    if len(results) > 1:
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "High Risk",
                high
            )

        with c2:
            st.metric(
                "Suspicious",
                suspicious
            )

        with c3:
            st.metric(
                "Caution",
                caution
            )

        with c4:
            st.metric(
                "Low Risk",
                low
            )

    for result in results:
        domain = (
            result.get(
                "registered_domain"
            )
            or result["url"]
        )

        age = result.get(
            "rdap",
            {}
        ).get(
            "age_days"
        )

        tls = result.get(
            "tls",
            {}
        )

        expiry = tls.get(
            "expires",
            "Unknown"
        )

        days_left = certificate_days_left(
            expiry
        )

        preview = result.get(
            "page",
            {}
        )

        screenshot = preview.get(
            "screenshot"
        )

        st.markdown(
            f"""
            <div class="result-card">
                <div class="result-title">{domain}</div>
                <div class="muted">
                    {result.get("site_status", "Unknown")}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Clear, normal browser-sized screenshot.
        if (
            screenshot
            and os.path.exists(
                screenshot
            )
        ):
            st.image(
                screenshot,
                caption="Website preview",
                use_container_width=True
            )

        elif preview.get(
            "preview_status"
        ) == "blocked":
            st.info(
                preview.get(
                    "preview_message",
                    "The website blocked the automated preview."
                )
            )

        elif preview.get(
            "preview_status"
        ) == "failed":
            st.info(
                "The website preview could not be loaded."
            )

        c1, c2, c3, c4 = st.columns(
            4
        )

        with c1:
            st.metric(
                "Risk",
                result["verdict"]
            )

        with c2:
            st.metric(
                "Domain age",
                (
                    f"{age} days"
                    if age is not None
                    else "Unknown"
                )
            )

        with c3:
            st.metric(
                "HTTPS",
                (
                    "Valid"
                    if tls.get(
                        "valid"
                    )
                    else "Not validated"
                )
            )

        with c4:
            if days_left is None:
                cert_text = "Unknown"
            elif days_left < 0:
                cert_text = "Expired"
            else:
                cert_text = (
                    f"{days_left} days"
                )

            st.metric(
                "Certificate",
                cert_text
            )

        google = result.get(
            "google_webrisk",
            {}
        )

        phishtank = result.get(
            "phish_tank",
            {}
        )

        openphish = result.get(
            "openphish",
            {}
        )

        # Reputation is now an important visible part of the result.
        if google.get(
            "confirmed"
        ):
            st.error(
                "Google Web Risk: Reported as phishing / social engineering"
            )
        elif google.get(
            "checked"
        ):
            st.success(
                "Google Web Risk: No current phishing match found"
            )
        elif not google.get(
            "configured"
        ):
            st.info(
                "Google Web Risk: API key not configured"
            )
        else:
            st.info(
                "Google Web Risk: Check unavailable"
            )

        if result.get(
            "reasons"
        ):
            st.write(
                result["reasons"][0]
            )
        else:
            st.write(
                "No major phishing indicators were found. "
                "This is not a guarantee that the website is genuine."
            )

        with st.expander(
            "Website details"
        ):
            st.write(
                "Original address:",
                result["url"]
            )

            st.write(
                "Final address:",
                result.get(
                    "final_url",
                    result["url"]
                )
            )

            st.write(
                "HTTP status:",
                result.get(
                    "status_code",
                    "Unknown"
                )
            )

            st.write(
                "Registrar:",
                result.get(
                    "rdap",
                    {}
                ).get(
                    "registrar",
                    "Unknown"
                )
            )

            st.write(
                "Certificate issuer:",
                tls.get(
                    "issuer",
                    "Unknown"
                )
            )

            st.write(
                "Google Web Risk:",
                (
                    "Reported unsafe"
                    if google.get(
                        "confirmed"
                    )
                    else (
                        "No match found"
                        if google.get(
                            "checked"
                        )
                        else (
                            "API key not configured"
                            if not google.get(
                                "configured"
                            )
                            else "Check unavailable"
                        )
                    )
                )
            )

            st.write(
                "PhishTank:",
                (
                    "Verified phishing match"
                    if phishtank.get(
                        "confirmed"
                    )
                    else (
                        "No verified match"
                        if phishtank.get(
                            "checked"
                        )
                        else "Check unavailable"
                    )
                )
            )

            st.write(
                "OpenPhish:",
                (
                    "Listed in community feed"
                    if openphish.get(
                        "confirmed"
                    )
                    else (
                        "No match found"
                        if openphish.get(
                            "checked"
                        )
                        else "Check unavailable"
                    )
                )
            )

            if result.get(
                "reasons"
            ):
                st.write(
                    "Findings:"
                )

                for finding in result[
                    "reasons"
                ][:8]:
                    st.write(
                        finding
                    )

        st.divider()
