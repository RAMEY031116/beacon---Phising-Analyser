import streamlit as st
import requests
import whois
import os
from urllib.parse import urlparse
from datetime import datetime
from playwright.sync_api import sync_playwright

st.set_page_config(
    page_title="Yeti Check",
    layout="wide"
)

st.markdown("""
<style>

.main-title {
    text-align: center;
    font-size: 3rem;
    font-weight: 700;
    margin-bottom: 0px;
}

.sub-title {
    text-align: center;
    color: #888;
    margin-bottom: 30px;
}

.block-container {
    padding-top: 2rem;
}

</style>
""", unsafe_allow_html=True)

st.markdown(
    """
<div class="main-title">Yeti Check</div>
<div class="sub-title">
Investigate links safely before opening them
</div>
""",
    unsafe_allow_html=True
)

url = st.text_input(
    "Enter URL",
    placeholder="https://example.com"
)

if st.button("Analyse"):

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
                "Recently registered domain"
            )

        if "-" in domain:
            score += 10
            reasons.append(
                "Hyphenated domain detected"
            )

        if "login" in final_url.lower():
            score += 10
            reasons.append(
                "Login related URL detected"
            )

        if score >= 60:
            verdict = "Potentially Suspicious"

        elif score >= 30:
            verdict = "Proceed With Caution"

        else:
            verdict = "Trusted"

        secure_connection = (
            "Yes"
            if final_url.startswith("https://")
            else "No"
        )

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
                secure_connection
            )

        with col4:
            if age:
                st.metric(
                    "Domain Age",
                    f"{age} Days"
                )
            else:
                st.metric(
                    "Domain Age",
                    "Unknown"
                )

        st.divider()

        st.subheader("Website Screenshot")

        screenshot_file = "screenshot.png"
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

                page_title = page.title()

                page.screenshot(
                    path=screenshot_file,
                    full_page=True
                )

                browser.close()

            st.image(
                screenshot_file,
                use_container_width=True
            )

        else:
            st.error(
                "Chromium not found on server."
            )

        st.subheader("Key Findings")

        findings = []

        findings.append(
            f"Final destination is {domain}"
        )

        findings.append(
            f"{len(redirects)} redirect(s) detected"
        )

        findings.append(
            f"Connection secured with HTTPS: {secure_connection}"
        )

        if age:
            findings.append(
                f"Domain registered approximately {age} days ago"
            )

        for item in findings:
            st.write("•", item)

        st.subheader("Page Information")

        st.write(
            "**Title:**",
            page_title
        )

        favicon = (
            f"https://www.google.com/s2/favicons"
            f"?domain={domain}&sz=128"
        )

        st.image(
            favicon,
            width=40
        )

        st.subheader("Analysis Summary")

        st.info(
            f"""
Final destination:

{final_url}

Assessment:

{verdict}

This assessment is based on the redirect chain, domain age, URL structure and other basic indicators. Results should be used as guidance only.
"""
        )

        with st.expander(
            "View Redirect Chain"
        ):

            if redirects:

                for item in redirects:
                    st.write(item)

            else:
                st.write(
                    "No redirects detected."
                )

        with st.expander(
            "View Domain Information"
        ):

            st.write(
                "Domain:",
                domain
            )

            st.write(
                "Registrar:",
                registrar
            )

            st.write(
                "HTTPS:",
                secure_connection
            )

            st.write(
                "Host:",
                parsed.netloc
            )

            st.write(
                "Path:",
                parsed.path if parsed.path else "/"
            )

            if age:
                st.write(
                    "Age:",
                    f"{age} days"
                )

        with st.expander(
            "View Risk Details"
        ):

            if reasons:

                for reason in reasons:
                    st.write(
                        "•",
                        reason
                    )

            else:

                st.write(
                    "No significant risk indicators detected."
                )

    except Exception as e:

        st.error(
            f"Analysis failed: {e}"
        )
