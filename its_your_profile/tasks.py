"""Background jobs, enqueued from BusinessProfile.on_update."""

import ipaddress
import mimetypes
import socket
from urllib.parse import urljoin, urlparse

import frappe
import requests
from bs4 import BeautifulSoup

from its_your_profile import ai

# Also written to logs/its_your_profile.log so failures can be read without opening the desk
logger = frappe.logger("its_your_profile", allow_site=True)

MAX_TEXT_CHARS = 20000
USER_AGENT = "Mozilla/5.0 (compatible; ItsYourProfileBot/1.0)"

CARD_FIELD_MAP = {
	"company_name": "company_name",
	"contact_person": "contact_person",
	"designation": "designation",
	"phone": "phone",
	"email": "email",
	"website": "website_url",
	"address_line": "address_line",
	"city": "city",
	"state": "state",
	"pincode": "pincode",
}


def scan_visiting_card(profile: str):
	doc = frappe.get_doc("Business Profile", profile)
	sides = [url for url in (doc.visiting_card, doc.visiting_card_back) if url]
	if not sides:
		return

	doc.db_set("card_scan_status", "Processing", commit=True)

	try:
		# Front first, so its values win; the optional back side only fills what's still blank
		results = []
		for file_url in sides:
			file = frappe.get_doc("File", {"file_url": file_url})
			mime_type = mimetypes.guess_type(file.file_name or file_url)[0] or "image/jpeg"
			results.append(ai.extract_card_details(file.get_content(), mime_type))

		# The AI call is slow; reload so edits saved meanwhile aren't overwritten (TimestampMismatchError)
		doc = frappe.get_doc("Business Profile", profile)

		# Only fill blanks, so anything the user already typed is kept
		for details in results:
			for key, fieldname in CARD_FIELD_MAP.items():
				value = getattr(details, key)
				if value and not doc.get(fieldname):
					doc.set(fieldname, value.strip())

		doc.card_scan_status = "Completed"
		doc.flags.from_scan = True
		doc.save(ignore_permissions=True)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(f"Visiting card scan failed for {profile}")
		logger.exception(f"Visiting card scan failed for {profile}")
		frappe.db.set_value("Business Profile", profile, "card_scan_status", "Failed")

	frappe.db.commit()


def scrape_website(profile: str):
	doc = frappe.get_doc("Business Profile", profile)
	if not doc.website_url:
		return

	try:
		home = fetch(doc.website_url)
		pages = [home]
		if contact_url := find_contact_page(home, doc.website_url):
			try:
				pages.append(fetch(contact_url))
			except Exception:
				pass  # the homepage alone is still useful

		soups = [BeautifulSoup(html, "html.parser") for html in pages]
		text = "\n\n".join(page_text(s) for s in soups)[:MAX_TEXT_CHARS]
		insights = ai.analyse_website(text)
		links = social_links(soups)

		# The AI call is slow; reload so edits saved meanwhile aren't overwritten (TimestampMismatchError)
		doc = frappe.get_doc("Business Profile", profile)
		doc.ai_summary = "<p>" + frappe.utils.escape_html(insights.ai_summary.strip()) + "</p>"
		if not doc.business_nature:
			doc.business_nature = insights.business_nature
		if not doc.established_year and insights.established_year:
			doc.established_year = insights.established_year
		# The AI only fills a platform the page's own <a> links didn't give us
		for platform, url in (("LinkedIn", insights.linkedin_url), ("Facebook", insights.facebook_url)):
			if url and not any(p == platform for p, _label, _url in links):
				links.append((platform, None, url))
		add_profile_links(doc, links)

		doc.save(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(f"Website scrape failed for {profile}")
		logger.exception(f"Website scrape failed for {profile}")


def fetch(url: str) -> str:
	ensure_public_url(url)
	response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20, allow_redirects=True)
	ensure_public_url(response.url)
	response.raise_for_status()
	return response.text


def ensure_public_url(url: str):
	"""Refuse URLs that point at the server's own network, since anyone can submit a website URL."""
	parsed = urlparse(url)
	if parsed.scheme not in ("http", "https") or not parsed.hostname:
		raise ValueError(f"Unsupported URL: {url}")

	for info in socket.getaddrinfo(parsed.hostname, parsed.port or 443):
		ip = ipaddress.ip_address(info[4][0])
		if not ip.is_global:
			raise ValueError(f"Refusing to fetch non-public address {ip} for {url}")


def find_contact_page(html: str, base_url: str) -> str | None:
	base_host = urlparse(base_url).hostname
	for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
		label = (a.get_text() + " " + a["href"]).lower()
		if "contact" in label:
			url = urljoin(base_url, a["href"])
			if urlparse(url).hostname == base_host:
				return url
	return None


def page_text(soup: BeautifulSoup) -> str:
	for tag in soup(["script", "style", "noscript", "svg"]):
		tag.decompose()
	return soup.get_text(" ", strip=True)


# (host suffix, path must contain, platform, label for "Other") — first match wins
LINK_RULES = (
	("linkedin.com", "", "LinkedIn", None),
	("facebook.com", "", "Facebook", None),
	("fb.com", "", "Facebook", None),
	("g.page", "", "Google Profile", None),
	("business.google.com", "", "Google Profile", None),
	("maps.app.goo.gl", "", "Google Profile", None),
	("goo.gl", "/maps", "Google Profile", None),
	("google.com", "/maps", "Google Profile", None),
	("bniconnectglobal.com", "", "BNI", None),
	("bni.com", "", "BNI", None),
	("bniindia.in", "", "BNI", None),
	("instagram.com", "", "Other", "Instagram"),
	("youtube.com", "", "Other", "YouTube"),
	("youtu.be", "", "Other", "YouTube"),
	("twitter.com", "", "Other", "X (Twitter)"),
	("x.com", "", "Other", "X (Twitter)"),
	("wa.me", "", "Other", "WhatsApp"),
	("indiamart.com", "", "Other", "IndiaMART"),
	("justdial.com", "", "Other", "Justdial"),
	("pinterest.com", "", "Other", "Pinterest"),
)

# "Share this page" buttons, not the company's own profile
SHARE_PATHS = ("/sharer", "/share", "/intent", "/shareArticle", "/dialog/")


def social_links(soups: list[BeautifulSoup]) -> list[tuple[str, str | None, str]]:
	"""Find the company's profile links on its pages, one per platform, as (platform, label, url)."""
	found, seen = [], set()
	for soup in soups:
		for a in soup.find_all("a", href=True):
			href = a["href"].strip()
			parsed = urlparse(href)
			host, path = (parsed.hostname or "").removeprefix("www."), parsed.path or ""
			if parsed.scheme not in ("http", "https") or any(s in path for s in SHARE_PATHS):
				continue
			for suffix, path_part, platform, label in LINK_RULES:
				if (host == suffix or host.endswith("." + suffix)) and path_part in path:
					key = (platform, label)
					if key not in seen:
						seen.add(key)
						found.append((platform, label, href))
					break
	return found


def add_profile_links(doc, links):
	"""Append links to the profile's table, skipping platforms (and URLs) it already has."""
	have = {(row.platform, row.label or None) for row in doc.profile_links}
	have_urls = {row.url.rstrip("/").lower() for row in doc.profile_links if row.url}
	for platform, label, url in links:
		if (platform, label) in have or url.rstrip("/").lower() in have_urls:
			continue
		doc.append("profile_links", {"platform": platform, "label": label, "url": url})
		have.add((platform, label))
