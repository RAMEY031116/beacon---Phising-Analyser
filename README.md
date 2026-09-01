# Yeti Check

**Yeti Check** is a Streamlit-based phishing investigation and website triage tool created by **bipzilla**.

It is designed to help investigate suspicious links, messages, QR codes, and email files without manually opening unknown websites in your normal browser.

Yeti Check combines URL analysis, redirect inspection, reputation services, domain intelligence, TLS certificate checks, browser-based page inspection, screenshots, phishing indicators, and downloadable PDF reports into one simple interface.

> **Important:** Yeti Check is an investigation aid. A **Low Risk** result does not prove that a website is genuine or safe.

---

## What Yeti Check does

Yeti Check can investigate:

- a single URL
- multiple URLs at once
- URLs pasted inside a full message or email
- QR codes containing URLs
- `.eml` email files
- redirected links
- login and credential pages
- suspicious or lookalike domains
- websites already reported by phishing or malware reputation services

The aim is to give an analyst one place to collect useful evidence before deciding whether a link should be trusted.

---

## Main features

### URL extraction

You can paste:

```text
https://example.com
```

multiple links:

```text
https://example.com
https://example.org
https://example.net
```

or an entire suspicious message:

```text
Your account has been suspended.

Verify your account here:
https://example-login.invalid/verify
```

Yeti automatically extracts the URLs it finds.

---

### Redirect analysis

Yeti follows HTTP redirects before analysing the final destination.

It records:

- original URL
- redirect chain
- final URL
- registered domains involved
- whether the redirect crossed into a different registered domain
- whether several different domains were involved

Changing domains during redirects can be useful supporting evidence during phishing investigations.

---

## Reputation checks

Yeti combines several external reputation sources.

### Google Web Risk

Yeti can use Google Web Risk to check URLs for:

- phishing / social engineering
- malware

The Google result contributes strongly to Yeti's overall risk score.

The main Yeti interface intentionally keeps provider-specific wording minimal so the analyst receives one overall Yeti verdict rather than several competing alerts.

Configure it using:

```toml
GOOGLE_WEB_RISK_API_KEY = "your-api-key"
```

---

### PhishTank

Yeti checks PhishTank for verified phishing reports.

An optional PhishTank application key can be configured with:

```toml
PHISHTANK_APP_KEY = "your-key"
```

Yeti can still attempt the lookup without an application key.

---

### OpenPhish

Yeti checks the OpenPhish community feed for exact URL matches.

The feed is cached temporarily to reduce repeated downloads and improve performance.

---

### urlscan.io history

Yeti can search existing **urlscan.io historical scans** for the website hostname.

It can use information such as:

- number of recent scans
- previous malicious verdicts
- most recent observation
- page title
- IP address
- country
- categories
- detected brands

Configure it using:

```toml
URLSCAN_API_KEY = "your-api-key"
```

### Privacy note for urlscan

Yeti currently **searches existing urlscan results only**.

It does **not automatically submit the URL being investigated for a new urlscan scan**.

This avoids accidentally publishing work URLs, tracking links, authentication tokens, or other sensitive information.

---

# Website and domain checks

## HTTP status

Yeti records the HTTP response and gives it a human-readable status such as:

- Working
- Access restricted
- Not found
- Rate limited
- Server error
- Redirect

A website blocking Yeti's automated browser is treated as a **neutral condition**, not proof of phishing.

---

## Domain age

Yeti performs an RDAP lookup and attempts to determine:

- registrar
- registration/creation date
- approximate domain age

Very new domains contribute supporting risk points because short-lived domains are commonly used in phishing campaigns.

A new domain alone does **not** mean a website is malicious.

---

## TLS / HTTPS checks

For HTTPS websites Yeti checks:

- whether the TLS certificate validates
- certificate issuer
- certificate expiry
- approximate days remaining

A valid certificate does not prove that a site is genuine, but invalid TLS can be useful supporting evidence.

---

## IP resolution

Yeti resolves the destination hostname and records the IP addresses associated with it.

Private and local addresses are rejected by Yeti's safety checks.

---

# Browser-based website inspection

Yeti uses **Playwright with Chromium** on the Streamlit server.

The suspicious website is therefore opened by the **server-side browser**, not by the user's normal desktop browser simply because the URL was pasted into Yeti.

The browser inspection can collect:

- page title
- Open Graph site name
- first page heading
- password fields
- email/username fields
- form destinations
- rendered website screenshot

---

## Full-page screenshots

Yeti captures a full-page screenshot rather than only the visible browser viewport.

Before capturing the screenshot Yeti scrolls through the page so that lazy-loaded images and sections have a chance to render.

If a website blocks automated access, Yeti attempts to capture the block or challenge page instead.

---

# Browser isolation and SSRF protection

Because Yeti intentionally visits untrusted websites, additional restrictions are applied to the Playwright browser.

The browser network guard checks **every browser request**, including:

- page navigation
- images
- scripts
- stylesheets
- iframes
- fetch/XHR requests

Requests to private or local destinations are blocked.

Examples include:

```text
127.0.0.1
localhost
10.0.0.0/8
172.16.0.0/12
192.168.0.0/16
link-local addresses
reserved addresses
```

Yeti also:

- rejects private/local IPs during normal HTTP redirect checks
- disables browser downloads
- blocks service workers
- clears browser permissions
- restricts non-HTTP/HTTPS browser protocols
- blocks WebSocket connections where supported by the installed Playwright version

### Important limitation

This provides an additional safety layer, but it is **not the same as running the browser inside a completely separate virtual machine or dedicated sandbox service**.

---

# Phishing and impersonation indicators

Yeti contains several local heuristics that are combined with reputation results.

## Lookalike domains

Yeti compares domain names against common brands such as:

- Microsoft
- Google
- Apple
- PayPal
- Amazon
- GitHub
- LinkedIn
- Dropbox
- Facebook
- Instagram
- Netflix
- DocuSign

It checks for:

- small spelling changes
- number-to-letter substitutions
- brand names inserted into unrelated domains
- similar-looking domains

Example:

```text
micros0ft-login.example
```

may be considered visually similar to Microsoft.

---

## Punycode

Domains using Punycode are highlighted because internationalised domain names can sometimes be used for visual impersonation.

Example:

```text
xn--example-...
```

Punycode itself is not malicious; it is treated as a supporting indicator.

---

## URL structure

Yeti can flag:

- URL shortening services
- unusually long URLs
- heavy URL encoding
- raw IP addresses instead of domain names
- username/password information embedded in the URL
- unusually deep subdomains

These are weak or supporting indicators rather than definitive phishing evidence.

---

# Login and form analysis

When the browser preview completes successfully, Yeti checks for:

- password fields
- email/username fields
- HTML forms
- form submission destinations

If a password form submits data to a different registered domain, Yeti considers that a strong warning sign.

Known authentication/payment services can be allowed so normal third-party authentication is not automatically treated as suspicious.

Examples include:

- Microsoft
- Google
- Okta
- Auth0
- Stripe
- PayPal

---

# Email analysis

Yeti supports uploaded `.eml` files.

It can extract:

- From address
- Reply-To address
- Subject
- URLs in plain-text email bodies
- links contained in HTML
- visible-link versus actual-link mismatches

It can also read authentication results already present in the email headers:

- SPF
- DKIM
- DMARC

This is useful for personal investigations or as supporting evidence.

If an organisation already has a secure email gateway that validates SPF, DKIM, and DMARC, Yeti does not need to replace that system.

---

## Visible link mismatch detection

For HTML email, Yeti can identify cases such as:

```text
Visible text:
https://microsoft.com

Actual link:
https://unrelated-example.invalid/login
```

This is highlighted because misleading visible URLs are a common phishing technique.

---

# QR code analysis

Yeti supports uploaded QR-code images.

It uses OpenCV to decode the QR code and extracts any URL that it contains.

The extracted URL is then analysed using the same Yeti investigation pipeline as a pasted URL.

This can be useful for investigating **QR phishing / quishing**.

---

# Yeti risk verdicts

Yeti combines its evidence into four main verdicts:

### Low Risk

No major warning signs were identified by the checks that completed.

This does **not** mean the website is guaranteed genuine.

### Caution

Some supporting warning signs were identified.

The website should be verified carefully before sensitive information is entered.

### Suspicious

Several significant warning signs were identified.

The link should be treated with caution and independently verified.

### High Risk

Strong evidence was identified, such as a confirmed unsafe reputation result or multiple serious phishing indicators.

---

# Risk scoring

Yeti uses weighted evidence.

Examples of stronger evidence include:

- confirmed unsafe URL reputation
- verified phishing database match
- credential forms posting to unrelated domains
- clear brand impersonation

Supporting evidence includes:

- very new domains
- domain-changing redirects
- lookalike domains
- Punycode
- unusual URL structure

The final score is capped at 100.

The risk score is intended to help prioritise evidence; it should not be treated as a mathematical guarantee.

---

# Parallel analysis and performance

After Yeti determines the final redirect destination, many independent checks run in parallel.

These include:

- Google Web Risk
- urlscan.io
- PhishTank
- OpenPhish
- RDAP
- TLS certificate inspection
- Playwright browser inspection

This reduces the total investigation time compared with running every network request sequentially.

Yeti also displays the elapsed analysis time.

The final time is still limited by the slowest service. A slow website, RDAP server, API, or full-page browser render may therefore increase the total duration.

---

# Yeti local history

Yeti keeps a local SQLite history of domains it has previously investigated.

Stored information includes:

- date/time checked
- registered domain
- sanitised original URL
- sanitised final URL
- verdict
- score
- HTTP status

Query strings and fragments are removed before URLs are stored locally to reduce the risk of preserving authentication tokens or tracking identifiers.

Yeti can report:

- how many times a domain has previously been checked
- first time checked
- last time checked
- previous verdict
- highest previous verdict
- highest previous score

### Streamlit Cloud limitation

Local SQLite files on Streamlit Community Cloud are not guaranteed to be permanent.

A restart, rebuild, or redeployment may remove local history.

For permanent organisation-wide history, use a persistent database such as PostgreSQL.

---

# PDF investigation reports

Every website result can be exported as a detailed PDF report.

The report contains:

- website/domain
- Yeti verdict
- risk score
- generated timestamp
- original URL
- final URL
- HTTP status
- analysis time
- website behaviour assessment
- phishing/social-engineering assessment
- malware reputation assessment
- credential-harvesting indicators
- brand impersonation indicators
- suspicious redirect indicators
- form destination analysis
- page title
- site name
- heading
- reputation results
- urlscan history
- redirect chain
- domain information
- IP addresses
- registrar
- domain age
- HTTPS validation
- certificate issuer
- certificate expiry
- local Yeti history
- investigation findings
- full website screenshot

Long website screenshots are split across multiple PDF pages instead of being compressed into one unreadable image.

Reports include:

```text
Yeti Check
by bipzilla
```

plus page numbers and report headers/footers.

---

# User interface

Yeti is designed to keep the main investigation view simple.

The primary result shows:

1. website/domain
2. Yeti risk verdict
3. screenshot
4. short explanation
5. domain age
6. HTTPS status
7. certificate status

Additional technical evidence is available inside expandable sections such as:

- Why this result?
- Website details
- Previous activity

---

# Light and dark appearance

Yeti includes its own appearance controls:

- System
- Light
- Dark

This avoids depending on Streamlit's toolbar appearance controls and keeps the interface consistent.

---

# Installation

## Python

A recent supported Python 3 version is recommended.

Clone the repository:

```bash
git clone YOUR_REPOSITORY_URL
cd YOUR_REPOSITORY
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Install Playwright Chromium:

```bash
playwright install chromium
```

Run Yeti:

```bash
streamlit run app.py
```

---

# Recommended `requirements.txt`

```text
streamlit
requests
playwright
tldextract
opencv-python-headless
numpy
reportlab
```

If clipboard QR functionality is enabled in your version, you may also need:

```text
streamlit-paste-button
```

---

# Streamlit Cloud deployment

For Streamlit Community Cloud:

1. Push the project to GitHub.
2. Create a new Streamlit app.
3. Select the repository and `app.py`.
4. Configure the required secrets.
5. Ensure Chromium/Playwright is available in the deployment environment.

Depending on your deployment configuration, you may need a setup script such as:

```bash
playwright install chromium
```

or install Chromium using the platform's package configuration.

---

# Secrets

API keys should **never** be placed directly inside `app.py`.

Store them in:

```text
.streamlit/secrets.toml
```

for local development, or in **Streamlit Cloud → App settings → Secrets**.

Example:

```toml
GOOGLE_WEB_RISK_API_KEY = "your-google-key"
URLSCAN_API_KEY = "your-urlscan-key"
PHISHTANK_APP_KEY = "optional-phishtank-key"
```

Never commit `secrets.toml` to a public repository.

A `.gitignore` entry is recommended:

```gitignore
.streamlit/secrets.toml
yeti_history.db
yeti_*.png
__pycache__/
*.pyc
```

---

# Privacy considerations

Yeti may send URL information to external reputation services.

Depending on which services are configured, this may include the complete URL.

URLs can sometimes contain:

- email addresses
- tracking IDs
- authentication tokens
- customer information
- internal identifiers

Consider this before analysing sensitive organisation-specific URLs.

Yeti already removes query strings from URLs stored in local history, but exact URL reputation services may still receive the complete URL during a live check.

urlscan is handled more conservatively: Yeti searches historical results and does not automatically submit new scans.

---

# What Yeti does not guarantee

Yeti cannot guarantee that a website is safe.

Possible situations include:

- a brand-new phishing site that is not yet in reputation databases
- a compromised legitimate website
- phishing pages shown only to certain countries/IP addresses
- websites that hide content from automated browsers
- time-limited malicious links
- legitimate newly registered domains
- false positives from reputation or heuristic systems

Always combine Yeti's result with analyst judgement and independent verification.

---

# Safe usage

Recommended behaviour:

- do not enter credentials into suspicious websites
- do not download files from investigated websites
- do not rely only on HTTPS
- independently verify unusual requests
- validate payment/account requests using a trusted communication channel
- consider unavailable checks as missing evidence, not evidence of safety

---

# Suggested architecture

```text
                       ┌────────────────────┐
                       │       User         │
                       └─────────┬──────────┘
                                 │
                                 ▼
                       ┌────────────────────┐
                       │   Yeti Check UI    │
                       │     Streamlit      │
                       └─────────┬──────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                    │
            ▼                    ▼                    ▼
   ┌────────────────┐   ┌────────────────┐   ┌─────────────────┐
   │ Reputation APIs│   │ Domain / TLS   │   │ Browser Worker  │
   │ Google         │   │ RDAP           │   │ Playwright      │
   │ PhishTank      │   │ DNS/IP         │   │ Chromium        │
   │ OpenPhish      │   │ Certificates   │   │ Full screenshot │
   │ urlscan history│   └────────────────┘   └────────┬────────┘
   └────────────────┘                                 │
                                                     ▼
                                           ┌─────────────────────┐
                                           │ Untrusted Website   │
                                           │ network restrictions│
                                           │ downloads disabled  │
                                           │ private IPs blocked │
                                           └─────────────────────┘
```

---

# Project purpose

Yeti Check was created as a practical phishing investigation tool rather than a replacement for:

- enterprise secure email gateways
- endpoint protection
- antivirus software
- browser isolation platforms
- professional threat-intelligence platforms
- SOC/SIEM systems

Its purpose is to bring useful phishing-analysis evidence together in a simple interface so suspicious links can be investigated more consistently.

---

# Future improvements

Potential future additions include:

- persistent PostgreSQL investigation history
- analyst case IDs
- analyst notes
- CSV/JSON report export
- per-service performance timings
- screenshot/result caching
- redirect-by-redirect reputation checks
- stronger Unicode/homoglyph detection
- ASN and hosting intelligence
- DNS and nameserver intelligence
- login/authentication for shared deployments
- configurable trusted-domain lists
- automated regression testing against known benign and malicious datasets

---

# Disclaimer

Yeti Check is provided for defensive security analysis and investigation.

It should not be treated as a definitive determination that a website is safe, legitimate, malicious, or fraudulent.

Use appropriate organisational security procedures and independent verification when dealing with sensitive information.

---

## Created by

**bipzilla**

Yeti Check
