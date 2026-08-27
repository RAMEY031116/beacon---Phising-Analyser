import streamlit as st
import requests
import whois
import os
import socket
from urllib.parse import urlparse
from datetime import datetime
from playwright.sync_api import sync_playwright

# ----------------------------------
# CONFIG
# ----------------------------------

st.set_page_config(
    page_title="Yeti Check",
    layout="wide"
)

# ----------------------------------
# STYLE
# ----------------------------------

st.markdown("""
<style>

.main-title{
    text-align:center;
    font-size:3.5rem;
    font-weight:700;
    margin-bottom:0;
}

.sub-title{
    text-align:center;
    color:#888;
    margin-bottom:2rem;
}

</style>
""", unsafe_allow_html=True)

# ----------------------------------
# HEADER
# ----------------------------------

st.markdown("""
<div class="main-title">Yeti Check</div>
<div class="sub-title">
Investigate links before interacting with them
</div>
""", unsafe_allow_html=True)

url = st.text_input(
    "URL",
    placeholder="https://example.com"
)

# ----------------------------------
# ANALYSE BUTTON
# ----------------------------------

if st.button("Analyse"):

    try:

        if not url:
            st.warning("Please enter a URL.")
            st.stop()

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # ----------------------------------
        # REQUEST
        # ----------------------------------

        response = requests.get(
            url,
            allow_redirects=True,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        redirects = [r.url for r in response.history]

        final_url = response.url

        parsed_url = urlparse(final_url)

        domain = parsed_url.netloc

        # ----------------------------------
        # WHOIS
        # ----------------------------------

        age = None
        registrar = "Unknown"

        try:

            domain_info = whois.whois(domain)

            registrar = getattr(
                domain_info,
                "registrar",
                "Unknown"
            )

            created = domain_info.creation_date

            if isinstance(created, list):
                created = created[0]

            if created:
                age = (
                    datetime.now() - created
                ).days

        except:
            pass

        # ----------------------------------
        # IP LOOKUP
        # ----------------------------------

        try:
            ip_address = socket.gethostbyname(domain)
        except:
            ip_address = "Unknown"

        # ----------------------------------
        # SCREENSHOT
        # ----------------------------------

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
                    page_title = page.title()
                except:
                    page_title = "Unknown"

                page.screenshot(
                    path=screenshot_file,
                    full_page=True
                )

                browser.close()

        # ----------------------------------
        # RISK ENGINE
        # ----------------------------------

        score = 0
        reasons = []

        suspicious_keywords = [
            "login",
            "signin",
            "password",
            "verify",
            "account",
            "security",
            "authentication",
            "invoice",
            "payment",
            "update"
        ]

        found_keywords = []

        test_string = (
            final_url.lower() +
            " " +
            page_title.lower()
        )

        for keyword in suspicious_keywords:

            if keyword in test_string:
                found_keywords.append(keyword)

        if len(redirects) >= 2:
            score += 20
            reasons.append("Multiple redirects detected")

        if age and age < 30:
            score += 40
            reasons.append("Recently registered domain")

        if "-" in domain:
            score += 10
            reasons.append("Hyphenated domain")

        if found_keywords:
            score += 15
            reasons.append("Suspicious keywords present")

        if score >= 60:
            verdict = "Potentially Suspicious"

        elif score >= 30:
            verdict = "Proceed With Caution"

        else:
            verdict = "Trusted"

        # ----------------------------------
        # METRICS
        # ----------------------------------

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

        # ----------------------------------
        # SCREENSHOT DISPLAY
        # ----------------------------------

        st.subheader("Website Screenshot")

        if os.path.exists(screenshot_file):
            st.image(
                screenshot_file,
                use_container_width=True
            )

        # ----------------------------------
        # KEY FINDINGS
        # ----------------------------------

        st.subheader("Key Findings")

        st.write(f"Final Destination: {final_url}")
        st.write(f"Domain: {domain}")
        st.write(f"IP Address: {ip_address}")
        st.write(f"Registrar: {registrar}")

        # ----------------------------------
        # PAGE INFORMATION
        # ----------------------------------

        st.subheader("Page Information")

        st.write("Title:", page_title)

        if found_keywords:

            st.warning(
                "Keywords found: "
                + ", ".join(found_keywords)
            )

        # ----------------------------------
        # VERDICT
        # ----------------------------------

        st.subheader("Analyst Verdict")

        verdict_text = f"""
Assessment: {verdict}

This site ultimately resolves to:

{final_url}

The page title identified was:

{page_title}

The risk score is based on
redirect activity,
domain age,
keyword analysis,
and URL characteristics.

Avoid entering passwords or personal
information unless the site has
been independently verified.
"""

        st.info(verdict_text)

        # ----------------------------------
        # EXPANDERS
        # ----------------------------------

        with st.expander("Redirect Chain"):

            if redirects:

                for item in redirects:
                    st.write(item)

            else:
                st.write(
                    "No redirects detected."
                )

        with st.expander("Domain Information"):

            st.write("Domain:", domain)
            st.write("Registrar:", registrar)
            st.write("IP Address:", ip_address)

            if age:
                st.write("Age:", age, "days")

        with st.expander("Risk Breakdown"):

            if reasons:

                for item in reasons:
                    st.write("•", item)

            else:

                st.write(
                    "No significant indicators detected."
                )

        # ----------------------------------
        # DOWNLOAD REPORT
        # ----------------------------------

        report = f"""
YETI CHECK REPORT

URL:
{url}

FINAL URL:
{final_url}

VERDICT:
{verdict}

RISK SCORE:
{score}/100

TITLE:
{page_title}

DOMAIN:
{domain}

REGISTRAR:
{registrar}

IP:
{ip_address}

KEYWORDS:
{', '.join(found_keywords)}
"""

        st.download_button(
            label="Download Report",
            data=report,
            file_name="yeticheck_report.txt",
            mime="text/plain"
        )

    except Exception as e:

        st.error(
            f"Analysis failed: {e}"
        )
