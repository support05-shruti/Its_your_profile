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
	if not doc.visiting_card:
		return

	doc.db_set("card_scan_status", "Processing", commit=True)

	try:
		file = frappe.get_doc("File", {"file_url": doc.visiting_card})
		mime_type = mimetypes.guess_type(file.file_name or doc.visiting_card)[0] or "image/jpeg"
		details = ai.extract_card_details(file.get_content(), mime_type)

		# Only fill blanks, so anything the user already typed is kept
		for key, fieldname in CARD_FIELD_MAP.items():
			value = getattr(details, key)
			if value and not doc.get(fieldname):
				doc.set(fieldname, value.strip())

		doc.card_scan_status = "Completed"
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

		doc.ai_summary = "<p>" + frappe.utils.escape_html(insights.ai_summary.strip()) + "</p>"
		if not doc.business_nature:
			doc.business_nature = insights.business_nature
		if not doc.established_year and insights.established_year:
			doc.established_year = insights.established_year
		if not doc.linkedin_url:
			doc.linkedin_url = links.get("linkedin") or insights.linkedin_url
		if not doc.facebook_url:
			doc.facebook_url = links.get("facebook") or insights.facebook_url

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


def social_links(soups: list[BeautifulSoup]) -> dict:
	found = {}
	for soup in soups:
		for a in soup.find_all("a", href=True):
			href = a["href"]
			host = urlparse(href).hostname or ""
			if host.endswith("linkedin.com"):
				found.setdefault("linkedin", href)
			elif host.endswith("facebook.com"):
				found.setdefault("facebook", href)
	return found
