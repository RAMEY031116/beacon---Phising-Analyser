import streamlit as st
import requests
import whois
import os
from urllib.parse import urlparse
from datetime import datetime
from playwright.sync_api import sync_playwright

st.set_page_config(
    page_title="Yeti Check",
    page_icon="🏔️",
    layout="wide"
)

st.title("🏔️ Yeti Check")
st.subheader("Check before you click")

url = st.text_input("Enter URL")

if st.button("Analyse"):

    if not url:
        st.warning("Please enter a URL")
        st.stop()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:

        st.header("🔍 Redirect Analysis")

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

        st.write("### Original URL")
        st.code(url)

        st.write("### Redirect Chain")

        if redirects:
            for item in redirects:
                st.write("➡️", item)
        else:
            st.write("No redirects detected.")

        st.write("### Final URL")
        st.success(final_url)

        st.header("📸 Website Screenshot")

        screenshot_file = "screenshot.png"

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

        st.write("Chromium found:", chromium_path)

        if chromium_path:

            with sync_playwright() as p:

                browser = p.chromium.launch(
                    executable_path=chromium_path,
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu"
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

                page.screenshot(
                    path=screenshot_file,
                    full_page=True
                )

                browser.close()

            st.image(
                screenshot_file,
                caption="Website Screenshot"
            )

        else:
            st.error(
                "Chromium browser not found on Streamlit server."
            )

        # DOMAIN INFO

        st.header("🌐 Domain Information")

        domain = urlparse(final_url).netloc

        st.write("**Domain:**", domain)

        age = None

        try:

            domain_info = whois.whois(domain)

            registrar = getattr(
                domain_info,
                "registrar",
                "Unknown"
            )

            st.write("**Registrar:**", registrar)

            created = domain_info.creation_date

            if isinstance(created, list):
                created = created[0]

            if created:

                age = (
                    datetime.now() - created
                ).days

                st.write(
                    "**Created:**",
                    created.date()
                )

                st.write(
                    "**Age:**",
                    f"{age} days"
                )

        except Exception:
            st.warning(
                "Could not retrieve WHOIS information."
            )

        # RISK SCORE

        st.header("⚠️ Risk Assessment")

        score = 0
        reasons = []

        if len(redirects) >= 2:
            score += 25
            reasons.append(
                "Multiple redirects detected"
            )

        if age and age < 30:
            score += 50
            reasons.append(
                "Domain less than 30 days old"
            )

        if "-" in domain:
            score += 10
            reasons.append(
                "Hyphenated domain detected"
            )

        if score >= 60:
            verdict = "🔴 High Risk"
        elif score >= 30:
            verdict = "🟡 Medium Risk"
        else:
            verdict = "🟢 Low Risk"

        st.metric(
            "Risk Score",
            f"{score}/100"
        )

        st.write(verdict)

        if reasons:
            st.write("### Reasons")

            for reason in reasons:
                st.write("•", reason)

        # SUMMARY

        st.header("🤖 Yeti Summary")

        summary = f"""
The URL redirected {len(redirects)} time(s)
before reaching:

{final_url}

Overall Risk Assessment:
{verdict}

This assessment is based on redirect
behaviour, domain information and
basic phishing indicators.
"""

        st.info(summary)

    except Exception as e:

        st.error(str(e))
