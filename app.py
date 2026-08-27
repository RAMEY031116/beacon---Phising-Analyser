import streamlit as st
import requests
import whois
import os
import socket
import ipaddress
from urllib.parse import urlparse
from datetime import datetime
from playwright.sync_api import sync_playwright

# ---------------- PAGE CONFIG ---------------- #

st.set_page_config(
    page_title="Yeti Check",
    layout="wide"
)

# ---------------- STYLING ---------------- #

st.markdown("""
<style>

.main-title{
    text-align:center;
    font-size:52px;
    font-weight:700;
    margin-bottom:0;
}

.sub-title{
    text-align:center;
    color:#888;
    font-size:18px;
    margin-bottom:30px;
}

.stat-box{
    background:#f5f5f5;
    padding:15px;
    border-radius:10px;
}

</style>
""", unsafe_allow_html=True)

# ---------------- HERO ---------------- #

st.markdown("""
<div class="main-title">
Yeti Check
</div>

<div class="sub-title">
Investigate links before you interact with them
</div>
""", unsafe_allow_html=True)

url = st.text_input(
    "Enter URL",
    placeholder="https://example.com"
)

analyse = st.button("Analyse")

# ---------------- ANALYSIS ---------------- #

if analyse:

    if not url:
        st.warning("Please enter a URL.")
        st.stop()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:

        response = requests.get(
            url,
            allow_redirects=True,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        redirects = [r.url for r in response.history]

        final_url = response.url

        parsed = urlparse(final_url)

        domain = parsed.netloc

        # ---------------- WHOIS ---------------- #

        age = None
        registrar = "Unknown"

        try:

            info = whois.whois(domain)

            registrar = getattr(
                info,
                "registrar",
                "Unknown"
            )

            created = info.creation_date

            if isinstance(created, list):
                created = created[0]

            if created:
                age = (
                    datetime.now() - created
                ).days

        except:
            pass

        # ---------------- IP ---------------- #

        try:
            ip_address = socket.gethostbyname(domain)
        except:
            ip_address = "Unknown"

        # ---------------- SCREENSHOT ---------------- #

        page_title = "Unknown"

        chromium_paths = [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium"
        ]

        chromium_path = None

        for path in chromium_paths:
            if os.path.exists(path):
                chromium_path = path
                break

        screenshot_file = "screenshot.png"

        if chromium_path:

            with sync_playwright() as p:

                browser = p.chromium.launch(
                    executable_path=chromium_path,
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage"
                    ]
                )

                page = browser.new_page()

                page.goto(
                    final_url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )

                page_title = page.title()

                page.screenshot(
                    path=screenshot_file,
                    full_page=True
                )

                browser.close()

        # ---------------- RISK ANALYSIS ---------------- #

        score = 0
        reasons = []

        suspicious_words = [
            "login",
            "signin",
            "password",
            "verify",
            "account",
            "authentication",
            "secure",
            "payment",
            "invoice",
            "update"
        ]

        detected_keywords = []

        text_to_check = (
            final_url.lower()
            + " "
            + page_title.lower()
        )

        for word in suspicious_words:

            if word in text_to_check:
                detected_keywords.append(word)

        brands = [
            "microsoft",
            "google",
            "paypal",
            "amazon",
            "adobe",
            "dhl",
            "dropbox",
            "onedrive",
            "office365"
        ]

        detected_brands = []

        for brand in brands:
            if brand.lower() in text_to_check:
                detected_brands.append(brand)

        if len(redirects) >= 2:
            score += 20
            reasons.append(
                "+20 Multiple redirects detected"
            )

        if age and age < 30:
            score += 40
            reasons.append(
                "+40 Recently registered domain"
            )

        if "-" in domain:
            score += 10
            reasons.append(
                "+10 Hyphenated domain"
            )

        if detected_keywords:
            score += 15
            reasons.append(
                "+15 Authentication related keywords"
            )

        try:

            ipaddress.ip_address(domain)

            score += 15

            reasons.append(
                "+15 Direct IP address used"
            )

        except:
            pass

        suspicious_tlds = [
            ".xyz",
            ".top",
            ".click",
            ".gq",
            ".tk",
            ".ml",
            ".cf"
        ]

        for tld in suspicious_tlds:

            if domain.endswith(tld):

                score += 10

                reasons.append(
                    "+10 Commonly abused TLD"
                )

                break

        if score >= 60:
            verdict = "Potentially Suspicious"

        elif score >= 30:
            verdict = "Proceed With Caution"

        else:
            verdict = "Trusted"

        # ---------------- TOP METRICS ---------------- #

        st.divider()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Risk Score",
                f"{score}/100"
            )

        with col2:
            st.metric(
                "Redirects",
                len(redirects)
            )

        with col3:
            st.metric(
                "HTTPS",
                "Yes" if final_url.startswith("https") else "No"
            )

        with col4:
            st.metric(
                "Domain Age",
                f"{age} Days" if age else "Unknown"
            )

        # ---------------- SCREENSHOT ---------------- #

        st.divider()

        st.subheader("Website Screenshot")

        if os.path.exists(screenshot_file):
            st.image(
                screenshot_file,
                use_container_width=True
            )

        # ---------------- KEY FINDINGS ---------------- #

        st.subheader("Key Findings")

        st.write(f"• Final destination: {domain}")
        st.write(f"• Redirect count: {len(redirects)}")
        st.write(f"• Registrar: {registrar}")
        st.write(f"• Resolved IP: {ip_address}")

        # ---------------- PAGE INFO ---------------- #

        st.subheader("Page Information")

        st.write("**Page Title:**", page_title)

        favicon = (
            f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
        )

        st.image(
            favicon,
            width=40
        )

        # ---------------- SUSPICIOUS INDICATORS ---------------- #

        st.subheader("Indicators")

        if detected_keywords:

            st.warning(
                "Keywords detected: "
                + ", ".join(detected_keywords)
            )

        else:

            st.success(
                "No suspicious keywords detected."
            )

        if detected_brands:

            st.info(
                "Possible brand references: "
                + ", ".join(detected_brands)
            )

        # ---------------- ANALYST VERDICT ---------------- #

        st.subheader("Analyst Verdict")

        verdict_text = f"""
The supplied URL eventually resolves to:

{final_url}

The page title identified was:

{page_title}

Risk Assessment:

{verdict}

This assessment is based on redirect behaviour,
domain characteristics, keyword analysis,
domain registration age and URL structure.

Recommendation:

Avoid entering credentials or personal
information unless the destination
has been independently verified.
"""

        st.info(verdict_text)

        # ---------------- TECHNICAL ---------------- #

        with st.expander("Redirect Chain"):

            if redirects:

                for r in redirects:
                    st.write(r)

            else:
                st.write(
                    "No redirects detected."
                )

        with st.expander("Domain Details"):

            st.write("Domain:", domain)
            st.write("Registrar:", registrar)
    
