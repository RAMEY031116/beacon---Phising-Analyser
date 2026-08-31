
import streamlit as st
import requests
import socket
import ssl
import os
import re
import io
import base64
import hashlib
import sqlite3
from urllib.parse import urlparse
from datetime import datetime, timezone
from ipaddress import ip_address
from difflib import SequenceMatcher
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

# Optional PDF report support
try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image as RLImage,
        PageBreak,
        KeepTogether,
    )
    from reportlab.lib.utils import ImageReader
    PDF_REPORT_SUPPORT = True
except Exception:
    PDF_REPORT_SUPPORT = False

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

# ------------------------------------------------------------
# APPEARANCE
# ------------------------------------------------------------

if "yeti_appearance" not in st.session_state:
    st.session_state["yeti_appearance"] = "System"

appearance = st.session_state["yeti_appearance"]


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


URLSCAN_API_KEY = get_secret(
    "URLSCAN_API_KEY"
)

HISTORY_DB_PATH = "yeti_history.db"


# ------------------------------------------------------------
# THEME-SAFE STYLE
# ------------------------------------------------------------


def get_theme_values(mode):
    if mode == "Dark":
        return {
            "page": "#101820",
            "surface": "#18232e",
            "surface2": "#202d39",
            "text": "#f3f6f9",
            "muted": "#b8c3ce",
            "border": "#394957",
            "accent": "#67a9cc",
            "accent_hover": "#7bb8d7",
            "input": "#18232e",
            "input_text": "#f3f6f9",
        }

    if mode == "Light":
        return {
            "page": "#f5f7fa",
            "surface": "#ffffff",
            "surface2": "#f0f4f7",
            "text": "#17212b",
            "muted": "#667085",
            "border": "#d7dee7",
            "accent": "#2c6e91",
            "accent_hover": "#235a78",
            "input": "#ffffff",
            "input_text": "#17212b",
        }

    # System uses a light baseline plus a browser dark-mode override.
    return {
        "page": "#f5f7fa",
        "surface": "#ffffff",
        "surface2": "#f0f4f7",
        "text": "#17212b",
        "muted": "#667085",
        "border": "#d7dee7",
        "accent": "#2c6e91",
        "accent_hover": "#235a78",
        "input": "#ffffff",
        "input_text": "#17212b",
    }


theme = get_theme_values(
    appearance
)

system_dark_css = ""

if appearance == "System":
    system_dark_css = """
    @media (prefers-color-scheme: dark) {
        :root {
            --yeti-page: #101820;
            --yeti-surface: #18232e;
            --yeti-surface2: #202d39;
            --yeti-text: #f3f6f9;
            --yeti-muted: #b8c3ce;
            --yeti-border: #394957;
            --yeti-accent: #67a9cc;
            --yeti-accent-hover: #7bb8d7;
            --yeti-input: #18232e;
            --yeti-input-text: #f3f6f9;
        }
    }
    """

st.markdown(
    f"""
    <style>
    :root {{
        --yeti-page: {theme["page"]};
        --yeti-surface: {theme["surface"]};
        --yeti-surface2: {theme["surface2"]};
        --yeti-text: {theme["text"]};
        --yeti-muted: {theme["muted"]};
        --yeti-border: {theme["border"]};
        --yeti-accent: {theme["accent"]};
        --yeti-accent-hover: {theme["accent_hover"]};
        --yeti-input: {theme["input"]};
        --yeti-input-text: {theme["input_text"]};
    }}

    {system_dark_css}

    html, body, .stApp {{
        background: var(--yeti-page) !important;
        color: var(--yeti-text) !important;
    }}

    .block-container {{
        max-width: 980px;
        padding-top: 1rem;
        padding-bottom: 3rem;
    }}

    /* Hide Streamlit chrome completely.
       This removes the black bar and repository/source controls. */
    header[data-testid="stHeader"],
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"] {{
        display: none !important;
    }}

    .stApp > header {{
        display: none !important;
    }}

    #MainMenu,
    footer {{
        visibility: hidden !important;
    }}

    .yeti-header {{
        display: flex;
        justify-content: center;
        margin: 0.15rem 0 0.1rem 0;
    }}

    .yeti-home {{
        display: inline-flex;
        align-items: center;
        gap: 0.65rem;
        text-decoration: none !important;
        padding: 0.3rem 0.45rem;
        border-radius: 10px;
    }}

    .yeti-home:hover {{
        background: var(--yeti-surface2) !important;
    }}

    .yeti-logo {{
        width: 48px;
        height: 48px;
        flex: 0 0 48px;
    }}

    .yeti-wordmark {{
        font-size: 2rem;
        font-weight: 750;
        letter-spacing: -0.03em;
        color: var(--yeti-text) !important;
    }}

    .yeti-subtitle {{
        text-align: center;
        color: var(--yeti-muted) !important;
        margin-bottom: 0.85rem;
        font-size: 0.93rem;
    }}

    .stApp p,
    .stApp label,
    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp h4,
    .stApp h5,
    .stApp h6 {{
        color: var(--yeti-text) !important;
    }}

    .stTextArea textarea,
    .stTextInput input {{
        background: var(--yeti-input) !important;
        color: var(--yeti-input-text) !important;
        caret-color: var(--yeti-input-text) !important;
        border: 1px solid var(--yeti-border) !important;
        border-radius: 9px !important;
        box-shadow: none !important;
    }}

    .stTextArea textarea::placeholder,
    .stTextInput input::placeholder {{
        color: var(--yeti-muted) !important;
        opacity: 0.9 !important;
    }}

    .stTextArea textarea:focus,
    .stTextInput input:focus {{
        border-color: var(--yeti-accent) !important;
        box-shadow: 0 0 0 1px var(--yeti-accent) !important;
    }}

    .stButton > button,
    div[data-testid="stFormSubmitButton"] > button,
    div[data-testid="stDownloadButton"] button {{
        background: var(--yeti-accent) !important;
        color: #ffffff !important;
        border: 1px solid var(--yeti-accent) !important;
        border-radius: 8px !important;
        font-weight: 650 !important;
        min-height: 2.5rem;
    }}

    .stButton > button *,
    div[data-testid="stFormSubmitButton"] > button *,
    div[data-testid="stDownloadButton"] button * {{
        color: #ffffff !important;
    }}

    .stButton > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover,
    div[data-testid="stDownloadButton"] button:hover {{
        background: var(--yeti-accent-hover) !important;
        border-color: var(--yeti-accent-hover) !important;
        color: #ffffff !important;
    }}

    section[data-testid="stFileUploaderDropzone"] {{
        background: var(--yeti-surface) !important;
        color: var(--yeti-text) !important;
        border: 1px dashed var(--yeti-border) !important;
        border-radius: 9px !important;
    }}

    section[data-testid="stFileUploaderDropzone"] *,
    div[data-testid="stFileUploader"] * {{
        color: var(--yeti-text) !important;
    }}

    section[data-testid="stFileUploaderDropzone"] button {{
        background: var(--yeti-surface2) !important;
        color: var(--yeti-text) !important;
        border: 1px solid var(--yeti-border) !important;
    }}

    section[data-testid="stFileUploaderDropzone"] button * {{
        color: var(--yeti-text) !important;
    }}

    .result-card {{
        background: var(--yeti-surface) !important;
        border: 1px solid var(--yeti-border) !important;
        border-radius: 10px;
        padding: 0.75rem 0.9rem;
        margin: 0.65rem 0;
    }}

    .result-title {{
        font-size: 1.05rem;
        font-weight: 700;
        color: var(--yeti-text) !important;
    }}

    .muted {{
        color: var(--yeti-muted) !important;
        font-size: 0.86rem;
    }}

    div[data-testid="stMetric"] {{
        background: var(--yeti-surface) !important;
        border: 1px solid var(--yeti-border) !important;
        border-radius: 9px !important;
        padding: 0.65rem !important;
    }}

    div[data-testid="stMetric"] *,
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] * {{
        color: var(--yeti-text) !important;
    }}

    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] * {{
        color: var(--yeti-muted) !important;
    }}

    div[data-testid="stExpander"] {{
        background: var(--yeti-surface) !important;
        border: 1px solid var(--yeti-border) !important;
        border-radius: 9px !important;
        overflow: hidden !important;
    }}

    div[data-testid="stExpander"] details,
    div[data-testid="stExpander"] summary {{
        background: var(--yeti-surface) !important;
        color: var(--yeti-text) !important;
    }}

    div[data-testid="stExpander"] summary:hover {{
        background: var(--yeti-surface2) !important;
    }}

    div[data-testid="stExpander"] *,
    div[data-testid="stExpander"] svg {{
        color: var(--yeti-text) !important;
        fill: currentColor !important;
    }}

    div[data-testid="stTabs"] button,
    div[data-testid="stTabs"] button * {{
        color: var(--yeti-text) !important;
    }}

    div[data-testid="stImage"] {{
        max-width: 820px;
        margin: 0.4rem auto 1rem auto;
    }}

    div[data-testid="stImage"] img {{
        border: 1px solid var(--yeti-border);
        border-radius: 10px;
        background: var(--yeti-surface);
    }}

    /* Risk colours remain meaningful in both themes */
    .risk-banner {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        border-radius: 11px;
        padding: 0.85rem 1rem;
        margin: 0.65rem 0 0.8rem 0;
        border: 1px solid transparent;
    }}

    .risk-banner-domain {{
        font-size: 1.05rem;
        font-weight: 700;
        line-height: 1.2;
        word-break: break-word;
    }}

    .risk-banner-status {{
        margin-top: 0.15rem;
        font-size: 0.8rem;
        opacity: 0.78;
    }}

    .risk-banner-verdict {{
        font-size: 1.3rem;
        font-weight: 800;
        white-space: nowrap;
    }}

    .risk-low {{
        background: #dff4e7;
        border-color: #addbbd;
        color: #14532d;
    }}

    .risk-caution {{
        background: #fff4d2;
        border-color: #ead17a;
        color: #745000;
    }}

    .risk-suspicious {{
        background: #ffe9d4;
        border-color: #e7b57e;
        color: #82400c;
    }}

    .risk-high {{
        background: #fbdede;
        border-color: #e8aaaa;
        color: #831b1b;
    }}

    .risk-unavailable {{
        background: var(--yeti-surface2);
        border-color: var(--yeti-border);
        color: var(--yeti-text);
    }}

    .risk-banner * {{
        color: inherit !important;
    }}

    hr {{
        border-color: var(--yeti-border) !important;
    }}

    @media (max-width: 650px) {{
        .block-container {{
            padding-left: 1rem;
            padding-right: 1rem;
        }}

        .risk-banner {{
            align-items: flex-start;
            flex-direction: column;
            gap: 0.35rem;
        }}
    }}
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
            <span class="yeti-byline">by bipzilla</span>
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



with st.expander("Settings"):
    new_appearance = st.radio(
        "Appearance",
        options=[
            "System",
            "Light",
            "Dark"
        ],
        horizontal=True,
        index=[
            "System",
            "Light",
            "Dark"
        ].index(
            st.session_state.get(
                "yeti_appearance",
                "System"
            )
        ),
        help="System follows your device appearance."
    )

    if new_appearance != st.session_state[
        "yeti_appearance"
    ]:
        st.session_state[
            "yeti_appearance"
        ] = new_appearance
        st.rerun()


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
# LOCAL YETI HISTORY
# ------------------------------------------------------------

def privacy_safe_url(url):
    """
    Remove query strings and fragments before writing a URL
    into Yeti's local history database.
    """

    try:
        parsed = urlparse(
            url
        )

        return parsed._replace(
            query="",
            fragment=""
        ).geturl()

    except Exception:
        return url


def initialise_history_database():
    try:
        connection = sqlite3.connect(
            HISTORY_DB_PATH,
            timeout=5
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at TEXT NOT NULL,
                domain TEXT,
                original_url TEXT,
                final_url TEXT,
                verdict TEXT,
                score INTEGER,
                status_code INTEGER
            )
            """
        )

        connection.commit()
        connection.close()

    except Exception:
        pass


def get_local_history(domain):
    result = {
        "available": False,
        "scan_count": 0,
        "first_seen": None,
        "last_seen": None,
        "highest_score": None,
        "highest_verdict": None,
        "last_verdict": None
    }

    if not domain:
        return result

    try:
        initialise_history_database()

        connection = sqlite3.connect(
            HISTORY_DB_PATH,
            timeout=5
        )

        rows = connection.execute(
            """
            SELECT
                checked_at,
                verdict,
                score
            FROM scans
            WHERE domain = ?
            ORDER BY checked_at ASC
            """,
            (
                domain,
            )
        ).fetchall()

        connection.close()

        result["available"] = True
        result["scan_count"] = len(
            rows
        )

        if rows:
            result["first_seen"] = rows[0][0]
            result["last_seen"] = rows[-1][0]
            result["last_verdict"] = rows[-1][1]

            highest = max(
                rows,
                key=lambda row: (
                    row[2]
                    if row[2] is not None
                    else -1
                )
            )

            result["highest_score"] = highest[2]
            result["highest_verdict"] = highest[1]

    except Exception:
        pass

    return result


def save_local_history(result):
    domain = result.get(
        "registered_domain",
        ""
    )

    if not domain:
        return

    try:
        initialise_history_database()

        connection = sqlite3.connect(
            HISTORY_DB_PATH,
            timeout=5
        )

        connection.execute(
            """
            INSERT INTO scans (
                checked_at,
                domain,
                original_url,
                final_url,
                verdict,
                score,
                status_code
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(
                    timezone.utc
                ).isoformat(),
                domain,
                privacy_safe_url(
                    result.get(
                        "url",
                        ""
                    )
                ),
                privacy_safe_url(
                    result.get(
                        "final_url",
                        ""
                    )
                ),
                result.get(
                    "verdict",
                    ""
                ),
                int(
                    result.get(
                        "score",
                        0
                    )
                    or 0
                ),
                result.get(
                    "status_code"
                )
            )
        )

        connection.commit()
        connection.close()

    except Exception:
        pass


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
# URLSCAN.IO HISTORICAL SEARCH
# ------------------------------------------------------------

def parse_urlscan_date(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        )
    except Exception:
        return None


def check_urlscan_history(hostname):
    """
    Search EXISTING urlscan.io scans for this exact hostname.

    Yeti does not automatically submit the user's URL to urlscan.
    This keeps work URLs from being published by accident.
    """

    result = {
        "configured": bool(
            URLSCAN_API_KEY
        ),
        "checked": False,
        "error": "",
        "total": 0,
        "recent_count": 0,
        "last_seen": None,
        "malicious_found": False,
        "malicious_count": 0,
        "highest_score": None,
        "categories": [],
        "brands": [],
        "latest_title": "",
        "latest_ip": "",
        "latest_country": ""
    }

    if not URLSCAN_API_KEY:
        return result

    if not hostname:
        return result

    # Hostnames contain only a small safe character set after URL parsing.
    safe_hostname = re.sub(
        r"[^A-Za-z0-9._-]",
        "",
        hostname
    )

    if not safe_hostname:
        return result

    try:
        response = requests.get(
            "https://urlscan.io/api/v1/search/",
            params={
                "q": (
                    f'page.domain.keyword:"{safe_hostname}" '
                    'AND date:>now-90d'
                ),
                "size": 10
            },
            headers={
                "api-key": URLSCAN_API_KEY,
                "User-Agent": "YetiCheck/1.0",
                "Accept": "application/json"
            },
            timeout=15
        )

        if response.status_code != 200:
            try:
                data = response.json()
                message = (
                    data.get(
                        "message"
                    )
                    or data.get(
                        "error"
                    )
                )

                if isinstance(
                    message,
                    dict
                ):
                    message = message.get(
                        "message"
                    )

                result["error"] = (
                    str(message)
                    if message
                    else f"HTTP {response.status_code}"
                )

            except Exception:
                result["error"] = (
                    f"HTTP {response.status_code}"
                )

            return result

        data = response.json()

        results = data.get(
            "results",
            []
        )

        result["checked"] = True
        result["total"] = int(
            data.get(
                "total",
                len(results)
            )
            or 0
        )
        result["recent_count"] = len(
            results
        )

        highest_score = None
        categories = set()
        brands = set()
        malicious_count = 0

        for index, scan in enumerate(
            results
        ):
            task = scan.get(
                "task",
                {}
            )
            page = scan.get(
                "page",
                {}
            )
            verdicts = scan.get(
                "verdicts",
                {}
            )

            if index == 0:
                result["last_seen"] = (
                    task.get(
                        "time"
                    )
                    or scan.get(
                        "_source",
                        {}
                    ).get(
                        "task",
                        {}
                    ).get(
                        "time"
                    )
                )

                result["latest_title"] = (
                    page.get(
                        "title"
                    )
                    or ""
                )

                result["latest_ip"] = (
                    page.get(
                        "ip"
                    )
                    or ""
                )

                result["latest_country"] = (
                    page.get(
                        "country"
                    )
                    or ""
                )

            malicious = bool(
                verdicts.get(
                    "malicious",
                    False
                )
            )

            urlscan_verdict = verdicts.get(
                "urlscan",
                {}
            )

            if isinstance(
                urlscan_verdict,
                dict
            ):
                malicious = (
                    malicious
                    or bool(
                        urlscan_verdict.get(
                            "malicious",
                            False
                        )
                    )
                )

                score = urlscan_verdict.get(
                    "score"
                )

                if isinstance(
                    score,
                    (int, float)
                ):
                    if (
                        highest_score is None
                        or score > highest_score
                    ):
                        highest_score = score

                for category in urlscan_verdict.get(
                    "categories",
                    []
                ) or []:
                    categories.add(
                        str(category)
                    )

                for brand in urlscan_verdict.get(
                    "brands",
                    []
                ) or []:
                    if isinstance(
                        brand,
                        dict
                    ):
                        brand_name = (
                            brand.get(
                                "name"
                            )
                            or brand.get(
                                "key"
                            )
                        )

                        if brand_name:
                            brands.add(
                                str(
                                    brand_name
                                )
                            )

            general_score = verdicts.get(
                "score"
            )

            if isinstance(
                general_score,
                (int, float)
            ):
                if (
                    highest_score is None
                    or general_score > highest_score
                ):
                    highest_score = general_score

            if malicious:
                malicious_count += 1

        result["malicious_count"] = (
            malicious_count
        )
        result["malicious_found"] = (
            malicious_count > 0
        )
        result["highest_score"] = (
            highest_score
        )
        result["categories"] = sorted(
            categories
        )
        result["brands"] = sorted(
            brands
        )

    except requests.exceptions.Timeout:
        result["error"] = (
            "urlscan.io timed out."
        )

    except Exception as error:
        result["error"] = str(
            error
        )

    return result


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
    Check Google's Web Risk Lookup API.

    The result keeps a user-readable error so configuration problems
    such as billing, API restrictions or an invalid key can be fixed.
    """

    result = {
        "configured": bool(
            GOOGLE_WEB_RISK_API_KEY
        ),
        "checked": False,
        "confirmed": False,
        "threat_types": [],
        "error": "",
        "status_code": None
    }

    if not GOOGLE_WEB_RISK_API_KEY:
        result["error"] = (
            "API key is not configured in Streamlit Secrets."
        )
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
                    "threatTypes",
                    "MALWARE"
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
            timeout=15,
            headers={
                "User-Agent": "YetiCheck/1.0",
                "Accept": "application/json"
            }
        )

        result["status_code"] = (
            response.status_code
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

            return result

        # Google normally returns a useful JSON error object.
        try:
            error_data = response.json()

            message = (
                error_data.get(
                    "error",
                    {}
                ).get(
                    "message"
                )
            )

            if message:
                result["error"] = (
                    message
                )
            else:
                result["error"] = (
                    f"Google returned HTTP {response.status_code}."
                )

        except Exception:
            result["error"] = (
                f"Google returned HTTP {response.status_code}."
            )

    except requests.exceptions.Timeout:
        result["error"] = (
            "Google Web Risk timed out."
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
    Check the original URL and important redirects.
    """

    checked_urls = []

    for item in (
        [original_url]
        + list(redirects)
        + [final_url]
    ):
        if (
            item
            and item not in checked_urls
        ):
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
        "error": "",
        "status_code": None
    }

    for item in checked_urls:
        result = check_google_webrisk(
            item
        )

        if result.get(
            "status_code"
        ) is not None:
            overall["status_code"] = (
                result["status_code"]
            )

        if result.get(
            "checked"
        ):
            overall["checked"] = True

        if (
            result.get(
                "error"
            )
            and not overall["error"]
        ):
            overall["error"] = (
                result["error"]
            )

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

            response = None
            navigation_error = ""

            try:
                response = page.goto(
                    browser_url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )
            except Exception as error:
                # Some sites display a usable block/challenge page while
                # Playwright still raises a navigation error. Continue so
                # Yeti can capture what the browser actually saw.
                navigation_error = str(
                    error
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
                    "The website restricted Yeti's automated browser. "
                    "The screenshot shows what Yeti was able to see. "
                    "This restriction is not counted as evidence of phishing."
                )

                # Capture the block/challenge page instead of returning
                # without a screenshot.
                try:
                    page.screenshot(
                        path=screenshot_path,
                        full_page=False
                    )

                    if os.path.exists(
                        screenshot_path
                    ):
                        result["screenshot"] = (
                            screenshot_path
                        )
                except Exception:
                    pass

                context.close()
                browser.close()
                return result

            if navigation_error:
                result["preview_status"] = "partial"
                result["preview_message"] = (
                    "The browser could not fully load the website, "
                    "but Yeti captured what was displayed."
                )
            else:
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
        "google_webrisk": {},
        "urlscan": {},
        "local_history": {}
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

    # Local history is read BEFORE this new scan is saved.
    result["local_history"] = get_local_history(
        registered_domain
    )

    # Search existing urlscan.io history.
    # No URL is submitted automatically.
    result["urlscan"] = check_urlscan_history(
        hostname
    )

    if result["urlscan"].get(
        "malicious_found"
    ):
        result["score"] += 30

        result["reasons"].append(
            "Previous website scans have reported this hostname as malicious."
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

        threat_types = result[
            "google_webrisk"
        ].get(
            "threat_types",
            []
        )

        readable_threats = []

        if "SOCIAL_ENGINEERING" in threat_types:
            readable_threats.append(
                "phishing / social engineering"
            )

        if "MALWARE" in threat_types:
            readable_threats.append(
                "malware"
            )

        threat_text = (
            " and ".join(
                readable_threats
            )
            if readable_threats
            else "unsafe activity"
        )

        result["reasons"].append(
            f"Google Web Risk reports this URL for {threat_text}."
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

    save_local_history(
        result
    )

    return result



# ------------------------------------------------------------
# PDF INVESTIGATION REPORT
# ------------------------------------------------------------

def report_safe_text(value):
    """
    Convert values into safe plain text for the PDF.
    """
    if value is None:
        return "Unknown"

    value = str(value)

    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def friendly_reputation_text(result):
    """
    Keep the report useful without putting provider-specific
    Google wording in the user-facing summary.
    """
    reputation = []

    google = result.get(
        "google_webrisk",
        {}
    )

    if google.get(
        "confirmed"
    ):
        threat_types = google.get(
            "threat_types",
            []
        )

        labels = []

        if "SOCIAL_ENGINEERING" in threat_types:
            labels.append(
                "phishing / social engineering"
            )

        if "MALWARE" in threat_types:
            labels.append(
                "malware"
            )

        reputation.append(
            "Live reputation: Reported for "
            + (
                " and ".join(
                    labels
                )
                if labels
                else "unsafe activity"
            )
        )
    elif google.get(
        "checked"
    ):
        reputation.append(
            "Live reputation: No match found"
        )
    else:
        reputation.append(
            "Live reputation: Check unavailable"
        )

    phishtank = result.get(
        "phish_tank",
        {}
    )

    if phishtank.get(
        "confirmed"
    ):
        reputation.append(
            "PhishTank: Verified phishing match"
        )
    elif phishtank.get(
        "checked"
    ):
        reputation.append(
            "PhishTank: No verified match"
        )
    else:
        reputation.append(
            "PhishTank: Check unavailable"
        )

    openphish = result.get(
        "openphish",
        {}
    )

    if openphish.get(
        "confirmed"
    ):
        reputation.append(
            "OpenPhish: Listed in phishing feed"
        )
    elif openphish.get(
        "checked"
    ):
        reputation.append(
            "OpenPhish: No match found"
        )
    else:
        reputation.append(
            "OpenPhish: Check unavailable"
        )

    urlscan = result.get(
        "urlscan",
        {}
    )

    if not urlscan.get(
        "configured"
    ):
        reputation.append(
            "urlscan.io history: Not configured"
        )
    elif not urlscan.get(
        "checked"
    ):
        reputation.append(
            "urlscan.io history: Check unavailable"
        )
    elif urlscan.get(
        "malicious_found"
    ):
        reputation.append(
            "urlscan.io history: "
            f"{urlscan.get('malicious_count', 0)} recent malicious scan(s)"
        )
    elif urlscan.get(
        "recent_count",
        0
    ):
        reputation.append(
            "urlscan.io history: "
            f"{urlscan.get('recent_count', 0)} recent scan(s), "
            "no malicious verdict found"
        )
    else:
        reputation.append(
            "urlscan.io history: No recent scans found"
        )

    return reputation


def clean_report_findings(result):
    findings = []

    for finding in result.get(
        "reasons",
        []
    ):
        clean = str(
            finding
        )

        if (
            "Google Web Risk reports this URL for malware"
            in clean
        ):
            clean = (
                "A live reputation source reports this URL as malicious."
            )

        elif (
            "Google Web Risk reports this URL for phishing / social engineering and malware"
            in clean
        ):
            clean = (
                "A live reputation source reports this URL as phishing and malicious."
            )

        elif (
            "Google Web Risk reports this URL for phishing / social engineering"
            in clean
        ):
            clean = (
                "A live reputation source reports this URL as phishing or deceptive."
            )

        findings.append(
            clean
        )

    return findings


def make_pdf_report(result):
    """
    Build a self-contained PDF investigation report in memory.
    """
    if not PDF_REPORT_SUPPORT:
        return None

    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title=(
            f"Yeti Check Report - "
            f"{result.get('registered_domain') or result.get('hostname') or 'Website'}"
        ),
        author="Yeti Check by bipzilla",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "YetiTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17212B"),
        spaceAfter=4 * mm,
    )

    byline_style = ParagraphStyle(
        "YetiByline",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#667085"),
        spaceAfter=6 * mm,
    )

    section_style = ParagraphStyle(
        "YetiSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#17212B"),
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )

    body_style = ParagraphStyle(
        "YetiBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#17212B"),
        wordWrap="CJK",
    )

    small_style = ParagraphStyle(
        "YetiSmall",
        parent=body_style,
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#475467"),
    )

    story = []

    story.append(
        Paragraph(
            "Yeti Check - Website Investigation Report",
            title_style
        )
    )

    story.append(
        Paragraph(
            "by bipzilla",
            byline_style
        )
    )

    generated = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    verdict = result.get(
        "verdict",
        "Unable to Check"
    )

    score = result.get(
        "score",
        0
    )

    domain = (
        result.get(
            "registered_domain"
        )
        or result.get(
            "hostname"
        )
        or result.get(
            "url",
            "Unknown"
        )
    )

    verdict_colours = {
        "Low Risk": "#DFF4E7",
        "Caution": "#FFF4D2",
        "Suspicious": "#FFE9D4",
        "High Risk": "#FBDEDE",
        "Unable to Check": "#EEF1F4",
    }

    verdict_text_colours = {
        "Low Risk": "#14532D",
        "Caution": "#745000",
        "Suspicious": "#82400C",
        "High Risk": "#831B1B",
        "Unable to Check": "#344054",
    }

    verdict_table = Table(
        [
            [
                Paragraph(
                    f"<b>{report_safe_text(domain)}</b><br/>"
                    f"<font size='7'>{report_safe_text(result.get('site_status', 'Unknown'))}</font>",
                    body_style
                ),
                Paragraph(
                    f"<b>{report_safe_text(verdict)}</b><br/>"
                    f"<font size='7'>Yeti score: {report_safe_text(score)}/100</font>",
                    body_style
                ),
            ]
        ],
        colWidths=[
            115 * mm,
            45 * mm
        ],
    )

    verdict_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor(
                        verdict_colours.get(
                            verdict,
                            "#EEF1F4"
                        )
                    ),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor(
                        verdict_text_colours.get(
                            verdict,
                            "#344054"
                        )
                    ),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.7,
                    colors.HexColor("#CBD5E1"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    story.append(
        verdict_table
    )

    story.append(
        Spacer(
            1,
            4 * mm
        )
    )

    meta_table = Table(
        [
            [
                Paragraph(
                    "<b>Generated</b>",
                    small_style
                ),
                Paragraph(
                    report_safe_text(
                        generated
                    ),
                    small_style
                ),
            ],
            [
                Paragraph(
                    "<b>Original URL</b>",
                    small_style
                ),
                Paragraph(
                    report_safe_text(
                        result.get(
                            "url",
                            "Unknown"
                        )
                    ),
                    small_style
                ),
            ],
            [
                Paragraph(
                    "<b>Final URL</b>",
                    small_style
                ),
                Paragraph(
                    report_safe_text(
                        result.get(
                            "final_url",
                            "Unknown"
                        )
                    ),
                    small_style
                ),
            ],
        ],
        colWidths=[
            35 * mm,
            125 * mm
        ],
    )

    meta_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#D7DEE7"),
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#F3F6F9"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    story.append(
        meta_table
    )

    # Screenshot
    screenshot = result.get(
        "page",
        {}
    ).get(
        "screenshot"
    )

    if (
        screenshot
        and os.path.exists(
            screenshot
        )
    ):
        story.append(
            Paragraph(
                "Website preview",
                section_style
            )
        )

        try:
            image_reader = ImageReader(
                screenshot
            )
            width_px, height_px = (
                image_reader.getSize()
            )

            max_width = 160 * mm
            max_height = 95 * mm

            scale = min(
                max_width / width_px,
                max_height / height_px,
                1
            )

            pdf_image = RLImage(
                screenshot,
                width=width_px * scale,
                height=height_px * scale
            )

            story.append(
                pdf_image
            )

        except Exception:
            story.append(
                Paragraph(
                    "Screenshot was captured but could not be embedded in the report.",
                    small_style
                )
            )

    story.append(
        Paragraph(
            "Website and connection details",
            section_style
        )
    )

    rdap = result.get(
        "rdap",
        {}
    )
    tls = result.get(
        "tls",
        {}
    )

    age = rdap.get(
        "age_days"
    )

    expiry = tls.get(
        "expires",
        "Unknown"
    )

    days_left = certificate_days_left(
        expiry
    )

    if days_left is None:
        certificate_expiry = (
            str(
                expiry
            )
            if expiry
            else "Unknown"
        )
    elif days_left < 0:
        certificate_expiry = (
            f"Expired ({expiry})"
        )
    else:
        certificate_expiry = (
            f"{days_left} days remaining ({expiry})"
        )

    detail_rows = [
        ("HTTP status", result.get("status_code", "Unknown")),
        ("Website status", result.get("site_status", "Unknown")),
        ("Content type", result.get("content_type", "Unknown")),
        ("Server", result.get("server", "Unknown")),
        ("Hostname", result.get("hostname", "Unknown")),
        ("Registered domain", result.get("registered_domain", "Unknown")),
        (
            "IP addresses",
            ", ".join(
                result.get(
                    "ip_addresses",
                    []
                )
            )
            or "Unknown"
        ),
        (
            "Domain age",
            (
                f"{age} days"
                if age is not None
                else "Unknown"
            )
        ),
        ("Registrar", rdap.get("registrar", "Unknown")),
        (
            "HTTPS certificate",
            (
                "Valid"
                if tls.get("valid")
                else "Not validated"
            )
        ),
        ("Certificate issuer", tls.get("issuer", "Unknown")),
        ("Certificate expiry", certificate_expiry),
    ]

    table_data = []

    for label, value in detail_rows:
        table_data.append(
            [
                Paragraph(
                    f"<b>{report_safe_text(label)}</b>",
                    small_style
                ),
                Paragraph(
                    report_safe_text(
                        value
                    ),
                    small_style
                ),
            ]
        )

    details_table = Table(
        table_data,
        colWidths=[
            43 * mm,
            117 * mm
        ],
        repeatRows=0,
    )

    details_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.HexColor("#D7DEE7"),
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#F6F8FA"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    story.append(
        details_table
    )

    # Redirects
    story.append(
        Paragraph(
            "Redirect chain",
            section_style
        )
    )

    redirect_chain = []

    original_url = result.get(
        "url"
    )

    if original_url:
        redirect_chain.append(
            original_url
        )

    for redirect in result.get(
        "redirects",
        []
    ):
        if isinstance(
            redirect,
            dict
        ):
            candidate = (
                redirect.get(
                    "url"
                )
                or redirect.get(
                    "location"
                )
                or str(
                    redirect
                )
            )
        else:
            candidate = str(
                redirect
            )

        if (
            candidate
            and candidate not in redirect_chain
        ):
            redirect_chain.append(
                candidate
            )

    final_url = result.get(
        "final_url"
    )

    if (
        final_url
        and final_url not in redirect_chain
    ):
        redirect_chain.append(
            final_url
        )

    if redirect_chain:
        for index, redirect_url in enumerate(
            redirect_chain,
            start=1
        ):
            story.append(
                Paragraph(
                    f"{index}. {report_safe_text(redirect_url)}",
                    small_style
                )
            )
    else:
        story.append(
            Paragraph(
                "No redirect information was recorded.",
                small_style
            )
        )

    # Reputation
    story.append(
        Paragraph(
            "Reputation checks",
            section_style
        )
    )

    for reputation_line in friendly_reputation_text(
        result
    ):
        story.append(
            Paragraph(
                report_safe_text(
                    reputation_line
                ),
                small_style
            )
        )

    # Browser/page checks
    story.append(
        Paragraph(
            "Page behaviour",
            section_style
        )
    )

    page = result.get(
        "page",
        {}
    )

    page_rows = [
        (
            "Preview status",
            page.get(
                "preview_status",
                "Unknown"
            )
        ),
        (
            "Page title",
            page.get(
                "title",
                "Unknown"
            )
            or "Unknown"
        ),
        (
            "Site name",
            page.get(
                "site_name",
                "Unknown"
            )
            or "Unknown"
        ),
        (
            "Heading",
            page.get(
                "h1",
                "Unknown"
            )
            or "Unknown"
        ),
        (
            "Password field detected",
            (
                "Yes"
                if page.get(
                    "password_field"
                )
                else "No"
            )
        ),
        (
            "Email field detected",
            (
                "Yes"
                if page.get(
                    "email_field"
                )
                else "No"
            )
        ),
    ]

    form_actions = page.get(
        "forms",
        []
    )

    page_rows.append(
        (
            "Form destinations",
            (
                ", ".join(
                    str(
                        item
                    )
                    for item in form_actions
                    if item
                )
                if form_actions
                else "None detected"
            )
        )
    )

    page_table_data = []

    for label, value in page_rows:
        page_table_data.append(
            [
                Paragraph(
                    f"<b>{report_safe_text(label)}</b>",
                    small_style
                ),
                Paragraph(
                    report_safe_text(
                        value
                    ),
                    small_style
                ),
            ]
        )

    page_table = Table(
        page_table_data,
        colWidths=[
            43 * mm,
            117 * mm
        ]
    )

    page_table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.HexColor("#D7DEE7"),
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#F6F8FA"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    story.append(
        page_table
    )

    # Previous activity
    history = result.get(
        "local_history",
        {}
    )

    story.append(
        Paragraph(
            "Yeti history",
            section_style
        )
    )

    if history.get(
        "scan_count",
        0
    ) > 0:
        history_lines = [
            (
                "Previous checks",
                history.get(
                    "scan_count",
                    0
                )
            ),
            (
                "First checked",
                history.get(
                    "first_seen",
                    "Unknown"
                )
            ),
            (
                "Last checked",
                history.get(
                    "last_seen",
                    "Unknown"
                )
            ),
            (
                "Previous verdict",
                history.get(
                    "last_verdict",
                    "Unknown"
                )
            ),
            (
                "Highest previous verdict",
                history.get(
                    "highest_verdict",
                    "Unknown"
                )
            ),
        ]

        for label, value in history_lines:
            story.append(
                Paragraph(
                    f"<b>{report_safe_text(label)}:</b> "
                    f"{report_safe_text(value)}",
                    small_style
                )
            )
    else:
        story.append(
            Paragraph(
                "No previous local Yeti checks were recorded for this domain before this scan.",
                small_style
            )
        )

    # Findings
    story.append(
        Paragraph(
            "Investigation findings",
            section_style
        )
    )

    findings = clean_report_findings(
        result
    )

    if findings:
        for index, finding in enumerate(
            findings,
            start=1
        ):
            story.append(
                Paragraph(
                    f"{index}. {report_safe_text(finding)}",
                    small_style
                )
            )
    else:
        story.append(
            Paragraph(
                "No major warning signs were found by the checks that completed.",
                small_style
            )
        )

    # Disclaimer
    story.append(
        Spacer(
            1,
            5 * mm
        )
    )

    story.append(
        Paragraph(
            "<b>Investigation note</b><br/>"
            "Yeti Check is an investigation aid. A Low Risk result does not prove "
            "that a website is genuine, and a failed or unavailable check is not "
            "evidence that a website is malicious. Validate sensitive requests "
            "through an independent trusted channel.",
            small_style
        )
    )

    document.build(
        story
    )

    buffer.seek(
        0
    )

    return buffer.getvalue()


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
        76,
        54 + line_count * 22
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

with st.expander(
    "Optional: QR code or email file"
):
    qr_tab, email_tab = st.tabs(
        [
            "QR code",
            "Email file"
        ]
    )

    with qr_tab:
        pasted_qr_image = None

        qr_file = st.file_uploader(
            "Upload QR image",
            type=[
                "png",
                "jpg",
                "jpeg",
                "webp"
            ],
            key="qr_upload",
            help="Upload a screenshot or image containing a QR code."
        )

    with email_tab:
        eml_file = st.file_uploader(
            "Upload .eml email",
            type=["eml"],
            key="eml_upload",
            help=(
                "Yeti can extract links and review sender, Reply-To, "
                "SPF, DKIM and DMARC results stored in the email headers."
            )
        )

button_col1, button_col2, button_spacer = st.columns(
    [1, 1, 2]
)

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
                "google_webrisk": {},
                "urlscan": {},
                "local_history": {}
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

        if days_left is None:
            cert_text = "Unknown"
        elif days_left < 0:
            cert_text = "Expired"
        else:
            cert_text = f"{days_left} days"

        # ----------------------------------------------------
        # Website name + colour-coded Yeti risk FIRST
        # ----------------------------------------------------

        verdict = result.get(
            "verdict",
            "Unable to Check"
        )

        risk_class = {
            "Low Risk": "risk-low",
            "Caution": "risk-caution",
            "Suspicious": "risk-suspicious",
            "High Risk": "risk-high",
            "Unable to Check": "risk-unavailable"
        }.get(
            verdict,
            "risk-unavailable"
        )

        st.markdown(
            f"""
            <div class="risk-banner {risk_class}">
                <div>
                    <div class="risk-banner-domain">{domain}</div>
                    <div class="risk-banner-status">
                        {result.get("site_status", "Unknown")}
                    </div>
                </div>
                <div class="risk-banner-verdict">{verdict}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # ----------------------------------------------------
        # Screenshot directly below the risk banner
        # ----------------------------------------------------

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
                    "The website restricted Yeti's automated browser."
                )
            )

        elif preview.get(
            "preview_status"
        ) == "partial":
            st.info(
                preview.get(
                    "preview_message",
                    "Yeti captured only a partial website preview."
                )
            )

        elif preview.get(
            "preview_status"
        ) == "failed":
            st.info(
                "The website preview could not be loaded."
            )

        # Short human-readable conclusion.
        # Keep provider/database names out of the main result.
        if result.get(
            "reasons"
        ):
            main_reason = result["reasons"][0]

            if "Google Web Risk reports this URL for malware" in main_reason:
                main_reason = (
                    "This website has been identified as a known malicious URL."
                )

            elif "Google Web Risk reports this URL for phishing / social engineering" in main_reason:
                main_reason = (
                    "This website has been identified as a known phishing or deceptive URL."
                )

            elif "Google Web Risk reports this URL for phishing / social engineering and malware" in main_reason:
                main_reason = (
                    "This website has been identified as a known phishing and malicious URL."
                )

            st.write(
                main_reason
            )

        else:
            st.write(
                "No major phishing indicators were found. "
                "This is not a guarantee that the website is genuine."
            )

        # ----------------------------------------------------
        # Only useful supporting facts
        # ----------------------------------------------------

        c1, c2, c3 = st.columns(
            3
        )

        with c1:
            st.metric(
                "Domain age",
                (
                    f"{age} days"
                    if age is not None
                    else "Unknown"
                )
            )

        with c2:
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

        with c3:
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

        # ----------------------------------------------------
        # Everything technical stays in one place
        # ----------------------------------------------------

        with st.expander(
            "Why this result?"
        ):
            findings = result.get(
                "reasons",
                []
            )

            if findings:
                for finding in findings[:4]:
                    clean_finding = finding

                    if "Google Web Risk reports this URL for malware" in clean_finding:
                        clean_finding = (
                            "A live reputation source reports this URL as malicious."
                        )

                    elif "Google Web Risk reports this URL for phishing / social engineering" in clean_finding:
                        clean_finding = (
                            "A live reputation source reports this URL as phishing or deceptive."
                        )

                    elif "Google Web Risk reports this URL for phishing / social engineering and malware" in clean_finding:
                        clean_finding = (
                            "A live reputation source reports this URL as phishing and malicious."
                        )

                    st.write(
                        clean_finding
                    )
            else:
                st.write(
                    "No major warning signs were found by the checks that completed."
                )

        with st.expander(
            "Website details"
        ):
            # Native Streamlit layout instead of raw HTML.
            # This avoids HTML being displayed as code in dark mode.

            detail_rows = [
                (
                    "Original address",
                    result["url"]
                ),
                (
                    "Final address",
                    result.get(
                        "final_url",
                        result["url"]
                    )
                ),
                (
                    "HTTP status",
                    str(
                        result.get(
                            "status_code",
                            "Unknown"
                        )
                    )
                ),
                (
                    "Website status",
                    result.get(
                        "site_status",
                        "Unknown"
                    )
                ),
                (
                    "Domain age",
                    (
                        f"{age} days"
                        if age is not None
                        else "Unknown"
                    )
                ),
                (
                    "Registrar",
                    result.get(
                        "rdap",
                        {}
                    ).get(
                        "registrar",
                        "Unknown"
                    )
                ),
                (
                    "HTTPS",
                    (
                        "Valid"
                        if tls.get(
                            "valid"
                        )
                        else "Not validated"
                    )
                ),
                (
                    "Certificate issuer",
                    tls.get(
                        "issuer",
                        "Unknown"
                    )
                ),
                (
                    "Certificate expiry",
                    cert_text
                ),
                (
                    "PhishTank",
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
                ),
                (
                    "OpenPhish",
                    (
                        "Listed in phishing feed"
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
            ]

            urlscan = result.get(
                "urlscan",
                {}
            )

            local_history = result.get(
                "local_history",
                {}
            )

            if urlscan.get(
                "configured"
            ):
                if urlscan.get(
                    "checked"
                ):
                    if urlscan.get(
                        "malicious_found"
                    ):
                        urlscan_text = (
                            f"{urlscan.get('malicious_count', 0)} recent scan(s) "
                            "reported malicious"
                        )
                    elif urlscan.get(
                        "recent_count",
                        0
                    ) > 0:
                        urlscan_text = (
                            f"{urlscan.get('recent_count', 0)} recent scan(s), "
                            "no malicious verdict found"
                        )
                    else:
                        urlscan_text = (
                            "No recent scans found"
                        )
                else:
                    urlscan_text = (
                        urlscan.get(
                            "error"
                        )
                        or "Check unavailable"
                    )

                detail_rows.append(
                    (
                        "urlscan.io history",
                        urlscan_text
                    )
                )
            else:
                detail_rows.append(
                    (
                        "urlscan.io history",
                        "API key not configured"
                    )
                )

            previous_count = local_history.get(
                "scan_count",
                0
            )

            if previous_count > 0:
                history_text = (
                    f"Previously checked {previous_count} time(s); "
                    f"last verdict: {local_history.get('last_verdict', 'Unknown')}"
                )
            else:
                history_text = (
                    "First time Yeti has seen this domain"
                )

            detail_rows.append(
                (
                    "Yeti history",
                    history_text
                )
            )

            for label, value in detail_rows:
                label_col, value_col = st.columns(
                    [1, 2.4]
                )

                with label_col:
                    st.markdown(
                        f"**{label}**"
                    )

                with value_col:
                    st.write(
                        value
                    )

            clean_findings = []

            for finding in result.get(
                "reasons",
                []
            ):
                if (
                    "Google Web Risk reports this URL for malware"
                    in finding
                ):
                    finding = (
                        "Known malicious URL reported by a live reputation source."
                    )

                elif (
                    "Google Web Risk reports this URL for phishing / social engineering"
                    in finding
                ):
                    finding = (
                        "Known phishing or deceptive URL reported by a live reputation source."
                    )

                elif (
                    "Google Web Risk reports this URL for phishing / social engineering and malware"
                    in finding
                ):
                    finding = (
                        "Known phishing and malicious URL reported by a live reputation source."
                    )

                clean_findings.append(
                    finding
                )

            if clean_findings:
                st.markdown(
                    "**Findings**"
                )

                for finding in clean_findings[:8]:
                    st.write(
                        finding
                    )


        history = result.get(
            "local_history",
            {}
        )

        urlscan = result.get(
            "urlscan",
            {}
        )

        if (
            history.get(
                "scan_count",
                0
            ) > 0
            or urlscan.get(
                "recent_count",
                0
            ) > 0
        ):
            with st.expander(
                "Previous activity"
            ):
                if history.get(
                    "scan_count",
                    0
                ) > 0:
                    st.write(
                        "Yeti previously checked this domain:",
                        history.get(
                            "scan_count",
                            0
                        ),
                        "time(s)"
                    )

                    st.write(
                        "First checked by Yeti:",
                        history.get(
                            "first_seen",
                            "Unknown"
                        )
                    )

                    st.write(
                        "Last checked by Yeti:",
                        history.get(
                            "last_seen",
                            "Unknown"
                        )
                    )

                    st.write(
                        "Previous verdict:",
                        history.get(
                            "last_verdict",
                            "Unknown"
                        )
                    )

                    if history.get(
                        "highest_verdict"
                    ):
                        st.write(
                            "Highest previous verdict:",
                            history.get(
                                "highest_verdict"
                            )
                        )

                if urlscan.get(
                    "checked"
                ):
                    st.write(
                        "urlscan.io recent scans found:",
                        urlscan.get(
                            "recent_count",
                            0
                        )
                    )

                    if urlscan.get(
                        "last_seen"
                    ):
                        st.write(
                            "Most recent urlscan observation:",
                            urlscan.get(
                                "last_seen"
                            )
                        )

                    if urlscan.get(
                        "malicious_found"
                    ):
                        st.write(
                            "Recent malicious urlscan verdicts:",
                            urlscan.get(
                                "malicious_count",
                                0
                            )
                        )

                    if urlscan.get(
                        "categories"
                    ):
                        st.write(
                            "urlscan categories:",
                            ", ".join(
                                urlscan.get(
                                    "categories",
                                    []
                                )
                            )
                        )

                    if urlscan.get(
                        "brands"
                    ):
                        st.write(
                            "Brands detected by urlscan:",
                            ", ".join(
                                urlscan.get(
                                    "brands",
                                    []
                                )
                            )
                        )

                    if urlscan.get(
                        "latest_title"
                    ):
                        st.write(
                            "Latest scanned page title:",
                            urlscan.get(
                                "latest_title"
                            )
                        )

                    if urlscan.get(
                        "latest_ip"
                    ):
                        st.write(
                            "Latest scanned IP:",
                            urlscan.get(
                                "latest_ip"
                            )
                        )

                    if urlscan.get(
                        "latest_country"
                    ):
                        st.write(
                            "Latest scanned country:",
                            urlscan.get(
                                "latest_country"
                            )
                        )


        # ----------------------------------------------------
        # Downloadable investigation report
        # ----------------------------------------------------

        if PDF_REPORT_SUPPORT:
            try:
                pdf_report = make_pdf_report(
                    result
                )

                safe_domain = re.sub(
                    r"[^A-Za-z0-9._-]+",
                    "_",
                    (
                        result.get(
                            "registered_domain"
                        )
                        or result.get(
                            "hostname"
                        )
                        or "website"
                    )
                ).strip(
                    "._"
                )

                timestamp_name = datetime.now(
                    timezone.utc
                ).strftime(
                    "%Y%m%d_%H%M%S"
                )

                if pdf_report:
                    st.download_button(
                        "Download PDF report",
                        data=pdf_report,
                        file_name=(
                            f"Yeti_Check_{safe_domain}_{timestamp_name}.pdf"
                        ),
                        mime="application/pdf",
                        use_container_width=False,
                        key=(
                            "pdf_report_"
                            + hashlib.sha256(
                                result.get(
                                    "url",
                                    ""
                                ).encode(
                                    "utf-8"
                                )
                            ).hexdigest()[:12]
                        )
                    )

            except Exception as report_error:
                with st.expander(
                    "PDF report unavailable"
                ):
                    st.write(
                        "Yeti could not build this report:",
                        str(
                            report_error
                        )
                    )

        else:
            st.caption(
                "PDF report support is not installed. Add reportlab to requirements.txt."
            )

        st.divider()
