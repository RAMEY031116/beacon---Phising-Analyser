import streamlit as st
import requests
import socket
import ssl
import os
import re
import hashlib
from urllib.parse import urlparse
from datetime import datetime, timezone
from ipaddress import ip_address
from difflib import SequenceMatcher

import tldextract
from playwright.sync_api import sync_playwright

# QR support
try:
    import cv2
    import numpy as np
    QR_SUPPORT = True
except Exception:
    QR_SUPPORT = False


# ------------------------------------------------------------
# PAGE SETUP
# ------------------------------------------------------------

st.set_page_config(
    page_title="Yeti Check",
    layout="wide"
)


# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------

MAX_LINKS_PER_CHECK = 10

# These use free public phishing sources and need no paid setup.
USE_PHISHTANK = True
USE_OPENPHISH = True

OPENPHISH_FEED = "https://openphish.com/feed.txt"


# ------------------------------------------------------------
# THEME SAFE STYLE
# ------------------------------------------------------------

st.markdown(
    """
    <style>

    html, body, [class*="css"] {
        color: #1f2933 !important;
    }

    .stApp {
        background-color: #f5f7fa !important;
        color: #1f2933 !important;
    }

    .block-container {
        max-width: 1100px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .main-title {
        text-align: center;
        font-size: 2.8rem;
        font-weight: 700;
        color: #1f2933 !important;
        margin-bottom: 0.15rem;
    }

    .sub-title {
        text-align: center;
        color: #5f6c7b !important;
        margin-bottom: 2rem;
    }

    .result-box {
        background-color: #ffffff !important;
        color: #1f2933 !important;
        border: 1px solid #d8dee6 !important;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }

    .result-box * {
        color: #1f2933 !important;
    }

    .result-title {
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }

    .muted {
        color: #5f6c7b !important;
    }

    .stApp p,
    .stApp span,
    .stApp label,
    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp h4,
    .stApp h5,
    .stApp h6 {
        color: #1f2933 !important;
    }

    .stTextArea textarea,
    .stTextInput input {
        background-color: #ffffff !important;
        color: #1f2933 !important;
        caret-color: #1f2933 !important;
        border: 1px solid #c8d0da !important;
        border-radius: 8px !important;
    }

    .stTextArea textarea::placeholder,
    .stTextInput input::placeholder {
        color: #8a96a3 !important;
        opacity: 1 !important;
    }

    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        color: #1f2933 !important;
        border: 1px solid #d8dee6 !important;
        border-radius: 8px !important;
        padding: 0.7rem !important;
    }

    div[data-testid="stMetric"] * {
        color: #1f2933 !important;
    }

    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] * {
        color: #5f6c7b !important;
    }

    div[data-testid="stExpander"] {
        background-color: #ffffff !important;
        color: #1f2933 !important;
        border: 1px solid #d8dee6 !important;
        border-radius: 8px !important;
    }

    div[data-testid="stExpander"] * {
        color: #1f2933 !important;
    }

    div[data-testid="stAlert"] *,
    div[data-testid="stNotification"] * {
        color: #1f2933 !important;
    }

    /* Normal buttons */
    .stButton > button,
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #1f2933 !important;
        color: #ffffff !important;
        border: 1px solid #1f2933 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    .stButton > button *,
    div[data-testid="stFormSubmitButton"] > button * {
        color: #ffffff !important;
    }

    .stButton > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        background-color: #344150 !important;
        color: #ffffff !important;
        border-color: #344150 !important;
    }

    /* Download button */
    div[data-testid="stDownloadButton"] button {
        background-color: #1f2933 !important;
        color: #ffffff !important;
        border: 1px solid #1f2933 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    div[data-testid="stDownloadButton"] button * {
        color: #ffffff !important;
    }

    /* File uploader / Browse files */
    section[data-testid="stFileUploaderDropzone"] {
        background-color: #ffffff !important;
        color: #1f2933 !important;
        border-color: #c8d0da !important;
    }

    section[data-testid="stFileUploaderDropzone"] * {
        color: #1f2933 !important;
    }

    section[data-testid="stFileUploaderDropzone"] button {
        background-color: #1f2933 !important;
        color: #ffffff !important;
        border: 1px solid #1f2933 !important;
    }

    section[data-testid="stFileUploaderDropzone"] button * {
        color: #ffffff !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# HEADER
# ------------------------------------------------------------

st.markdown(
    """
    <div class="main-title">Yeti Check</div>
    <div class="sub-title">
        Check websites, messages and QR codes before you use them
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# KNOWN BRANDS
# ------------------------------------------------------------

KNOWN_BRANDS = {
    "microsoft": [
        "microsoft.com",
        "live.com",
        "microsoftonline.com",
        "office.com",
        "outlook.com"
    ],
    "google": [
        "google.com",
        "gmail.com",
        "youtube.com"
    ],
    "apple": [
        "apple.com",
        "icloud.com"
    ],
    "paypal": [
        "paypal.com"
    ],
    "amazon": [
        "amazon.com",
        "amazon.co.uk"
    ],
    "github": [
        "github.com"
    ],
    "linkedin": [
        "linkedin.com"
    ],
    "dropbox": [
        "dropbox.com"
    ],
    "facebook": [
        "facebook.com"
    ],
    "instagram": [
        "instagram.com"
    ],
    "netflix": [
        "netflix.com"
    ],
    "docusign": [
        "docusign.com",
        "docusign.net"
    ]
}

SHORTENERS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "cutt.ly",
    "rb.gy",
    "is.gd",
    "buff.ly",
    "ow.ly",
    "rebrand.ly",
    "shorturl.at"
}


# ------------------------------------------------------------
# INPUT EXTRACTION
# ------------------------------------------------------------

def clean_url(value):
    value = value.strip().strip(".,);]>}\"'")

    if not value.startswith(("http://", "https://")):
        value = "https://" + value

    return value


def extract_urls_from_text(text):
    if not text:
        return []

    pattern = re.compile(
        r'(?:(?:https?://)|(?:www\.))[^\s<>"\']+',
        re.IGNORECASE
    )

    found = pattern.findall(text)

    urls = []

    for item in found:
        item = clean_url(item)

        if item not in urls:
            urls.append(item)

    # Accept a bare domain when it is the only pasted value.
    if not urls:
        simple = text.strip()

        if (
            " " not in simple
            and "\n" not in simple
            and "." in simple
        ):
            urls.append(
                clean_url(simple)
            )

    return urls


def decode_qr_codes(uploaded_file):
    if not QR_SUPPORT or uploaded_file is None:
        return []

    try:
        raw = uploaded_file.getvalue()

        image_array = np.frombuffer(
            raw,
            dtype=np.uint8
        )

        image = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

        if image is None:
            return []

        detector = cv2.QRCodeDetector()

        values = []

        try:
            ok, decoded, points, _ = (
                detector.detectAndDecodeMulti(
                    image
                )
            )

            if ok:
                for item in decoded:
                    if item:
                        values.append(
                            item.strip()
                        )
        except Exception:
            pass

        if not values:
            try:
                value, points, _ = (
                    detector.detectAndDecode(
                        image
                    )
                )

                if value:
                    values.append(
                        value.strip()
                    )
            except Exception:
                pass

        return values

    except Exception:
        return []


# ------------------------------------------------------------
# DOMAIN HELPERS
# ------------------------------------------------------------

def get_hostname(url):
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def get_registered_domain(hostname):
    if not hostname:
        return ""

    result = tldextract.extract(
        hostname
    )

    if (
        not result.domain
        or not result.suffix
    ):
        return hostname.lower()

    return (
        f"{result.domain}.{result.suffix}"
        .lower()
    )


def get_domain_name_only(
    registered_domain
):
    result = tldextract.extract(
        registered_domain
    )

    return result.domain.lower()


# ------------------------------------------------------------
# NETWORK SAFETY
# ------------------------------------------------------------

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

        addresses = []

        for record in records:
            address = record[4][0]

            if address not in addresses:
                addresses.append(
                    address
                )

        return addresses

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
        if is_private_or_local_ip(
            address
        ):
            return (
                False,
                "Private or local network addresses are not allowed"
            )

    return True, ""


# ------------------------------------------------------------
# HTTP / REDIRECT CHECK
# ------------------------------------------------------------

def safe_request(url):
    current_url = url
    redirect_chain = []
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
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )
            }
        )

        if response.status_code in (
            301,
            302,
            303,
            307,
            308
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

            redirect_chain.append(
                next_url
            )

            current_url = next_url
            continue

        return (
            response,
            current_url,
            redirect_chain
        )

    return (
        response,
        current_url,
        redirect_chain
    )


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
    urls = (
        [original_url]
        + list(redirects)
        + [final_url]
    )

    domains = []

    for item in urls:

        domain = get_registered_domain(
            get_hostname(item)
        )

        if domain and (
            not domains
            or domain != domains[-1]
        ):
            domains.append(
                domain
            )

    return max(
        0,
        len(domains) - 1
    ), domains


# ------------------------------------------------------------
# RDAP
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

        for entity in data.get(
            "entities",
            []
        ):

            if "registrar" in entity.get(
                "roles",
                []
            ):

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
                            result[
                                "registrar"
                            ] = field[3]

                            break

        for event in data.get(
            "events",
            []
        ):

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

                    result["created"] = (
                        created
                    )

                    result["age_days"] = (
                        datetime.now(
                            timezone.utc
                        )
                        - created
                    ).days

                    break

    except Exception:
        pass

    return result


# ------------------------------------------------------------
# TLS CERTIFICATE
# ------------------------------------------------------------

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

                certificate = (
                    secure_socket.getpeercert()
                )

                result["valid"] = True

                issuer_names = []

                for group in certificate.get(
                    "issuer",
                    []
                ):

                    for key, value in group:

                        if key == "organizationName":
                            issuer_names.append(
                                value
                            )

                if issuer_names:
                    result["issuer"] = (
                        ", ".join(
                            issuer_names
                        )
                    )

                result["expires"] = (
                    certificate.get(
                        "notAfter",
                        "Unknown"
                    )
                )

    except Exception:
        pass

    return result


# ------------------------------------------------------------
# REPUTATION SOURCES
# ------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
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

    if not USE_OPENPHISH:
        return result

    try:
        feed = get_openphish_feed()

        if not feed:
            return result

        result["checked"] = True

        # Check exact URL first.
        if url in feed:
            result["confirmed"] = True
            return result

        # Also compare URLs without a trailing slash.
        clean = url.rstrip("/")

        for item in feed:
            if item.rstrip("/") == clean:
                result["confirmed"] = True
                break

    except Exception:
        pass

    return result


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
                "format": "json"
            },
            timeout=10,
            headers={
                "User-Agent": "YetiCheck/1.0"
            }
        )

        if response.status_code != 200:
            return result

        data = response.json()

        details = data.get(
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
            "true",
            "yes",
            "1"
        )

        verified = str(
            details.get(
                "verified",
                False
            )
        ).lower() in (
            "true",
            "yes",
            "1"
        )

        valid = str(
            details.get(
                "valid",
                False
            )
        ).lower() in (
            "true",
            "yes",
            "1"
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
# LOOKALIKE / BRAND CHECKS
# ------------------------------------------------------------

def is_official_brand_domain(
    brand,
    registered_domain
):
    return (
        registered_domain.lower()
        in KNOWN_BRANDS.get(
            brand,
            []
        )
    )


def simple_edit_distance(
    first,
    second
):
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

    for row in range(
        1,
        rows
    ):

        for column in range(
            1,
            columns
        ):

            cost = (
                0
                if first[row - 1]
                == second[column - 1]
                else 1
            )

            table[row][column] = min(
                table[row - 1][column] + 1,
                table[row][column - 1] + 1,
                table[row - 1][column - 1]
                + cost
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

        normal_brand = (
            normalise_lookalike_text(
                brand
            )
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
    hostname_lower = (
        hostname.lower()
    )

    title = (
        page.get(
            "title",
            ""
        )
        or ""
    ).lower()

    site_name = (
        page.get(
            "site_name",
            ""
        )
        or ""
    ).lower()

    heading = (
        page.get(
            "heading",
            ""
        )
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

        combined = (
            title
            + " "
            + heading
        )

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

    hostname = (
        parsed.hostname
        or ""
    )

    registered_domain = (
        get_registered_domain(
            hostname
        )
    )

    if registered_domain in SHORTENERS:
        findings.append((
            5,
            "The address uses a URL shortening service."
        ))

    if (
        parsed.username
        or parsed.password
    ):
        findings.append((
            20,
            "The URL contains information before the hostname that may hide the real destination."
        ))

    if (
        hostname.startswith(
            "xn--"
        )
        or ".xn--" in hostname
    ):
        findings.append((
            22,
            "The domain uses punycode, which can be used for lookalike domain names."
        ))

    try:
        ip_address(
            hostname
        )

        findings.append((
            20,
            "The website uses an IP address instead of a normal domain name."
        ))

    except ValueError:
        pass

    extracted = tldextract.extract(
        hostname
    )

    if extracted.subdomain:

        parts = [
            item
            for item
            in extracted.subdomain.split(".")
            if item
        ]

        if len(parts) >= 4:
            findings.append((
                7,
                "The address uses an unusually deep subdomain structure."
            ))

    if url.count("%") >= 5:
        findings.append((
            5,
            "The URL contains a large amount of encoded text."
        ))

    if len(url) > 220:
        findings.append((
            4,
            "The URL is unusually long."
        ))

    return findings


# ------------------------------------------------------------
# BROWSER CHECK
# ------------------------------------------------------------

def get_browser_path():
    paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium"
    ]

    for path in paths:
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

    screenshot_path = (
        f"yeti_{file_id}.png"
    )

    try:
        with sync_playwright() as p:

            chromium_path = (
                get_browser_path()
            )

            launch_options = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage"
                ]
            }

            if chromium_path:
                launch_options[
                    "executable_path"
                ] = chromium_path

            browser = p.chromium.launch(
                **launch_options
            )

            context = browser.new_context(
                viewport={
                    "width": 1366,
                    "height": 768
                },
                user_agent=(
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="en-GB",
                extra_http_headers={
                    "Accept-Language": (
                        "en-GB,en;q=0.9"
                    )
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
                    2000
                )
            except Exception:
                pass

            try:
                result["title"] = (
                    page.title()
                )
            except Exception:
                pass

            body_text = ""

            try:
                body_text = (
                    page.locator(
                        "body"
                    ).inner_text(
                        timeout=3000
                    )
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

                result[
                    "preview_status"
                ] = "blocked"

                result[
                    "preview_message"
                ] = (
                    "The website blocked the automated preview. "
                    "This is common on some legitimate websites and "
                    "is not counted as evidence of phishing."
                )

                context.close()
                browser.close()

                return result

            result[
                "preview_status"
            ] = "success"

            try:
                meta = page.locator(
                    'meta[property="og:site_name"]'
                )

                if meta.count() > 0:
                    result[
                        "site_name"
                    ] = (
                        meta.first
                        .get_attribute(
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
                    result[
                        "heading"
                    ] = (
                        heading.first
                        .inner_text(
                            timeout=2000
                        )
                        or ""
                    )
            except Exception:
                pass

            try:
                result[
                    "password_field"
                ] = (
                    page.locator(
                        'input[type="password"]'
                    ).count() > 0
                )
            except Exception:
                pass

            try:
                result[
                    "email_field"
                ] = (
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
                        action = (
                            requests.compat.urljoin(
                                page.url,
                                action
                            )
                        )

                    result["forms"].append(
                        action
                    )

            except Exception:
                pass

            try:
                page.screenshot(
                    path=screenshot_path,
                    full_page=True
                )

                result[
                    "screenshot"
                ] = screenshot_path

            except Exception:
                pass

            context.close()
            browser.close()

    except Exception:

        result[
            "preview_status"
        ] = "failed"

        result[
            "preview_message"
        ] = (
            "The website preview could not be loaded. "
            "The other checks can still be used."
        )

    return result


# ------------------------------------------------------------
# FORM DESTINATION HELPERS
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
# ANALYSIS
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
        "openphish": {}
    }

    # --------------------------------------------------------
    # 1. Request and final destination
    # --------------------------------------------------------

    response, final_url, redirects = (
        safe_request(
            url
        )
    )

    result["final_url"] = (
        final_url
    )

    result["redirects"] = (
        redirects
    )

    if response is not None:

        result["status_code"] = (
            response.status_code
        )

        result["site_status"] = (
            classify_http_status(
                response.status_code
            )
        )

        result["content_type"] = (
            response.headers.get(
                "Content-Type",
                "Unknown"
            )
        )

        result["server"] = (
            response.headers.get(
                "Server",
                "Unknown"
            )
        )

    hostname = get_hostname(
        final_url
    )

    registered_domain = (
        get_registered_domain(
            hostname
        )
    )

    result["hostname"] = (
        hostname
    )

    result[
        "registered_domain"
    ] = registered_domain

    result[
        "ip_addresses"
    ] = resolve_ip(
        hostname
    )


    # --------------------------------------------------------
    # 2. Reputation databases
    # --------------------------------------------------------

    result["phish_tank"] = (
        check_phishtank(
            final_url
        )
    )

    result["openphish"] = (
        check_openphish(
            final_url
        )
    )

    if result[
        "phish_tank"
    ].get("confirmed"):

        result["score"] += 75

        result["reasons"].append(
            "The address appears in the PhishTank verified phishing database."
        )

    if result[
        "openphish"
    ].get("confirmed"):

        result["score"] += 75

        result["reasons"].append(
            "The address appears in the OpenPhish community phishing feed."
        )


    # --------------------------------------------------------
    # 3. Domain registration
    # --------------------------------------------------------

    result["rdap"] = (
        get_rdap_information(
            registered_domain
        )
    )

    age = result[
        "rdap"
    ].get(
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


    # --------------------------------------------------------
    # 4. HTTPS
    # --------------------------------------------------------

    if final_url.startswith(
        "https://"
    ):

        result["tls"] = (
            get_tls_information(
                hostname
            )
        )

        if not result[
            "tls"
        ].get(
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


    # --------------------------------------------------------
    # 5. URL structure
    # --------------------------------------------------------

    for points, reason in (
        get_url_structure_findings(
            final_url
        )
    ):

        result["score"] += (
            points
        )

        result["reasons"].append(
            reason
        )


    # --------------------------------------------------------
    # 6. Redirect changes
    # --------------------------------------------------------

    changes, domains = (
        count_registered_domain_changes(
            url,
            redirects,
            final_url
        )
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


    # --------------------------------------------------------
    # 7. Lookalike domain
    # --------------------------------------------------------

    lookalike = (
        detect_lookalike_domain(
            registered_domain
        )
    )

    if lookalike:

        result["score"] += 32

        result["reasons"].append(
            f"The domain name looks similar to {lookalike.title()}, "
            "but it is not one of that brand's known official domains."
        )


    # --------------------------------------------------------
    # 8. Page and form checks
    # --------------------------------------------------------

    result["page"] = (
        inspect_page(
            url
        )
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

        password_field = (
            result["page"].get(
                "password_field",
                False
            )
        )

        if password_field:

            result["score"] += 3

            result["reasons"].append(
                "The page contains a password field."
            )

        for action in result[
            "page"
        ].get(
            "forms",
            []
        ):

            if not action:
                continue

            form_domain = (
                get_registered_domain(
                    get_hostname(
                        action
                    )
                )
            )

            if (
                form_domain
                and registered_domain
                and form_domain
                != registered_domain
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


    # --------------------------------------------------------
    # 9. Availability result
    # --------------------------------------------------------

    # A dead site is not the same as phishing.
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


    # --------------------------------------------------------
    # 10. Verdict
    # --------------------------------------------------------

    result["score"] = min(
        result["score"],
        100
    )

    if result["score"] >= 70:
        result["verdict"] = (
            "High Risk"
        )

    elif result["score"] >= 40:
        result["verdict"] = (
            "Suspicious"
        )

    elif result["score"] >= 20:
        result["verdict"] = (
            "Caution"
        )

    else:
        result["verdict"] = (
            "Low Risk"
        )

    return result


# ------------------------------------------------------------
# REPORT HELPERS
# ------------------------------------------------------------

def main_reason(result):
    if result.get("reasons"):
        return result["reasons"][0]

    return "No major phishing indicators were found."


def create_text_report(results):
    lines = [
        "YETI CHECK REPORT",
        ""
    ]

    for result in results:

        lines.append(
            f"URL: {result['url']}"
        )

        lines.append(
            f"Final URL: {result.get('final_url', result['url'])}"
        )

        lines.append(
            f"Result: {result['verdict']}"
        )

        lines.append(
            f"Risk score: {result.get('score', 0)}/100"
        )

        lines.append(
            f"Website status: {result.get('site_status', 'Unknown')}"
        )

        lines.append(
            f"HTTP status: {result.get('status_code', 'Unknown')}"
        )

        lines.append(
            f"Domain: {result.get('registered_domain', 'Unknown')}"
        )

        lines.append(
            "Findings:"
        )

        if result.get(
            "reasons"
        ):

            for reason in result[
                "reasons"
            ]:

                lines.append(
                    f"- {reason}"
                )

        else:

            lines.append(
                "- No major phishing indicators were found."
            )

        lines.append("")
        lines.append("-" * 50)
        lines.append("")

    return "\n".join(
        lines
    )


# ------------------------------------------------------------
# INPUT
# ------------------------------------------------------------

with st.form(
    "yeti_check_form",
    clear_on_submit=False
):

    pasted_text = st.text_area(
        "Link or message",
        placeholder=(
            "Paste a website, several websites, "
            "or a suspicious email or message here"
        ),
        height=140,
        key="yeti_text"
    )

    qr_file = st.file_uploader(
        "QR code image",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp"
        ],
        help=(
            "Optional. Upload a QR code image and "
            "Yeti will check the hidden link."
        )
    )

    submitted = (
        st.form_submit_button(
            "Check"
        )
    )


# ------------------------------------------------------------
# RUN
# ------------------------------------------------------------

if submitted:

    urls = extract_urls_from_text(
        pasted_text
    )

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
                clean_url(
                    value
                )
            ]

        for item in qr_urls:

            if item not in urls:
                urls.append(
                    item
                )


    if not urls:

        if (
            qr_file is not None
            and not QR_SUPPORT
        ):

            st.error(
                "QR reading is not available. "
                "Check the requirements.txt file."
            )

        elif qr_file is not None:

            st.warning(
                "No website link could be read from the QR code."
            )

        else:

            st.warning(
                "No website links were found."
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


    results = []

    progress = st.progress(
        0
    )

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
                "registered_domain": (
                    get_registered_domain(
                        get_hostname(
                            url
                        )
                    )
                ),
                "reasons": [
                    str(error)
                ],
                "rdap": {},
                "tls": {},
                "page": {},
                "phish_tank": {},
                "openphish": {}
            }

        results.append(
            result
        )

        progress.progress(
            index / len(urls)
        )

    progress.empty()
    status.empty()


    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    high_count = sum(
        item["verdict"]
        == "High Risk"
        for item in results
    )

    suspicious_count = sum(
        item["verdict"]
        == "Suspicious"
        for item in results
    )

    caution_count = sum(
        item["verdict"]
        == "Caution"
        for item in results
    )

    low_count = sum(
        item["verdict"]
        == "Low Risk"
        for item in results
    )

    st.markdown(
        f"""
        <div class="result-box">
            <div class="result-title">Check complete</div>
            <div class="muted">{len(results)} link(s) checked</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:
        st.metric(
            "High Risk",
            high_count
        )

    with col2:
        st.metric(
            "Suspicious",
            suspicious_count
        )

    with col3:
        st.metric(
            "Caution",
            caution_count
        )

    with col4:
        st.metric(
            "Low Risk",
            low_count
        )


    # --------------------------------------------------------
    # RESULTS
    # --------------------------------------------------------

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

    st.subheader(
        "Results"
    )

    for result in results:

        domain = (
            result.get(
                "registered_domain"
            )
            or result["url"]
        )

        st.markdown(
            f"""
            <div class="result-box">
                <div class="result-title">{domain}</div>
                <div class="muted">
                    {result["verdict"]} &nbsp; | &nbsp;
                    Risk score: {result.get("score", 0)}/100
                    &nbsp; | &nbsp;
                    {result.get("site_status", "Unknown")}
                </div>
                <div style="margin-top:0.5rem;">
                    {main_reason(result)}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.expander(
            f"Details for {domain}"
        ):

            col_a, col_b, col_c = (
                st.columns(3)
            )

            with col_a:
                st.metric(
                    "Website status",
                    result.get(
                        "site_status",
                        "Unknown"
                    )
                )

            with col_b:
                st.metric(
                    "HTTP",
                    (
                        result.get(
                            "status_code"
                        )
                        if result.get(
                            "status_code"
                        ) is not None
                        else "Unknown"
                    )
                )

            with col_c:
                st.metric(
                    "HTTPS",
                    (
                        "Valid"
                        if result.get(
                            "tls",
                            {}
                        ).get(
                            "valid"
                        )
                        else "Not validated"
                    )
                )

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

            age = result.get(
                "rdap",
                {}
            ).get(
                "age_days"
            )

            st.write(
                "Domain age:",
                (
                    f"{age} days"
                    if age is not None
                    else "Unknown"
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
                "Content type:",
                result.get(
                    "content_type",
                    "Unknown"
                )
            )

            st.write(
                "Server:",
                result.get(
                    "server",
                    "Unknown"
                )
            )

            phishtank = result.get(
                "phish_tank",
                {}
            )

            openphish = result.get(
                "openphish",
                {}
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

            st.write(
                "Findings:"
            )

            if result.get(
                "reasons"
            ):

                for reason in result[
                    "reasons"
                ][:8]:

                    st.write(
                        reason
                    )

            else:

                st.write(
                    "No major phishing indicators were found."
                )

            preview = result.get(
                "page",
                {}
            )

            if preview.get(
                "preview_status"
            ) in (
                "blocked",
                "failed"
            ):

                st.info(
                    preview.get(
                        "preview_message",
                        "Preview unavailable."
                    )
                )

            screenshot = preview.get(
                "screenshot"
            )

            if (
                screenshot
                and os.path.exists(
                    screenshot
                )
            ):

                st.image(
                    screenshot,
                    use_container_width=True
                )


    # --------------------------------------------------------
    # REPORT AND RESET
    # --------------------------------------------------------

    report = create_text_report(
        results
    )

    st.download_button(
        "Download report",
        data=report,
        file_name="yeti_check_report.txt",
        mime="text/plain"
    )

    if st.button(
        "Reset",
        key="reset_button"
    ):

        st.session_state[
            "yeti_text"
        ] = ""

        st.rerun()
