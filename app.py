import streamlit as st
import requests
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import whois
from datetime import datetime

st.set_page_config(
    page_title="LinkLens AI",
    layout="wide"
)

st.title("🔍 LinkLens AI")
st.write("Check where a link goes before clicking it")

url = st.text_input("Enter URL")

if st.button("Analyse URL"):

    if not url.startswith("http"):
        url = "https://" + url

    try:

        st.subheader("Redirect Analysis")

        response = requests.get(
            url,
            allow_redirects=True,
            timeout=10
        )

        redirects = []

        for r in response.history:
            redirects.append(r.url)

        final_url = response.url

        st.write("Original URL")
        st.code(url)

        st.write("Redirect Chain")

        for item in redirects:
            st.write("➡️", item)

        st.write("Final URL")
        st.success(final_url)

        # Screenshot
        st.subheader("Website Screenshot")

        screenshot_file = "screenshot.png"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            page = browser.new_page()

            page.goto(
                final_url,
                wait_until="networkidle",
                timeout=30000
            )

            page.screenshot(
                path=screenshot_file,
                full_page=True
            )

            browser.close()

        st.image(screenshot_file)

        # Whois
        st.subheader("Domain Information")

        domain = urlparse(final_url).netloc

        try:

            info = whois.whois(domain)

            st.write("Domain:", domain)
            st.write("Registrar:", info.registrar)

            if info.creation_date:

                created = info.creation_date

                if isinstance(created, list):
                    created = created[0]

                age = (datetime.now() - created).days

                st.write("Age:", age, "days")

        except:
            st.warning("Could not retrieve WHOIS information")

        # Risk assessment

        st.subheader("Risk Assessment")

        score = 0

        if len(redirects) > 2:
            score += 20

        try:
            if age < 30:
                score += 40
        except:
            pass

        if score >= 60:
            verdict = "🔴 High Risk"

        elif score >= 30:
            verdict = "🟡 Medium Risk"

        else:
            verdict = "🟢 Low Risk"

        st.metric(
            "Risk Score",
            score
        )

        st.write(verdict)

        st.subheader("Simple Analysis")

        summary = f"""
The URL redirected {len(redirects)} times before reaching its final destination.

Final destination:
{final_url}

Risk score:
{score}/100

This does not guarantee the website is safe or unsafe,
but provides an initial assessment.
"""

        st.info(summary)

    except Exception as e:

        st.error(str(e))
