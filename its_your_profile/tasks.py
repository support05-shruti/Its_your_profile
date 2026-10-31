"""Background jobs, enqueued from BusinessProfile.on_update."""

import ipaddress
import mimetypes
import re
import socket
import subprocess
from urllib.parse import urljoin, urlparse

import frappe
import requests
from bs4 import BeautifulSoup

from its_your_profile import ai

# Also written to logs/its_your_profile.log so failures can be read without opening the desk
logger = frappe.logger("its_your_profile", allow_site=True)

MAX_TEXT_CHARS = 20000
# Less text than this means the page is built by JavaScript and must be opened in a browser
MIN_PAGE_TEXT = 500
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

		from its_your_profile.its_your_profile.doctype.business_profile.business_profile import card_colours

		# Only fill blanks, so anything the user already typed is kept
		for details in results:
			for key, fieldname in CARD_FIELD_MAP.items():
				value = getattr(details, key)
				if value and not doc.get(fieldname):
					doc.set(fieldname, value.strip())
			for fieldname, value in card_colours(details).items():
				if value and not doc.get(fieldname):
					doc.set(fieldname, value)

		if not doc.website_url:
			doc.website_url = website_from_email(doc.email)

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
		home = fetch_page(doc.website_url)
		pages = [home]
		if contact_url := find_contact_page(home, doc.website_url):
			try:
				pages.append(fetch_page(contact_url))
			except Exception:
				pass  # the homepage alone is still useful

		soups = [BeautifulSoup(html, "html.parser") for html in pages]
		text = "\n\n".join(page_text(s) for s in soups)[:MAX_TEXT_CHARS]
		insights = ai.analyse_website(text, doc.company_name)
		if not insights.ai_summary and ai._setting("gemini_api_key"):
			# Sites built in the browser (Hostinger Horizons, Wix...) give almost no text; look the company up instead
			researched = ai.research_company(doc.company_name, doc.website_url, doc.city)
			for field in ("ai_summary", "business_nature", "linkedin_url", "facebook_url", "established_year"):
				if not getattr(insights, field):
					setattr(insights, field, getattr(researched, field))
		links = social_links(soups)
		map_url = find_map_url(soups)

		# The AI call is slow; reload so edits saved meanwhile aren't overwritten (TimestampMismatchError)
		doc = frappe.get_doc("Business Profile", profile)
		# Blank rather than keep an old summary that may only say the website had no text
		doc.ai_summary = (
			"<p>" + frappe.utils.escape_html(insights.ai_summary.strip()) + "</p>" if insights.ai_summary else None
		)
		if not doc.business_nature and insights.business_nature:
			doc.business_nature = insights.business_nature
		if not doc.established_year and insights.established_year:
			doc.established_year = insights.established_year
		# The AI only fills a platform the page's own <a> links didn't give us
		for platform, url in (("LinkedIn", insights.linkedin_url), ("Facebook", insights.facebook_url)):
			if url and not any(p == platform for p, _label, _url in links):
				links.append((platform, None, url))
		add_profile_links(doc, links)
		use_website_map(doc, map_url)

		doc.save(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(f"Website scrape failed for {profile}")
		logger.exception(f"Website scrape failed for {profile}")


LINKEDIN_PERSON = re.compile(r"^https?://([a-z]{2,3}\.)?linkedin\.com/in/[^/?#\s]+", re.I)
LINKEDIN_COMPANY = re.compile(r"^https?://([a-z]{2,3}\.)?linkedin\.com/company/[^/?#\s]+", re.I)


def find_linkedin(profile: str):
	# The search runs on Gemini only; without its key there is nothing to search with
	if not ai._setting("gemini_api_key"):
		return
	doc = frappe.get_doc("Business Profile", profile)
	if not doc.contact_person:
		return

	doc.db_set("linkedin_status", "Searching", commit=True)

	try:
		match = ai.find_linkedin(
			doc.contact_person, doc.designation, doc.company_name, doc.city, doc.website_url
		)
		person_url = clean_linkedin_url(match.person_url, LINKEDIN_PERSON)
		company_url = clean_linkedin_url(match.company_url, LINKEDIN_COMPANY)

		# The AI call is slow; reload so edits saved meanwhile aren't overwritten (TimestampMismatchError)
		doc = frappe.get_doc("Business Profile", profile)
		if person_url and not doc.contact_linkedin_url:
			doc.contact_linkedin_url = person_url
		if company_url:
			add_profile_links(doc, [("LinkedIn", None, company_url)])
		doc.linkedin_status = "Found" if doc.contact_linkedin_url else "Not Found"

		doc.save(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(f"LinkedIn search failed for {profile}")
		logger.exception(f"LinkedIn search failed for {profile}")
		frappe.db.set_value("Business Profile", profile, "linkedin_status", "Failed")
		frappe.db.commit()


def clean_linkedin_url(url: str | None, pattern: re.Pattern) -> str | None:
	"""in.linkedin.com/in/name?trk=x → https://www.linkedin.com/in/name; anything else → None."""
	found = pattern.match((url or "").strip())
	return "https://www.linkedin.com" + urlparse(found.group()).path if found else None


# Free/personal mail services: an address there says nothing about the business's own website
FREE_EMAIL_DOMAINS = {
	"gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.in", "ymail.com", "rocketmail.com",
	"rediffmail.com", "outlook.com", "outlook.in", "hotmail.com", "live.com", "live.in", "msn.com",
	"icloud.com", "me.com", "aol.com", "zoho.com", "zohomail.in", "protonmail.com", "proton.me",
	"gmx.com", "mail.com", "yandex.com",
}  # fmt: skip


def staff_email_domains() -> set[str]:
	"""Domains of the desk users' own emails. A staff address typed in for testing
	(support@softworld.co.in) says nothing about the business on the card."""
	emails = frappe.get_all("User", filters={"user_type": "System User", "enabled": 1}, pluck="email")
	return {e.rsplit("@", 1)[-1].lower() for e in emails if e and "@" in e}


def website_from_email(email: str | None) -> str | None:
	"""info@softworld.co.in → https://softworld.co.in, but only if that website actually opens.
	Personal addresses (gmail.com and the like) and our own staff's domain give nothing."""
	domain = email.rsplit("@", 1)[-1].strip().lower() if email and "@" in email else ""
	if not domain or "." not in domain or domain in FREE_EMAIL_DOMAINS or domain in staff_email_domains():
		return None

	for url in (f"https://{domain}", f"https://www.{domain}"):
		try:
			ensure_public_url(url)
			response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=8, allow_redirects=True)
			ensure_public_url(response.url)
			if response.ok:
				return url
		except Exception:
			continue  # no such site, or not reachable: try the next form
	return None


def fetch(url: str) -> str:
	ensure_public_url(url)
	response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20, allow_redirects=True)
	ensure_public_url(response.url)
	response.raise_for_status()
	return response.text


def fetch_page(url: str) -> str:
	"""The page's HTML. Sites built in the browser with JavaScript (Hostinger Horizons, Wix, React...)
	send almost no text, so those are opened in headless Chromium to read what a visitor sees."""
	html = fetch(url)
	if len(page_text(BeautifulSoup(html, "html.parser"))) >= MIN_PAGE_TEXT:
		return html
	try:
		return render(url) or html
	except Exception:
		logger.exception(f"Could not open {url} in Chromium")
		return html


def render(url: str) -> str:
	from frappe.utils.print_utils import find_or_download_chromium_executable

	ensure_public_url(url)
	result = subprocess.run(
		[
			# Frappe's own Chromium for PDFs, downloaded into frappe-bench/chromium on first use
			find_or_download_chromium_executable(),
			"--headless",
			"--no-sandbox",
			"--disable-gpu",
			"--disable-dev-shm-usage",
			f"--user-agent={USER_AGENT}",
			# Let the page's scripts run for up to 10 seconds before reading it
			"--virtual-time-budget=10000",
			"--dump-dom",
			url,
		],
		capture_output=True,
		text=True,
		timeout=90,
	)
	return result.stdout


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
	# JavaScript-built sites often have no body text, but may still carry a useful meta description
	meta = [soup.title.get_text(" ", strip=True) if soup.title else ""]
	for attrs in ({"name": "description"}, {"property": "og:description"}, {"name": "keywords"}):
		if tag := soup.find("meta", attrs=attrs):
			meta.append(tag.get("content") or "")
	for tag in soup(["script", "style", "noscript", "svg"]):
		tag.decompose()
	return "\n".join(filter(None, [*meta, soup.get_text(" ", strip=True)]))


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


MAP_EMBED = re.compile(r"^https://(www\.|maps\.)?google\.[a-z.]+/maps/embed", re.I)
MAP_LINK = re.compile(r"^https://((www\.|maps\.)?google\.[a-z.]+/maps|maps\.app\.goo\.gl/|goo\.gl/maps)", re.I)


def find_map_url(soups: list[BeautifulSoup]) -> str | None:
	"""The business's own Google Map on its website: an embedded map (<iframe>) first, as it is
	the exact location the owner chose, else a link to Google Maps."""
	for soup in soups:
		for frame in soup.find_all("iframe", src=True):
			src = frame["src"].strip()
			src = "https:" + src if src.startswith("//") else src
			if MAP_EMBED.match(src):
				return src
	for soup in soups:
		for a in soup.find_all("a", href=True):
			href = a["href"].strip()
			if MAP_LINK.match(href):
				return href
	return None


def use_website_map(doc, map_url):
	"""Prefer the website's map over one we built from the address; never replace one typed in."""
	from its_your_profile.its_your_profile.doctype.business_profile.business_profile import MAPS_SEARCH_PREFIX

	if map_url and (not doc.google_maps_url or doc.google_maps_url.startswith(MAPS_SEARCH_PREFIX)):
		doc.google_maps_url = map_url


def add_profile_links(doc, links):
	"""Append links to the profile's table, skipping platforms (and URLs) it already has."""
	have = {(row.platform, row.label or None) for row in doc.profile_links}
	have_urls = {row.url.rstrip("/").lower() for row in doc.profile_links if row.url}
	for platform, label, url in links:
		if (platform, label) in have or url.rstrip("/").lower() in have_urls:
			continue
		doc.append("profile_links", {"platform": platform, "label": label, "url": url})
		have.add((platform, label))
