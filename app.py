import os
import re
import ssl
import json
import time
import socket
import ipaddress
import tempfile
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse, urljoin

import requests
import streamlit as st
import tldextract
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ==========================================================
# CONFIG
# ==========================================================

st.set_page_config(
    page_title="Yeti Check",
    page_icon="🛡️",
    layout="wide",
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 YetiCheck/2.0"
)

REQUEST_TIMEOUT = 12
MAX_REDIRECTS = 8
MAX_RESPONSE_BYTES = 2_000_000

# Use tldextract's bundled public suffix snapshot so the app does not
# need to download the PSL at runtime.
TLD_EXTRACT = tldextract.TLDExtract(suffix_list_urls=None)

SUSPICIOUS_URL_WORDS = {
    "login", "signin", "sign-in", "password", "verify", "verification",
    "account", "security", "authentication", "invoice", "payment",
    "update", "unlock", "suspended", "confirm", "wallet", "recovery",
    "urgent", "secure", "billing", "identity", "webscr", "bonus",
}

URGENT_PAGE_PHRASES = {
    "account suspended", "verify your account", "confirm your identity",
    "unusual activity", "urgent action", "password expires",
    "payment failed", "account locked", "verify immediately",
}

BRANDS = {
    "microsoft": {
        "domains": {"microsoft.com", "microsoftonline.com", "live.com", "office.com", "outlook.com"},
        "aliases": {"microsoft", "office 365", "microsoft 365", "outlook", "onedrive"},
    },
    "google": {
        "domains": {"google.com", "gmail.com", "googleusercontent.com"},
        "aliases": {"google", "gmail", "google drive"},
    },
    "apple": {
        "domains": {"apple.com", "icloud.com"},
        "aliases": {"apple", "icloud", "apple id"},
    },
    "paypal": {
        "domains": {"paypal.com", "paypalobjects.com"},
        "aliases": {"paypal"},
    },
    "amazon": {
        "domains": {"amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.es", "amazon.it"},
        "aliases": {"amazon", "amazon prime"},
    },
    "github": {
        "domains": {"github.com", "githubusercontent.com"},
        "aliases": {"github"},
    },
    "dropbox": {
        "domains": {"dropbox.com", "dropboxusercontent.com"},
        "aliases": {"dropbox"},
    },
    "facebook": {
        "domains": {"facebook.com", "fb.com", "messenger.com"},
        "aliases": {"facebook", "messenger"},
    },
    "instagram": {
        "domains": {"instagram.com"},
        "aliases": {"instagram"},
    },
    "netflix": {
        "domains": {"netflix.com"},
        "aliases": {"netflix"},
    },
    "docusign": {
        "domains": {"docusign.com", "docusign.net"},
        "aliases": {"docusign"},
    },
    "linkedin": {
        "domains": {"linkedin.com", "licdn.com"},
        "aliases": {"linkedin"},
    },
}

# ==========================================================
# STYLE
# ==========================================================

st.markdown(
    """
<style>
.main-title {
    text-align:center;
    font-size:3.4rem;
    font-weight:800;
    margin-bottom:0;
}
.sub-title {
    text-align:center;
    color:#888;
    margin-bottom:1.2rem;
}
.verdict-card {
    border:1px solid rgba(128,128,128,.25);
    border-radius:16px;
    padding:1.1rem 1.2rem;
    margin:0.6rem 0 1.2rem 0;
}
.small-note { color:#888; font-size:.92rem; }
code { word-break: break-all; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">🛡️ Yeti Check</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Investigate suspicious links before interacting with them</div>',
    unsafe_allow_html=True,
)

# ==========================================================
# HELPERS: URL / DOMAIN / SSRF
# ==========================================================


def normalize_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("Please enter a URL.")

    if not value.lower().startswith(("http://", "https://")):
        value = "https://" + value

    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only http:// and https:// URLs are supported.")
    if not parsed.hostname:
        raise ValueError("The URL does not contain a valid hostname.")

    return value


def registered_domain(hostname: str) -> str:
    if not hostname:
        return ""
    ext = TLD_EXTRACT(hostname)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}".lower()
    return hostname.lower().strip(".")


def resolve_ips(hostname: str) -> list[str]:
    addresses = set()
    for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM):
        addresses.add(item[4][0])
    return sorted(addresses)


def ip_is_public(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_url(value: str) -> dict:
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS links are allowed.")

    host = parsed.hostname
    if not host:
        raise ValueError("Missing hostname.")

    lowered = host.lower().rstrip(".")
    if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith(".local"):
        raise ValueError("Local/private network addresses are blocked.")

    # Direct IP URL
    try:
        direct_ip = ipaddress.ip_address(lowered)
        if not ip_is_public(str(direct_ip)):
            raise ValueError("Private, local, reserved, or link-local IP addresses are blocked.")
        return {"hostname": lowered, "ips": [str(direct_ip)]}
    except ValueError as exc:
        if "blocked" in str(exc):
            raise
    except Exception:
        pass

    try:
        ips = resolve_ips(lowered)
    except socket.gaierror:
        raise ValueError("The hostname could not be resolved.")

    if not ips:
        raise ValueError("The hostname did not resolve to an IP address.")

    bad = [ip for ip in ips if not ip_is_public(ip)]
    if bad:
        raise ValueError(
            "This hostname resolves to a private/local/reserved address and was blocked: "
            + ", ".join(bad)
        )

    return {"hostname": lowered, "ips": ips}


def safe_fetch(start_url: str) -> dict:
    """Follow redirects manually and validate every destination before requesting it."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})

    current = start_url
    chain = []
    first_status = None
    response = None

    for hop in range(MAX_REDIRECTS + 1):
        validation = validate_public_url(current)

        try:
            response = session.get(
                current,
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
                stream=True,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Request failed: {exc}") from exc

        if first_status is None:
            first_status = response.status_code

        chain.append(
            {
                "url": current,
                "status": response.status_code,
                "hostname": validation["hostname"],
                "ips": validation["ips"],
            }
        )

        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            response.close()
            if not location:
                break
            next_url = urljoin(current, location)
            validate_public_url(next_url)
            current = next_url
            continue

        break
    else:
        raise RuntimeError("Too many redirects.")

    if response is None:
        raise RuntimeError("No response received.")

    # Read only a capped amount; we do not need to download huge files.
    body = b""
    content_type = response.headers.get("Content-Type", "")
    try:
        for chunk in response.iter_content(chunk_size=65_536):
            if not chunk:
                continue
            body += chunk
            if len(body) >= MAX_RESPONSE_BYTES:
                body = body[:MAX_RESPONSE_BYTES]
                break
    finally:
        response.close()

    return {
        "final_url": current,
        "redirect_chain": chain,
        "status_code": chain[-1]["status"],
        "initial_status_code": first_status,
        "content_type": content_type,
        "body": body,
        "headers": dict(response.headers),
    }


# ==========================================================
# HELPERS: RDAP / TLS / URL FEATURES
# ==========================================================


def parse_rdap_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def get_rdap(domain: str) -> dict:
    result = {
        "registrar": "Unknown",
        "created": None,
        "updated": None,
        "expires": None,
        "age_days": None,
        "nameservers": [],
        "error": None,
    }

    if not domain or "." not in domain:
        result["error"] = "RDAP is not available for this hostname."
        return result

    try:
        r = requests.get(
            f"https://rdap.org/domain/{domain}",
            headers={"User-Agent": USER_AGENT, "Accept": "application/rdap+json, application/json"},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        if r.status_code != 200:
            result["error"] = f"RDAP returned HTTP {r.status_code}."
            return result

        data = r.json()

        for event in data.get("events", []):
            action = (event.get("eventAction") or "").lower()
            dt = parse_rdap_date(event.get("eventDate"))
            if action == "registration":
                result["created"] = dt
            elif action in {"last changed", "last update of rdap database"}:
                result["updated"] = dt
            elif action == "expiration":
                result["expires"] = dt

        if result["created"]:
            now = datetime.now(timezone.utc)
            created = result["created"]
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            result["age_days"] = max(0, (now - created).days)

        result["nameservers"] = sorted(
            {
                (ns.get("ldhName") or "").lower()
                for ns in data.get("nameservers", [])
                if ns.get("ldhName")
            }
        )

        for entity in data.get("entities", []):
            roles = {str(x).lower() for x in entity.get("roles", [])}
            if "registrar" not in roles:
                continue
            vcard = entity.get("vcardArray")
            if isinstance(vcard, list) and len(vcard) == 2:
                for row in vcard[1]:
                    if len(row) >= 4 and row[0] == "fn":
                        result["registrar"] = str(row[3])
                        break
            if result["registrar"] != "Unknown":
                break

    except Exception as exc:
        result["error"] = str(exc)

    return result


def get_tls_info(hostname: str, port: int = 443) -> dict:
    info = {
        "enabled": False,
        "valid": False,
        "issuer": "Unknown",
        "subject": "Unknown",
        "not_before": None,
        "not_after": None,
        "days_remaining": None,
        "error": None,
    }

    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=8) as raw:
            with context.wrap_socket(raw, server_hostname=hostname) as sock:
                cert = sock.getpeercert()
                info["enabled"] = True
                info["valid"] = True

                issuer_parts = dict(x[0] for x in cert.get("issuer", []))
                subject_parts = dict(x[0] for x in cert.get("subject", []))
                info["issuer"] = issuer_parts.get("organizationName") or issuer_parts.get("commonName") or "Unknown"
                info["subject"] = subject_parts.get("commonName") or "Unknown"

                fmt = "%b %d %H:%M:%S %Y %Z"
                if cert.get("notBefore"):
                    info["not_before"] = datetime.strptime(cert["notBefore"], fmt).replace(tzinfo=timezone.utc)
                if cert.get("notAfter"):
                    info["not_after"] = datetime.strptime(cert["notAfter"], fmt).replace(tzinfo=timezone.utc)
                    info["days_remaining"] = (info["not_after"] - datetime.now(timezone.utc)).days
    except Exception as exc:
        info["error"] = str(exc)

    return info


def count_subdomains(hostname: str) -> int:
    ext = TLD_EXTRACT(hostname)
    if not ext.subdomain:
        return 0
    return len([x for x in ext.subdomain.split(".") if x])


def looks_like_ip_hostname(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
        return True
    except Exception:
        return False


def url_features(value: str) -> dict:
    p = urlparse(value)
    hostname = (p.hostname or "").lower()
    reg = registered_domain(hostname)
    raw = value.lower()

    encoded_count = len(re.findall(r"%[0-9a-f]{2}", raw))
    suspicious_words = sorted({word for word in SUSPICIOUS_URL_WORDS if word in raw})

    return {
        "hostname": hostname,
        "registered_domain": reg,
        "https": p.scheme.lower() == "https",
        "has_punycode": "xn--" in hostname,
        "has_unicode_hostname": any(ord(ch) > 127 for ch in hostname),
        "has_at_symbol": "@" in p.netloc,
        "is_ip_url": looks_like_ip_hostname(hostname),
        "subdomain_count": count_subdomains(hostname),
        "url_length": len(value),
        "hyphen_count": hostname.count("-"),
        "encoded_count": encoded_count,
        "suspicious_words": suspicious_words,
        "nonstandard_port": p.port not in {None, 80, 443},
    }


# ==========================================================
# HELPERS: BRAND / PAGE ANALYSIS
# ==========================================================


COMMON_HOMOGLYPHS = str.maketrans({
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t",
    "@": "a", "$": "s",
})


def simplify_for_similarity(text: str) -> str:
    text = text.lower().translate(COMMON_HOMOGLYPHS)
    return re.sub(r"[^a-z0-9]", "", text)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, simplify_for_similarity(a), simplify_for_similarity(b)).ratio()


def detect_brand(hostname: str, page_title: str = "", page_text: str = "") -> dict:
    reg = registered_domain(hostname)
    ext = TLD_EXTRACT(hostname)
    domain_label = ext.domain.lower() if ext.domain else hostname.lower()
    haystack = f"{hostname} {page_title} {page_text[:12000]}".lower()

    detected = []

    for brand, meta in BRANDS.items():
        official = reg in meta["domains"]
        alias_hits = [alias for alias in meta["aliases"] if alias in haystack]

        # Typosquatting similarity is useful only if this is not already an official domain.
        typo_score = similarity(domain_label, brand)
        typo_like = (not official) and typo_score >= 0.72 and domain_label != brand

        if alias_hits or typo_like:
            detected.append(
                {
                    "brand": brand,
                    "official": official,
                    "official_domains": sorted(meta["domains"]),
                    "alias_hits": sorted(alias_hits),
                    "similarity": round(typo_score, 2),
                    "typo_like": typo_like,
                }
            )

    detected.sort(key=lambda x: (x["official"], len(x["alias_hits"]), x["similarity"]), reverse=True)
    primary = detected[0] if detected else None

    return {"detected": detected, "primary": primary}


def safe_route_handler(route):
    """Best-effort block of browser requests to private/local network destinations."""
    request_url = route.request.url
    parsed = urlparse(request_url)

    # Let browser-internal URLs pass.
    if parsed.scheme in {"data", "blob", "about", "chrome", "file"}:
        route.continue_()
        return

    try:
        if parsed.scheme not in {"http", "https"}:
            route.abort()
            return
        validate_public_url(request_url)
        route.continue_()
    except Exception:
        route.abort()


def find_chromium_path():
    candidates = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def deep_page_analysis(final_url: str) -> dict:
    result = {
        "browser_available": False,
        "title": "Unknown",
        "text": "",
        "screenshot": None,
        "password_fields": 0,
        "email_fields": 0,
        "otp_fields": 0,
        "forms": [],
        "external_form_actions": [],
        "urgent_phrases": [],
        "links_count": 0,
        "error": None,
    }

    chromium_path = find_chromium_path()

    validate_public_url(final_url)

    screenshot_path = os.path.join(tempfile.gettempdir(), f"yeticheck_{int(time.time() * 1000)}.png")

    try:
        with sync_playwright() as p:
            launch_kwargs = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-background-networking",
                ],
            }
            if chromium_path:
                launch_kwargs["executable_path"] = chromium_path

            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                viewport={"width": 1366, "height": 850},
                user_agent=USER_AGENT,
                ignore_https_errors=False,
            )
            page = context.new_page()
            page.route("**/*", safe_route_handler)

            page.goto(final_url, wait_until="domcontentloaded", timeout=25_000)
            page.wait_for_timeout(1200)

            result["browser_available"] = True
            try:
                result["title"] = page.title() or "Unknown"
            except Exception:
                pass

            try:
                body_text = page.locator("body").inner_text(timeout=3000)
                result["text"] = body_text[:50_000]
            except Exception:
                result["text"] = ""

            result["password_fields"] = page.locator('input[type="password"]').count()
            result["email_fields"] = page.locator(
                'input[type="email"], input[name*="email" i], input[autocomplete="email"]'
            ).count()
            result["otp_fields"] = page.locator(
                'input[autocomplete="one-time-code"], input[name*="otp" i], input[name*="code" i]'
            ).count()
            result["links_count"] = page.locator("a[href]").count()

            page_domain = registered_domain(urlparse(final_url).hostname or "")
            forms = page.locator("form")
            form_count = min(forms.count(), 30)

            for idx in range(form_count):
                form = forms.nth(idx)
                action = form.get_attribute("action") or ""
                method = (form.get_attribute("method") or "GET").upper()
                resolved_action = urljoin(final_url, action) if action else final_url
                action_host = urlparse(resolved_action).hostname or ""
                action_domain = registered_domain(action_host)
                external = bool(action_domain and page_domain and action_domain != page_domain)
                item = {
                    "method": method,
                    "action": resolved_action,
                    "external": external,
                    "action_domain": action_domain,
                }
                result["forms"].append(item)
                if external:
                    result["external_form_actions"].append(item)

            lower_text = result["text"].lower()
            result["urgent_phrases"] = sorted(
                phrase for phrase in URGENT_PAGE_PHRASES if phrase in lower_text
            )

            page.screenshot(path=screenshot_path, full_page=False)
            result["screenshot"] = screenshot_path

            context.close()
            browser.close()

    except PlaywrightTimeoutError:
        result["error"] = "The page took too long to render in Deep Check."
    except Exception as exc:
        result["error"] = str(exc)

    return result


# ==========================================================
# RISK ENGINE
# ==========================================================


def add_risk(items, points, title, detail, severity="medium"):
    items.append({"points": points, "title": title, "detail": detail, "severity": severity})


def calculate_risk(
    original_url: str,
    final_url: str,
    redirect_chain: list,
    features: dict,
    rdap: dict,
    tls: dict,
    page: dict | None,
    brand: dict,
) -> dict:
    risks = []
    positives = []

    original_domain = registered_domain(urlparse(original_url).hostname or "")
    final_domain = features["registered_domain"]

    # Strong indicators
    primary_brand = brand.get("primary")
    if primary_brand and not primary_brand["official"]:
        if primary_brand["typo_like"]:
            add_risk(
                risks, 35,
                "Possible brand lookalike / typosquatting",
                f"The domain resembles {primary_brand['brand'].title()} but is not one of its known official domains.",
                "high",
            )
        elif primary_brand["alias_hits"]:
            add_risk(
                risks, 30,
                "Brand/domain mismatch",
                f"The page or URL references {primary_brand['brand'].title()}, but the registered domain is {final_domain}.",
                "high",
            )

    if page:
        if page["password_fields"] > 0:
            add_risk(
                risks, 15,
                "Password field detected",
                f"The page contains {page['password_fields']} password field(s). Only enter credentials after independently verifying the domain.",
                "high",
            )
        if page["external_form_actions"]:
            destinations = sorted({x["action_domain"] for x in page["external_form_actions"] if x["action_domain"]})
            add_risk(
                risks, 30,
                "Form submits to another registered domain",
                "One or more forms send data to: " + ", ".join(destinations),
                "high",
            )
        if page["urgent_phrases"]:
            add_risk(
                risks, 10,
                "Urgency / account-pressure language",
                "Detected: " + ", ".join(page["urgent_phrases"]),
                "medium",
            )

    # Domain age
    age = rdap.get("age_days")
    if age is not None:
        if age < 7:
            add_risk(risks, 25, "Very recently registered domain", f"The domain is approximately {age} day(s) old.", "high")
        elif age < 30:
            add_risk(risks, 18, "Recently registered domain", f"The domain is approximately {age} days old.", "medium")
        elif age < 180:
            add_risk(risks, 8, "Relatively new domain", f"The domain is approximately {age} days old.", "low")
        else:
            positives.append(f"Domain has existed for approximately {age} days.")

    # Redirect intelligence
    redirect_count = max(0, len(redirect_chain) - 1)
    domains_in_chain = [registered_domain(item["hostname"]) for item in redirect_chain]
    domain_changes = sum(1 for a, b in zip(domains_in_chain, domains_in_chain[1:]) if a and b and a != b)

    if domain_changes >= 2:
        add_risk(risks, 18, "Multiple cross-domain redirects", f"The redirect chain changed registered domain {domain_changes} times.", "medium")
    elif domain_changes == 1:
        add_risk(risks, 7, "Cross-domain redirect", "The link redirects to a different registered domain.", "low")
    elif redirect_count:
        positives.append("Redirects stayed within the same registered domain.")

    if original_domain and final_domain and original_domain != final_domain:
        add_risk(
            risks, 8,
            "Final domain differs from the entered domain",
            f"Entered: {original_domain} → Final: {final_domain}",
            "medium",
        )

    # URL structure
    if features["has_punycode"]:
        add_risk(risks, 20, "Punycode hostname", "The hostname contains xn-- encoding. This can be legitimate, but is also used in lookalike attacks.", "high")
    if features["has_unicode_hostname"]:
        add_risk(risks, 18, "Unicode characters in hostname", "Internationalised domains can be legitimate, but visually similar Unicode characters are also used in lookalike attacks.", "high")
    if features["has_at_symbol"]:
        add_risk(risks, 20, "@ symbol in URL authority", "This can make a URL visually misleading about its actual destination.", "high")
    if features["is_ip_url"]:
        add_risk(risks, 15, "Direct IP-address URL", "The link uses an IP address instead of a normal domain name.", "medium")
    if features["subdomain_count"] >= 4:
        add_risk(risks, 10, "Many subdomains", f"The hostname contains {features['subdomain_count']} subdomain levels.", "low")
    if features["url_length"] > 180:
        add_risk(risks, 7, "Very long URL", f"The URL is {features['url_length']} characters long.", "low")
    if features["encoded_count"] >= 5:
        add_risk(risks, 8, "Heavy URL encoding", f"The URL contains {features['encoded_count']} percent-encoded sequences.", "low")
    if features["hyphen_count"] >= 3:
        add_risk(risks, 6, "Heavily hyphenated hostname", f"The hostname contains {features['hyphen_count']} hyphens.", "low")
    if features["nonstandard_port"]:
        add_risk(risks, 8, "Non-standard web port", "The URL uses a port other than 80 or 443.", "medium")

    if features["suspicious_words"]:
        add_risk(
            risks, 5,
            "Security/login wording in URL",
            "Detected URL terms: " + ", ".join(features["suspicious_words"]),
            "low",
        )

    # HTTPS/TLS
    if not features["https"]:
        add_risk(risks, 15, "Connection is not HTTPS", "Credentials or sensitive data should not be entered over plain HTTP.", "high")
    elif not tls.get("valid"):
        add_risk(risks, 18, "TLS certificate could not be validated", tls.get("error") or "Certificate validation failed.", "high")
    else:
        positives.append("TLS certificate validated for the hostname.")

    raw_score = sum(x["points"] for x in risks)
    score = min(100, raw_score)

    # Confidence describes completeness, not safety.
    completeness = 0
    completeness += 25 if final_domain else 0
    completeness += 20 if rdap.get("age_days") is not None else 0
    completeness += 20 if tls.get("enabled") else 0
    completeness += 15 if redirect_chain else 0
    completeness += 20 if page and page.get("browser_available") else 0

    if completeness >= 85:
        confidence = "High"
    elif completeness >= 60:
        confidence = "Medium"
    else:
        confidence = "Limited"

    if score >= 75:
        verdict = "High phishing risk"
        icon = "🔴"
        action = "Do not sign in, pay, or enter personal information through this link. Use the organisation's official app or type its known website address yourself."
    elif score >= 45:
        verdict = "Suspicious — verify independently"
        icon = "🟠"
        action = "Do not enter credentials yet. Verify the organisation and domain through an independent source before proceeding."
    elif score >= 20:
        verdict = "Some caution indicators"
        icon = "🟡"
        action = "No decisive phishing evidence was found, but some indicators deserve checking. Verify the domain before entering sensitive information."
    else:
        verdict = "No major phishing indicators detected"
        icon = "🟢"
        action = "No major indicators were detected by these checks. This is not a guarantee that the site is genuine; verify sensitive requests independently."

    return {
        "score": score,
        "raw_score": raw_score,
        "verdict": verdict,
        "icon": icon,
        "action": action,
        "confidence": confidence,
        "completeness": completeness,
        "risks": sorted(risks, key=lambda x: x["points"], reverse=True),
        "positives": positives,
        "domain_changes": domain_changes,
    }


# ==========================================================
# UI INPUTS
# ==========================================================

with st.container(border=True):
    url_input = st.text_input(
        "URL to investigate",
        placeholder="https://example.com/login",
        help="Paste the exact link you received. Yeti Check will not submit forms or enter credentials.",
    )

    left, right = st.columns([1, 2])
    with left:
        scan_mode = st.radio(
            "Scan mode",
            ["Quick Check", "Deep Check"],
            horizontal=True,
            help="Deep Check opens the final page in a headless browser, takes a screenshot, and inspects forms/credential fields.",
        )
    with right:
        st.caption(
            "Quick Check: URL + DNS + redirects + domain + RDAP + TLS + brand checks.  "
            "Deep Check: also renders the page and inspects login/forms."
        )

    analyse_clicked = st.button("🔎 Analyse link", type="primary", use_container_width=True)

st.caption(
    "Yeti Check is a phishing-analysis aid, not a guarantee of safety and not an antivirus scanner. "
    "Do not paste internal/private company URLs into a public deployment."
)

# ==========================================================
# MAIN ANALYSIS
# ==========================================================

if analyse_clicked:
    try:
        normalized = normalize_url(url_input)

        with st.status("Running Yeti Check…", expanded=True) as status:
            st.write("1/6 Validating destination and blocking private/local network targets…")
            validate_public_url(normalized)

            st.write("2/6 Following redirects safely…")
            fetch = safe_fetch(normalized)
            final_url = fetch["final_url"]
            final_parsed = urlparse(final_url)
            hostname = (final_parsed.hostname or "").lower()
            reg_domain = registered_domain(hostname)
            features = url_features(final_url)

            # Extract a lightweight title from the fetched HTML for Quick Check.
            quick_title = ""
            if "html" in (fetch.get("content_type") or "").lower() and fetch.get("body"):
                try:
                    html_sample = fetch["body"].decode("utf-8", errors="ignore")
                    match = re.search(r"<title[^>]*>(.*?)</title>", html_sample, re.I | re.S)
                    if match:
                        quick_title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(1))).strip()[:300]
                except Exception:
                    quick_title = ""

            st.write("3/6 Checking domain registration data (RDAP)…")
            rdap = get_rdap(reg_domain)

            st.write("4/6 Checking HTTPS/TLS certificate…")
            tls = get_tls_info(hostname, final_parsed.port or 443) if final_parsed.scheme == "https" else {
                "enabled": False,
                "valid": False,
                "issuer": "Not applicable",
                "subject": "Not applicable",
                "not_before": None,
                "not_after": None,
                "days_remaining": None,
                "error": "URL is not HTTPS.",
            }

            page = None
            if scan_mode == "Deep Check":
                st.write("5/6 Rendering the page safely and inspecting forms…")
                page = deep_page_analysis(final_url)
            else:
                st.write("5/6 Skipping browser rendering (Quick Check selected)…")

            st.write("6/6 Comparing identity signals and calculating risk…")
            page_title = page.get("title", "") if page else quick_title
            page_text = page.get("text", "") if page else ""
            brand = detect_brand(hostname, page_title, page_text)

            risk = calculate_risk(
                original_url=normalized,
                final_url=final_url,
                redirect_chain=fetch["redirect_chain"],
                features=features,
                rdap=rdap,
                tls=tls,
                page=page,
                brand=brand,
            )

            status.update(label="Analysis complete", state="complete", expanded=False)

        # ==================================================
        # RESULT SUMMARY
        # ==================================================

        st.divider()
        st.markdown(
            f"""
<div class="verdict-card">
    <h2 style="margin-top:0">{risk['icon']} {risk['verdict']}</h2>
    <p><strong>Yeti risk score:</strong> {risk['score']}/100 &nbsp; • &nbsp; <strong>Analysis confidence:</strong> {risk['confidence']}</p>
    <p>{risk['action']}</p>
</div>
""",
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Risk", f"{risk['score']}/100")
        c2.metric("Final domain", reg_domain or "Unknown")
        c3.metric("Redirects", max(0, len(fetch["redirect_chain"]) - 1))
        c4.metric("HTTPS", "Yes" if features["https"] else "No")
        c5.metric("Domain age", f"{rdap['age_days']} days" if rdap.get("age_days") is not None else "Unknown")

        # Identity check
        st.subheader("🏢 Identity check")
        primary = brand.get("primary")
        if primary:
            a, b, c = st.columns(3)
            a.write(f"**Possible brand:** {primary['brand'].title()}")
            b.write(f"**Actual registered domain:** `{reg_domain}`")
            b_ok = primary["official"]
            c.write(f"**Official domain match:** {'✅ Yes' if b_ok else '❌ No'}")

            if not b_ok:
                st.error(
                    f"This page appears related to **{primary['brand'].title()}**, but `{reg_domain}` is not in Yeti Check's known official-domain list for that brand."
                )
                st.caption("Known official domains in this local list: " + ", ".join(primary["official_domains"]))
            else:
                st.success("The registered domain matches Yeti Check's local official-domain list for the detected brand.")
        else:
            st.info("No supported major brand was confidently identified from the URL/page signals.")

        # Reasons
        st.subheader("🔍 Why Yeti reached this result")
        if risk["risks"]:
            for item in risk["risks"]:
                icon = "🔴" if item["severity"] == "high" else "🟠" if item["severity"] == "medium" else "🟡"
                st.markdown(f"{icon} **{item['title']}**  \n{item['detail']}  \n`+{item['points']} risk points`")
        else:
            st.success("No significant phishing indicators were detected by the checks that completed.")

        if risk["positives"]:
            with st.expander("✅ Reassuring signals"):
                for item in risk["positives"]:
                    st.write("•", item)

        # Deep-check details
        if page:
            st.subheader("🧪 Deep page analysis")
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Password fields", page["password_fields"])
            p2.metric("Email fields", page["email_fields"])
            p3.metric("OTP/code fields", page["otp_fields"])
            p4.metric("Forms", len(page["forms"]))

            if page.get("error"):
                st.warning("Deep Check note: " + page["error"])

            if page.get("screenshot") and os.path.exists(page["screenshot"]):
                st.subheader("📸 Website screenshot")
                st.image(page["screenshot"], use_container_width=True)

            with st.expander("Page and form details"):
                st.write("**Page title:**", page.get("title") or "Unknown")
                if page["forms"]:
                    for idx, form in enumerate(page["forms"], start=1):
                        marker = "⚠️ External domain" if form["external"] else "Same registered domain"
                        st.write(f"**Form {idx}:** {form['method']} → `{form['action']}` — {marker}")
                else:
                    st.write("No HTML forms detected.")

        # Technical details
        with st.expander("🌐 Redirect chain"):
            for idx, hop in enumerate(fetch["redirect_chain"], start=1):
                st.write(
                    f"**{idx}. HTTP {hop['status']}** — `{hop['url']}`  \n"
                    f"Host: `{hop['hostname']}` • IP(s): {', '.join(hop['ips'])}"
                )

        with st.expander("📋 Domain / RDAP information"):
            st.write("**Hostname:**", hostname)
            st.write("**Registered domain:**", reg_domain)
            st.write("**Registrar:**", rdap.get("registrar") or "Unknown")
            st.write("**Created:**", rdap["created"].isoformat() if rdap.get("created") else "Unknown")
            st.write("**Updated:**", rdap["updated"].isoformat() if rdap.get("updated") else "Unknown")
            st.write("**Expires:**", rdap["expires"].isoformat() if rdap.get("expires") else "Unknown")
            st.write("**Nameservers:**", ", ".join(rdap.get("nameservers", [])) or "Unknown")
            if rdap.get("error"):
                st.caption("RDAP note: " + rdap["error"])

        with st.expander("🔐 TLS certificate"):
            st.write("**TLS enabled:**", "Yes" if tls.get("enabled") else "No")
            st.write("**Certificate validated:**", "Yes" if tls.get("valid") else "No")
            st.write("**Issuer:**", tls.get("issuer") or "Unknown")
            st.write("**Certificate subject:**", tls.get("subject") or "Unknown")
            st.write("**Valid from:**", tls["not_before"].isoformat() if tls.get("not_before") else "Unknown")
            st.write("**Valid until:**", tls["not_after"].isoformat() if tls.get("not_after") else "Unknown")
            st.write("**Days remaining:**", tls.get("days_remaining") if tls.get("days_remaining") is not None else "Unknown")
            st.caption("HTTPS protects the connection. It does not prove that the website belongs to the organisation it claims to represent.")

        with st.expander("🧬 URL structure"):
            st.json(features)

        # Report
        report_data = {
            "tool": "Yeti Check 2.0",
            "scan_mode": scan_mode,
            "entered_url": normalized,
            "final_url": final_url,
            "hostname": hostname,
            "registered_domain": reg_domain,
            "status_code": fetch["status_code"],
            "risk_score": risk["score"],
            "verdict": risk["verdict"],
            "confidence": risk["confidence"],
            "recommended_action": risk["action"],
            "detected_brand": primary["brand"] if primary else None,
            "official_brand_domain_match": primary["official"] if primary else None,
            "risk_reasons": risk["risks"],
            "url_features": features,
            "rdap": {
                "registrar": rdap.get("registrar"),
                "age_days": rdap.get("age_days"),
                "created": rdap["created"].isoformat() if rdap.get("created") else None,
                "expires": rdap["expires"].isoformat() if rdap.get("expires") else None,
                "nameservers": rdap.get("nameservers"),
            },
            "tls": {
                "enabled": tls.get("enabled"),
                "valid": tls.get("valid"),
                "issuer": tls.get("issuer"),
                "subject": tls.get("subject"),
                "days_remaining": tls.get("days_remaining"),
            },
            "redirect_chain": fetch["redirect_chain"],
            "deep_check": {
                "title": page.get("title") if page else None,
                "password_fields": page.get("password_fields") if page else None,
                "email_fields": page.get("email_fields") if page else None,
                "otp_fields": page.get("otp_fields") if page else None,
                "forms": page.get("forms") if page else None,
            },
            "warning": "No phishing-analysis tool can guarantee that a website is genuine. Verify sensitive requests independently.",
        }

        report_text = json.dumps(report_data, indent=2, default=str)
        st.download_button(
            "⬇️ Download full Yeti Check report",
            data=report_text,
            file_name="yeticheck_report.json",
            mime="application/json",
            use_container_width=True,
        )

    except Exception as exc:
        st.error(f"Analysis failed: {exc}")
        st.caption(
            "Yeti Check blocks localhost, private IP ranges, link-local addresses, and other unsafe server-side destinations. "
            "A blocked analysis can therefore be an intentional safety control rather than an app failure."
        )
