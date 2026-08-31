
import streamlit as st
import requests
import socket
import ssl
import os
from urllib.parse import urlparse
from datetime import datetime, timezone
from ipaddress import ip_address
from difflib import SequenceMatcher

import tldextract
from playwright.sync_api import sync_playwright


# ------------------------------------------------------------
# PAGE SETUP
# ------------------------------------------------------------

st.set_page_config(
    page_title="Yeti Check",
    layout="wide"
)


# ------------------------------------------------------------
# OPTIONAL REPUTATION CHECK
# ------------------------------------------------------------
# PhishTank is a public phishing database.
# Set this to False if you do not want scanned URLs sent there.

USE_PHISHTANK = True
PHISHTANK_APP_KEY = os.getenv("PHISHTANK_APP_KEY", "").strip()


# ------------------------------------------------------------
# SIMPLE PAGE STYLE
# ------------------------------------------------------------

st.markdown(
    """
    <style>

    .stApp {
        background-color: #f5f7fa;
        color: #1f2933;
    }

    .block-container {
        max-width: 1050px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .main-title {
        text-align: center;
        font-size: 2.8rem;
        font-weight: 700;
        color: #1f2933;
        margin-bottom: 0.2rem;
    }

    .sub-title {
        text-align: center;
        color: #5f6c7b;
        margin-bottom: 2rem;
    }

    .result-box {
        background-color: #ffffff;
        color: #1f2933;
        border: 1px solid #d8dee6;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }

    .result-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #1f2933;
        margin-bottom: 0.3rem;
    }

    .muted {
        color: #5f6c7b;
    }

    div[data-testid="stMetric"] {
        background-color: #ffffff;
        color: #1f2933;
        border: 1px solid #d8dee6;
        border-radius: 8px;
        padding: 0.7rem;
    }

    div[data-testid="stExpander"] {
        background-color: #ffffff;
        color: #1f2933;
        border: 1px solid #d8dee6;
        border-radius: 8px;
    }

    div[data-testid="stAlert"] {
        color: #1f2933 !important;
    }

    .stTextInput input {
        background-color: #ffffff !important;
        color: #1f2933 !important;
        border: 1px solid #c8d0da !important;
        border-radius: 8px !important;
    }

    .stTextInput label {
        color: #1f2933 !important;
    }

    p, span, label, div {
        color: inherit;
    }


    .stButton > button,
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #1f2933 !important;
        color: #ffffff !important;
        border: 1px solid #1f2933 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    .stButton > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        background-color: #2f3b49 !important;
        color: #ffffff !important;
        border-color: #2f3b49 !important;
    }

    .stButton > button:focus,
    div[data-testid="stFormSubmitButton"] > button:focus {
        background-color: #1f2933 !important;
        color: #ffffff !important;
        border-color: #1f2933 !important;
        box-shadow: none !important;
    }

    .stButton > button p,
    div[data-testid="stFormSubmitButton"] > button p {
        color: #ffffff !important;
    }


    /* Keep Streamlit metric cards readable in every theme */
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

    div[data-testid="stMetricLabel"] {
        color: #5f6c7b !important;
    }

    div[data-testid="stMetricLabel"] p {
        color: #5f6c7b !important;
    }

    div[data-testid="stMetricValue"] {
        color: #1f2933 !important;
    }

    div[data-testid="stMetricValue"] div {
        color: #1f2933 !important;
    }

    div[data-testid="stMetricDelta"] {
        color: #1f2933 !important;
    }

    /* Keep normal Streamlit text readable against our light background */
    .stApp,
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

    /* Input text and placeholder */
    .stTextInput input {
        background-color: #ffffff !important;
        color: #1f2933 !important;
        caret-color: #1f2933 !important;
    }

    .stTextInput input::placeholder {
        color: #8a96a3 !important;
        opacity: 1 !important;
    }

    /* Expander content */
    div[data-testid="stExpander"] {
        background-color: #ffffff !important;
        color: #1f2933 !important;
    }

    div[data-testid="stExpander"] * {
        color: #1f2933 !important;
    }

    /* Alerts can inherit theme colours, so force readable text */
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] div {
        color: #1f2933 !important;
    }

    /* Keep button text white in every theme */
    .stButton > button,
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #1f2933 !important;
        color: #ffffff !important;
    }

    .stButton > button *,
    div[data-testid="stFormSubmitButton"] > button * {
        color: #ffffff !important;
    }

    .stButton > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        background-color: #2f3b49 !important;
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
        Check a website before you use it
    </div>
    """,
    unsafe_allow_html=True
)


# ------------------------------------------------------------
# KNOWN OFFICIAL DOMAINS
# ------------------------------------------------------------
# This is only used when there is strong evidence that a page
# is pretending to be one of these brands.
#
# A normal social link does NOT count as brand impersonation.

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
    ]
}


# ------------------------------------------------------------
# SMALL HELPER FUNCTIONS
# ------------------------------------------------------------

def clean_url(value):
    value = value.strip()

    if not value.startswith(("http://", "https://")):
        value = "https://" + value

    return value


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
        return hostname

    return f"{result.domain}.{result.suffix}"


def is_private_or_local_ip(value):
    try:
        ip = ip_address(value)

        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )

    except ValueError:
        return False


def resolve_ip(hostname):
    try:
        addresses = socket.getaddrinfo(hostname, None)

        found = []

        for item in addresses:
            address = item[4][0]

            if address not in found:
                found.append(address)

        return found

    except Exception:
        return []


def check_host_is_safe(hostname):
    if not hostname:
        return False, "Invalid hostname"

    lower = hostname.lower()

    if lower in ("localhost", "localhost.localdomain"):
        return False, "Local addresses are not allowed"

    addresses = resolve_ip(hostname)

    if not addresses:
        return False, "The hostname could not be resolved"

    for address in addresses:
        if is_private_or_local_ip(address):
            return False, "Private or local network addresses are not allowed"

    return True, ""


def safe_request(url):
    current_url = url
    redirect_chain = []

    for _ in range(6):
        hostname = get_hostname(current_url)

        safe, message = check_host_is_safe(hostname)

        if not safe:
            raise Exception(message)

        response = requests.get(
            current_url,
            timeout=15,
            allow_redirects=False,
            headers={
                "User-Agent": "Mozilla/5.0 YetiCheck/1.0"
            }
        )

        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")

            if not location:
                break

            next_url = requests.compat.urljoin(current_url, location)

            redirect_chain.append(next_url)
            current_url = next_url
            continue

        return response, current_url, redirect_chain

    return response, current_url, redirect_chain


def get_tls_information(hostname):
    result = {
        "enabled": False,
        "valid": False,
        "issuer": "Unknown",
        "expires": "Unknown"
    }

    try:
        context = ssl.create_default_context()

        with socket.create_connection((hostname, 443), timeout=8) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as secure_socket:
                cert = secure_socket.getpeercert()

                result["enabled"] = True
                result["valid"] = True

                issuer_parts = cert.get("issuer", [])

                issuer_text = []

                for group in issuer_parts:
                    for key, value in group:
                        if key == "organizationName":
                            issuer_text.append(value)

                if issuer_text:
                    result["issuer"] = ", ".join(issuer_text)

                result["expires"] = cert.get("notAfter", "Unknown")

    except Exception:
        pass

    return result


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

        entities = data.get("entities", [])

        for entity in entities:
            roles = entity.get("roles", [])

            if "registrar" in roles:
                vcard = entity.get("vcardArray", [])

                if len(vcard) == 2:
                    for field in vcard[1]:
                        if len(field) >= 4 and field[0] == "fn":
                            result["registrar"] = field[3]
                            break

        events = data.get("events", [])

        for event in events:
            action = event.get("eventAction", "").lower()

            if action in (
                "registration",
                "registered",
                "creation",
                "created"
            ):
                date_text = event.get("eventDate")

                if date_text:
                    created = datetime.fromisoformat(
                        date_text.replace("Z", "+00:00")
                    )

                    result["created"] = created

                    now = datetime.now(timezone.utc)

                    result["age_days"] = (now - created).days

                    break

    except Exception:
        pass

    return result


def check_phishtank(url):
    result = {
        "checked": False,
        "listed": False,
        "verified": False,
        "valid": False
    }

    if not USE_PHISHTANK:
        return result

    try:
        data = {
            "url": url,
            "format": "json"
        }

        if PHISHTANK_APP_KEY:
            data["app_key"] = PHISHTANK_APP_KEY

        response = requests.post(
            "https://checkurl.phishtank.com/checkurl/",
            data=data,
            timeout=12,
            headers={"User-Agent": "YetiCheck/1.0"}
        )

        if response.status_code != 200:
            return result

        payload = response.json()
        details = payload.get("results", {})

        result["checked"] = True

        def yes(value):
            return str(value).lower() in (
                "true", "yes", "y", "1"
            )

        result["listed"] = yes(details.get("in_database", False))
        result["verified"] = yes(details.get("verified", False))
        result["valid"] = yes(details.get("valid", False))

    except Exception:
        pass

    return result


def detect_claimed_brand(hostname, registered_domain, page):
    """
    Only use strong identity signals.

    Normal social links are ignored, so a company website containing
    a LinkedIn link will not be treated as LinkedIn.
    """

    hostname_lower = hostname.lower()
    title = (page.get("title", "") or "").lower()
    site_name = (page.get("site_name", "") or "").lower()
    heading = (page.get("heading", "") or "").lower()
    password_field = page.get("password_field", False)

    for brand in KNOWN_BRANDS:
        if brand in hostname_lower:
            return brand

        if brand in site_name and site_name.strip():
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

        for phrase in phrases:
            if phrase in combined:
                return brand

        if password_field and (brand in title or brand in heading):
            return brand

    return None


def is_official_brand_domain(brand, registered_domain):
    if not brand:
        return True

    return registered_domain.lower() in KNOWN_BRANDS.get(brand, [])


def simple_edit_distance(first, second):
    rows = len(first) + 1
    columns = len(second) + 1
    table = [[0] * columns for _ in range(rows)]

    for row in range(rows):
        table[row][0] = row

    for column in range(columns):
        table[0][column] = column

    for row in range(1, rows):
        for column in range(1, columns):
            cost = 0 if first[row - 1] == second[column - 1] else 1
            table[row][column] = min(
                table[row - 1][column] + 1,
                table[row][column - 1] + 1,
                table[row - 1][column - 1] + cost
            )

    return table[-1][-1]


def detect_lookalike_domain(registered_domain):
    extracted = tldextract.extract(registered_domain)
    domain_name = extracted.domain.lower()

    if not domain_name:
        return None

    for brand in KNOWN_BRANDS:
        if is_official_brand_domain(brand, registered_domain):
            continue

        if brand in domain_name and domain_name != brand:
            return brand

        if len(brand) >= 5:
            distance = simple_edit_distance(domain_name, brand)
            similarity = SequenceMatcher(None, domain_name, brand).ratio()

            if distance == 1 or similarity >= 0.88:
                return brand

    return None


def get_browser_path():
    possible_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium"
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def inspect_page(final_url):
    result = {
        "title": "Unknown",
        "site_name": "",
        "heading": "",
        "password_field": False,
        "email_field": False,
        "forms": [],
        "screenshot": None
    }

    screenshot_path = "yeti_screenshot.png"

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

            browser = p.chromium.launch(**launch_options)

            page = browser.new_page(
                viewport={
                    "width": 1366,
                    "height": 768
                }
            )

            page.goto(
                final_url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            try:
                result["title"] = page.title()
            except Exception:
                pass

            try:
                meta = page.locator('meta[property="og:site_name"]')
                if meta.count() > 0:
                    result["site_name"] = meta.first.get_attribute("content") or ""
            except Exception:
                pass

            try:
                heading = page.locator("h1")
                if heading.count() > 0:
                    result["heading"] = heading.first.inner_text(timeout=2000) or ""
            except Exception:
                pass

            try:
                result["password_field"] = page.locator(
                    'input[type="password"]'
                ).count() > 0
            except Exception:
                pass

            try:
                email_selectors = (
                    'input[type="email"], '
                    'input[name*="email" i], '
                    'input[name*="user" i]'
                )

                result["email_field"] = page.locator(
                    email_selectors
                ).count() > 0
            except Exception:
                pass

            try:
                forms = page.locator("form")

                count = min(forms.count(), 20)

                for i in range(count):
                    form = forms.nth(i)

                    action = form.get_attribute("action") or ""

                    if action:
                        action = requests.compat.urljoin(
                            final_url,
                            action
                        )

                    result["forms"].append(action)

            except Exception:
                pass

            try:
                page.screenshot(
                    path=screenshot_path,
                    full_page=True
                )

                result["screenshot"] = screenshot_path

            except Exception:
                pass

            browser.close()

    except Exception:
        pass

    return result


def analyse_url(url):
    result = {
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
        "phishing_database": {},
        "brand": None,
        "lookalike_brand": None
    }

    response, final_url, redirects = safe_request(url)

    result["final_url"] = final_url
    result["redirects"] = redirects

    hostname = get_hostname(final_url)
    registered_domain = get_registered_domain(hostname)

    result["hostname"] = hostname
    result["registered_domain"] = registered_domain
    result["ip_addresses"] = resolve_ip(hostname)

    # Reputation check. A positive match is strong evidence.
    # No match does not mean the website is safe.
    result["phishing_database"] = check_phishtank(final_url)
    phishing = result["phishing_database"]

    if (
        phishing.get("listed")
        and phishing.get("verified")
        and phishing.get("valid")
    ):
        result["score"] += 70
        result["reasons"].append(
            "This address is listed as a verified phishing page in PhishTank."
        )

    # Registration age. New domains are only supporting evidence.
    result["rdap"] = get_rdap_information(registered_domain)
    age = result["rdap"].get("age_days")

    if age is not None:
        if age < 14:
            result["score"] += 25
            result["reasons"].append(
                "The domain was registered less than 14 days ago."
            )
        elif age < 30:
            result["score"] += 18
            result["reasons"].append(
                "The domain was registered less than 30 days ago."
            )
        elif age < 180:
            result["score"] += 6
            result["reasons"].append(
                "The domain was registered less than 6 months ago."
            )

    # HTTPS certificate.
    if final_url.startswith("https://"):
        result["tls"] = get_tls_information(hostname)
    else:
        result["tls"] = {
            "enabled": False,
            "valid": False,
            "issuer": "Unknown",
            "expires": "Unknown"
        }
        result["score"] += 12
        result["reasons"].append(
            "The final page is not using HTTPS."
        )

    # Inspect the page.
    result["page"] = inspect_page(final_url)

    # Strong brand identity check.
    brand = detect_claimed_brand(
        hostname,
        registered_domain,
        result["page"]
    )
    result["brand"] = brand

    if brand and not is_official_brand_domain(brand, registered_domain):
        result["score"] += 40
        result["reasons"].append(
            f"The page appears to identify as {brand.title()}, "
            f"but the registered domain is {registered_domain}."
        )

    # Lookalike / typo domain check.
    lookalike = detect_lookalike_domain(registered_domain)
    result["lookalike_brand"] = lookalike

    if lookalike and lookalike != brand:
        result["score"] += 30
        result["reasons"].append(
            f"The domain name looks similar to {lookalike.title()}, "
            "but it is not one of that brand's known official domains."
        )

    # Redirects matter mainly when the registered domain changes.
    entered_domain = get_registered_domain(get_hostname(url))

    if (
        entered_domain
        and registered_domain
        and entered_domain != registered_domain
    ):
        result["score"] += 12
        result["reasons"].append(
            "The link redirected to a different registered domain."
        )

    if len(redirects) >= 4:
        result["score"] += 6
        result["reasons"].append(
            "The link used several redirects."
        )

    # Punycode can be used for visually similar domains.
    if hostname.startswith("xn--") or ".xn--" in hostname:
        result["score"] += 22
        result["reasons"].append(
            "The domain uses punycode, which can be used to create lookalike names."
        )

    # Direct IP URLs are unusual for normal public login pages.
    try:
        ip_address(hostname)
        result["score"] += 20
        result["reasons"].append(
            "The website uses an IP address instead of a normal domain name."
        )
    except ValueError:
        pass

    # Misleading user-info syntax.
    if "@" in final_url:
        result["score"] += 20
        result["reasons"].append(
            "The URL contains an @ symbol, which can make the real destination harder to see."
        )

    # Long URLs are weak evidence only.
    if len(final_url) > 200:
        result["score"] += 4
        result["reasons"].append(
            "The URL is unusually long."
        )

    # Password fields are common on legitimate sites, so use a small weight.
    if result["page"].get("password_field"):
        result["score"] += 5
        result["reasons"].append(
            "The page contains a password field."
        )

    # Sending a form to another registered domain is a stronger warning.
    for action in result["page"].get("forms", []):
        if not action:
            continue

        form_domain = get_registered_domain(get_hostname(action))

        if (
            form_domain
            and registered_domain
            and form_domain != registered_domain
        ):
            result["score"] += 35
            result["reasons"].append(
                "A form on the page sends information to a different registered domain."
            )
            break

    result["score"] = min(result["score"], 100)

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
# INPUT
# ------------------------------------------------------------
# A form means pressing Enter inside the box starts the check.

with st.form("website_check", clear_on_submit=False):
    website = st.text_input(
        "Website",
        placeholder="https://example.com",
        key="website_input"
    )

    submitted = st.form_submit_button("Check website")


# ------------------------------------------------------------
# ANALYSIS
# ------------------------------------------------------------

if submitted:

    if not website.strip():
        st.warning("Enter a website address.")
        st.stop()

    website = clean_url(website)

    with st.spinner("Checking website..."):

        try:
            result = analyse_url(website)

        except Exception as error:
            st.error(f"Check failed: {error}")
            st.stop()


    # --------------------------------------------------------
    # MAIN RESULT
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="result-box">
            <div class="result-title">{result["verdict"]}</div>
            <div class="muted">
                Risk score: {result["score"]}/100
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


    # --------------------------------------------------------
    # SIMPLE SUMMARY
    # --------------------------------------------------------

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Registered domain",
            result["registered_domain"] or "Unknown"
        )

    with col2:
        age = result["rdap"].get("age_days")

        st.metric(
            "Domain age",
            f"{age} days" if age is not None else "Unknown"
        )

    with col3:
        st.metric(
            "HTTPS",
            "Yes" if result["tls"].get("valid") else "No"
        )


    # --------------------------------------------------------
    # FINDINGS
    # --------------------------------------------------------

    st.subheader("Findings")

    if result["reasons"]:
        for reason in result["reasons"]:
            st.write(reason)
    else:
        st.write(
            "No major phishing indicators were found in these checks."
        )


    # --------------------------------------------------------
    # RECOMMENDATION
    # --------------------------------------------------------

    st.subheader("Recommendation")

    if result["verdict"] == "High Risk":
        st.error(
            "Do not enter passwords, payment details or personal information "
            "on this page. Open the organisation's official website separately."
        )

    elif result["verdict"] == "Suspicious":
        st.warning(
            "The website has suspicious characteristics. Verify the address "
            "independently before entering any sensitive information."
        )

    elif result["verdict"] == "Caution":
        st.warning(
            "Some unusual characteristics were found. Check the domain carefully "
            "before entering passwords or personal information."
        )

    else:
        st.info(
            "No major phishing indicators were found. This does not guarantee "
            "that the website is genuine, so still check the address before "
            "entering sensitive information."
        )


    # --------------------------------------------------------
    # PAGE PREVIEW
    # --------------------------------------------------------

    screenshot = result["page"].get("screenshot")

    if screenshot and os.path.exists(screenshot):
        st.subheader("Website preview")
        st.image(
            screenshot,
            use_container_width=True
        )


    # --------------------------------------------------------
    # EXTRA DETAILS
    # --------------------------------------------------------

    with st.expander("Website details"):

        st.write(
            "Final address:",
            result["final_url"]
        )

        st.write(
            "Hostname:",
            result["hostname"]
        )

        st.write(
            "Registered domain:",
            result["registered_domain"]
        )

        st.write(
            "IP addresses:",
            ", ".join(result["ip_addresses"])
            if result["ip_addresses"]
            else "Unknown"
        )

        st.write(
            "Registrar:",
            result["rdap"].get(
                "registrar",
                "Unknown"
            )
        )

        st.write(
            "Page title:",
            result["page"].get(
                "title",
                "Unknown"
            )
        )

        st.write(
            "Password field:",
            "Yes"
            if result["page"].get("password_field")
            else "No"
        )

        st.write(
            "Email or username field:",
            "Yes"
            if result["page"].get("email_field")
            else "No"
        )

        phishing = result.get("phishing_database", {})

        if phishing.get("checked"):
            if (
                phishing.get("listed")
                and phishing.get("verified")
                and phishing.get("valid")
            ):
                reputation_text = "Listed as verified phishing"
            elif phishing.get("listed"):
                reputation_text = "Found in database, but not confirmed as active phishing"
            else:
                reputation_text = "No match found"
        else:
            reputation_text = "Not available"

        st.write(
            "Phishing reputation:",
            reputation_text
        )


    with st.expander("Redirects"):

        if result["redirects"]:
            st.write("Original:")
            st.write(website)

            for item in result["redirects"]:
                st.write(item)

            st.write("Final:")
            st.write(result["final_url"])

        else:
            st.write("No redirects were detected.")


    with st.expander("Certificate"):

        st.write(
            "Valid HTTPS certificate:",
            "Yes"
            if result["tls"].get("valid")
            else "No"
        )

        st.write(
            "Certificate issuer:",
            result["tls"].get(
                "issuer",
                "Unknown"
            )
        )

        st.write(
            "Certificate expiry:",
            result["tls"].get(
                "expires",
                "Unknown"
            )
        )

    st.divider()

    if st.button("Reset", key="reset_button"):
        st.session_state["website_input"] = ""
        st.rerun()

