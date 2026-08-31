
import streamlit as st
import requests
import socket
import ssl
import os
import re
import json
import hashlib
from urllib.parse import urlparse, urlunparse
from datetime import datetime, timezone
from ipaddress import ip_address
from difflib import SequenceMatcher

import tldextract
from playwright.sync_api import sync_playwright

# QR reading
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
# SIMPLE SETTINGS
# ------------------------------------------------------------

# These checks use free public services.
# No API key is required.
#
# Set this to False if you do not want Yeti to send URLs
# to external reputation services.
USE_EXTERNAL_REPUTATION = True

# Keep batch checks reasonable so one pasted email cannot
# accidentally launch hundreds of browser checks.
MAX_LINKS_PER_CHECK = 10


# ------------------------------------------------------------
# PAGE STYLE
# ------------------------------------------------------------

st.markdown(
    """
    <style>

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
        border: 1px solid #d8dee6;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }

    .result-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1f2933 !important;
        margin-bottom: 0.2rem;
    }

    .muted {
        color: #5f6c7b !important;
    }

    .stApp p,
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
    div[data-testid="stMetricLabel"] p {
        color: #5f6c7b !important;
    }

    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] div {
        color: #1f2933 !important;
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

    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] div {
        color: #1f2933 !important;
    }

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
        background-color: #2f3b49 !important;
        color: #ffffff !important;
        border-color: #2f3b49 !important;
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
        Check links before you use them
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
    Finds normal http/https links and common www links
    inside pasted emails, Teams messages or plain text.
    """

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

    # If the user pasted only a bare domain such as tesco.com,
    # accept that too.
    if not urls:
        simple = text.strip()

        if (
            " " not in simple
            and "." in simple
            and "\n" not in simple
        ):
            urls.append(clean_url(simple))

    return urls


def decode_qr_codes(uploaded_file):
    """
    Decode one or more QR codes from an uploaded image.
    Uses OpenCV locally. No external service is used.
    """

    if not QR_SUPPORT:
        return []

    if uploaded_file is None:
        return []

    try:
        data = uploaded_file.getvalue()

        image_array = np.frombuffer(
            data,
            dtype=np.uint8
        )

        image = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

        if image is None:
            return []

        detector = cv2.QRCodeDetector()

        decoded = []

        # Try multiple QR codes first.
        try:
            ok, values, points, _ = (
                detector.detectAndDecodeMulti(
                    image
                )
            )

            if ok:
                for value in values:
                    if value:
                        decoded.append(
                            value.strip()
                        )
        except Exception:
            pass

        # Fallback to a single QR code.
        if not decoded:
            try:
                value, points, _ = (
                    detector.detectAndDecode(
                        image
                    )
                )

                if value:
                    decoded.append(
                        value.strip()
                    )
            except Exception:
                pass

        return decoded

    except Exception:
        return []


# ------------------------------------------------------------
# DOMAIN FUNCTIONS
# ------------------------------------------------------------

def get_hostname(url):
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def get_registered_domain(hostname):
    if not hostname:
        return ""

    extracted = tldextract.extract(
        hostname
    )

    if (
        not extracted.domain
        or not extracted.suffix
    ):
        return hostname.lower()

    return (
        f"{extracted.domain}.{extracted.suffix}"
        .lower()
    )


def get_domain_name_only(
    registered_domain
):
    extracted = tldextract.extract(
        registered_domain
    )

    return extracted.domain.lower()


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
            value = record[4][0]

            if value not in addresses:
                addresses.append(value)

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
        return (
            False,
            "Local addresses are not allowed"
        )

    addresses = resolve_ip(
        hostname
    )

    if not addresses:
        return (
            False,
            "The hostname could not be resolved"
        )

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
# REDIRECTS
# ------------------------------------------------------------

def safe_request(url):
    current_url = url
    redirect_chain = []
    response = None

    for _ in range(8):

        hostname = get_hostname(
            current_url
        )

        safe, message = (
            check_host_is_safe(
                hostname
            )
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
            domains.append(domain)

    if len(domains) <= 1:
        return 0, domains

    return (
        len(domains) - 1,
        domains
    )


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
                            result["registrar"] = (
                                field[3]
                            )

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

                    now = datetime.now(
                        timezone.utc
                    )

                    result["age_days"] = (
                        now - created
                    ).days

                    break

    except Exception:
        pass

    return result


# ------------------------------------------------------------
# HTTPS CERTIFICATE
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

                        if (
                            key
                            == "organizationName"
                        ):
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
# BRAND AND LOOKALIKE CHECKS
# ------------------------------------------------------------

def is_official_brand_domain(
    brand,
    registered_domain
):
    official_domains = KNOWN_BRANDS.get(
        brand,
        []
    )

    return (
        registered_domain.lower()
        in official_domains
    )


def simple_edit_distance(
    first,
    second
):
    rows = len(first) + 1
    columns = len(second) + 1

    table = []

    for row in range(rows):
        table.append(
            [0] * columns
        )

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

            cost = 0

            if (
                first[row - 1]
                != second[column - 1]
            ):
                cost = 1

            table[row][column] = min(
                table[row - 1][column] + 1,
                table[row][column - 1] + 1,
                table[row - 1][column - 1]
                + cost
            )

    return table[-1][-1]


def normalise_lookalike_text(value):
    value = value.lower()

    replacements = {
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t"
    }

    for old, new in (
        replacements.items()
    ):
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

    normalised = (
        normalise_lookalike_text(
            domain_name
        )
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

            if distance == 1:
                return brand

            if similarity >= 0.88:
                return brand

    return None


def detect_claimed_brand(
    hostname,
    page
):
    """
    Only use strong page identity signals.
    Normal social links are ignored.
    """

    hostname_lower = (
        hostname.lower()
    )

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

        combined = (
            title
            + " "
            + heading
        )

        for phrase in phrases:
            if phrase in combined:
                return brand

        if password_field:
            if (
                brand in title
                or brand in heading
            ):
                return brand

    return None


# ------------------------------------------------------------
# URL STRUCTURE
# ------------------------------------------------------------

def get_url_structure_findings(url):
    findings = []

    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if parsed.username or parsed.password:
        findings.append((
            20,
            "The URL contains username or password information before the hostname."
        ))

    if (
        hostname.startswith("xn--")
        or ".xn--" in hostname
    ):
        findings.append((
            22,
            "The domain uses punycode, which can be used for lookalike domain names."
        ))

    try:
        ip_address(hostname)

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
            part
            for part
            in extracted.subdomain.split(".")
            if part
        ]

        if len(parts) >= 4:
            findings.append((
                7,
                "The address uses an unusually deep subdomain structure."
            ))

    try:
        port = parsed.port

        if (
            port
            and port not in (
                80,
                443
            )
        ):
            findings.append((
                5,
                f"The website uses the non-standard port {port}."
            ))

    except ValueError:
        pass

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
# OPTIONAL FREE REPUTATION CHECK
# ------------------------------------------------------------

def check_phishtank(url):
    """
    PhishTank allows URL checks without requiring a paid account.
    If the service is unavailable, Yeti simply continues.
    """

    result = {
        "checked": False,
        "confirmed": False
    }

    if not USE_EXTERNAL_REPUTATION:
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
# BROWSER PREVIEW
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
        "preview_message": "",
        "browser_final_url": browser_url
    }

    # Give each URL its own screenshot file.
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
                timezone_id="Europe/London",
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

            result[
                "browser_final_url"
            ] = page.url

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
                email_selector = (
                    'input[type="email"], '
                    'input[name*="email" i], '
                    'input[name*="user" i]'
                )

                result[
                    "email_field"
                ] = (
                    page.locator(
                        email_selector
                    ).count() > 0
                )
            except Exception:
                pass

            try:
                forms = page.locator(
                    "form"
                )

                count = min(
                    forms.count(),
                    20
                )

                for i in range(count):

                    form = forms.nth(i)

                    action = (
                        form.get_attribute(
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
# KNOWN EXTERNAL AUTH SERVICES
# ------------------------------------------------------------

def is_known_auth_service(domain):
    known_services = {
        "microsoftonline.com",
        "live.com",
        "google.com",
        "okta.com",
        "auth0.com",
        "stripe.com",
        "paypal.com"
    }

    return (
        domain.lower()
        in known_services
    )


# ------------------------------------------------------------
# MAIN ANALYSIS
# ------------------------------------------------------------

def analyse_url(url):
    result = {
        "url": url,
        "score": 0,
        "reasons": [],
        "final_url": url,
        "redirects": [],
        "hostname": "",
        "registered_domain": "",
        "ip_addresses": [],
        "rdap": {},
        "tls": {},
        "page": {},
        "brand": None,
        "lookalike_brand": None,
        "redirect_domains": [],
        "reputation": {
            "checked": False,
            "confirmed": False
        }
    }

    # 1. Redirects and final destination
    response, final_url, redirects = (
        safe_request(url)
    )

    result["final_url"] = final_url
    result["redirects"] = redirects

    hostname = get_hostname(
        final_url
    )

    registered_domain = (
        get_registered_domain(
            hostname
        )
    )

    result["hostname"] = hostname
    result[
        "registered_domain"
    ] = registered_domain

    result[
        "ip_addresses"
    ] = resolve_ip(
        hostname
    )


    # 2. Free reputation check
    result["reputation"] = (
        check_phishtank(
            final_url
        )
    )

    if result[
        "reputation"
    ].get("confirmed"):

        result["score"] += 75

        result["reasons"].append(
            "This address appears in a verified phishing database."
        )


    # 3. Domain age
    result["rdap"] = (
        get_rdap_information(
            registered_domain
        )
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


    # 4. HTTPS certificate
    if final_url.startswith(
        "https://"
    ):

        result["tls"] = (
            get_tls_information(
                hostname
            )
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


    # 5. URL structure
    for points, reason in (
        get_url_structure_findings(
            final_url
        )
    ):

        result["score"] += points
        result["reasons"].append(
            reason
        )


    # 6. Redirect domain changes
    changes, domains = (
        count_registered_domain_changes(
            url,
            redirects,
            final_url
        )
    )

    result[
        "redirect_domains"
    ] = domains

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


    # 7. Lookalike domain
    lookalike = (
        detect_lookalike_domain(
            registered_domain
        )
    )

    result[
        "lookalike_brand"
    ] = lookalike

    if lookalike:

        result["score"] += 32

        result["reasons"].append(
            f"The domain name looks similar to {lookalike.title()}, "
            "but it is not one of that brand's known official domains."
        )


    # 8. Browser page checks
    result["page"] = inspect_page(
        url
    )

    preview_ok = (
        result["page"].get(
            "preview_status"
        )
        == "success"
    )


    # 9. Brand identity
    brand = None

    if preview_ok:

        brand = detect_claimed_brand(
            hostname,
            result["page"]
        )

    result["brand"] = brand

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


    # 10. Forms
    if preview_ok:

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

        for action in (
            result["page"].get(
                "forms",
                []
            )
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


    # 11. Final result
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
# SIMPLE SUMMARY HELPERS
# ------------------------------------------------------------

def main_reason(result):
    if result["reasons"]:
        return result["reasons"][0]

    return (
        "No major phishing indicators were found."
    )


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
            f"Final URL: {result['final_url']}"
        )

        lines.append(
            f"Result: {result['verdict']}"
        )

        lines.append(
            f"Risk score: {result['score']}/100"
        )

        lines.append(
            "Findings:"
        )

        if result["reasons"]:

            for reason in (
                result["reasons"]
            ):
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

    return "\n".join(lines)


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
            "Yeti will read the hidden link."
        )
    )

    submitted = st.form_submit_button(
        "Check"
    )


# ------------------------------------------------------------
# RUN
# ------------------------------------------------------------

if submitted:

    urls = extract_urls_from_text(
        pasted_text
    )

    qr_values = decode_qr_codes(
        qr_file
    )

    for value in qr_values:

        qr_urls = extract_urls_from_text(
            value
        )

        # Some QR codes contain only the URL with no extra text.
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
            qr_file is not None
            and not QR_SUPPORT
        ):
            st.error(
                "QR reading is not available. "
                "Add opencv-python-headless and numpy to requirements.txt."
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
            f"Checking {index} of {len(urls)}: {url}"
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
                "registered_domain": (
                    get_registered_domain(
                        get_hostname(url)
                    )
                ),
                "reasons": [
                    str(error)
                ],
                "redirects": [],
                "redirect_domains": [],
                "ip_addresses": [],
                "rdap": {},
                "tls": {},
                "page": {},
                "reputation": {
                    "checked": False,
                    "confirmed": False
                }
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
    # OVERALL SUMMARY
    # --------------------------------------------------------

    high_count = sum(
        1
        for item in results
        if item["verdict"]
        == "High Risk"
    )

    suspicious_count = sum(
        1
        for item in results
        if item["verdict"]
        == "Suspicious"
    )

    caution_count = sum(
        1
        for item in results
        if item["verdict"]
        == "Caution"
    )

    low_count = sum(
        1
        for item in results
        if item["verdict"]
        == "Low Risk"
    )

    st.markdown(
        f"""
        <div class="result-box">
            <div class="result-title">Check complete</div>
            <div class="muted">
                {len(results)} link(s) checked
            </div>
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
    # RESULT LIST
    # --------------------------------------------------------

    st.subheader(
        "Results"
    )

    # Put the most important results first.
    order = {
        "High Risk": 0,
        "Suspicious": 1,
        "Caution": 2,
        "Unable to Check": 3,
        "Low Risk": 4
    }

    sorted_results = sorted(
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

    for result in sorted_results:

        domain = (
            result.get(
                "registered_domain"
            )
            or result["url"]
        )

        st.markdown(
            f"""
            <div class="result-box">
                <div class="result-title">
                    {domain}
                </div>
                <div class="muted">
                    {result["verdict"]} &nbsp; | &nbsp;
                    Risk score: {result.get("score", 0)}/100
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
                "HTTPS certificate:",
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

            reputation = result.get(
                "reputation",
                {}
            )

            if reputation.get(
                "checked"
            ):
                st.write(
                    "Phishing database:",
                    (
                        "Verified match"
                        if reputation.get(
                            "confirmed"
                        )
                        else "No verified match found"
                    )
                )
            else:
                st.write(
                    "Phishing database:",
                    "Check unavailable"
                )

            st.write(
                "Findings:"
            )

            if result.get(
                "reasons"
            ):

                for reason in result[
                    "reasons"
                ]:
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
            ) == "blocked":

                st.info(
                    preview.get(
                        "preview_message"
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
    # REPORT
    # --------------------------------------------------------

    report = create_text_report(
        sorted_results
    )

    st.download_button(
        "Download report",
        data=report,
        file_name="yeti_check_report.txt",
        mime="text/plain"
    )


    # --------------------------------------------------------
    # RESET
    # --------------------------------------------------------

    if st.button(
        "Reset",
        key="reset_button"
    ):
        st.session_state[
            "yeti_text"
        ] = ""

        st.rerun()
