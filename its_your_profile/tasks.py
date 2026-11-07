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
	"segment": "segment",  # industry, free text (2026-11-07)
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

# Business Nature is a fixed dropdown: AI answers are matched to one of these, anything else dropped
BUSINESS_NATURES = ("Service", "Manufacturing", "Hybrid/Trading")


def clean_nature(value: str | None) -> str | None:
	"""'manufacturer' → 'Manufacturing', 'trading' → 'Hybrid/Trading'; None if it doesn't match."""
	text = (value or "").strip().lower()
	if not text:
		return None
	for nature in BUSINESS_NATURES:
		if text == nature.lower():
			return nature
	if "manufactur" in text:
		return "Manufacturing"
	if "trad" in text or "hybrid" in text:
		return "Hybrid/Trading"
	if "service" in text:
		return "Service"
	return None


def scan_visiting_card(profile: str):
	doc = frappe.get_doc("Business Profile", profile)
	sides = [url for url in (doc.visiting_card, doc.visiting_card_back) if url]
	if not sides:
		return

	doc.db_set("card_scan_status", "Processing", commit=True)

	try:
		# Front first, so its values win; the optional back side only fills what's still blank
		results = []
		logo_url = None
		for file_url in sides:
			file = frappe.get_doc("File", {"file_url": file_url})
			mime_type = mimetypes.guess_type(file.file_name or file_url)[0] or "image/jpeg"
			content = file.get_content()
			details = ai.extract_card_details(content, mime_type)
			results.append(details)
			if not logo_url and not doc.company_logo:
				logo_url = save_card_logo(content, details.logo_box, profile)

		# The AI call is slow; reload so edits saved meanwhile aren't overwritten (TimestampMismatchError)
		doc = frappe.get_doc("Business Profile", profile)

		from its_your_profile.its_your_profile.doctype.business_profile.business_profile import card_colours

		# Only fill blanks, so anything the user already typed is kept
		for details in results:
			for key, fieldname in CARD_FIELD_MAP.items():
				value = getattr(details, key)
				if value and not doc.get(fieldname):
					doc.set(fieldname, value.strip())
			if not doc.business_nature and (nature := clean_nature(getattr(details, "business_nature", None))):
				doc.business_nature = nature
			for fieldname, value in card_colours(details).items():
				if value and not doc.get(fieldname):
					doc.set(fieldname, value)
			add_profile_links(doc, card_links(details.social_links))

		if not doc.website_url:
			doc.website_url = website_from_email(doc.email)
		if logo_url and not doc.company_logo:
			doc.company_logo = logo_url

		doc.card_scan_status = "Completed"
		doc.flags.from_scan = True
		doc.save(ignore_permissions=True)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(f"Visiting card scan failed for {profile}")
		logger.exception(f"Visiting card scan failed for {profile}")
		frappe.db.set_value("Business Profile", profile, "card_scan_status", "Failed")

	frappe.db.commit()


AUTO_LOGO_NAME = re.compile(r"^/files/logo-[0-9a-f]{8}\.png$")


def add_logo_from_card(profile: str, redo: bool = False):
	"""Fill a missing Company Logo from the card photos, front first. Touches nothing else.
	With redo, a logo cut from the card earlier is cut again; one uploaded by hand is kept."""
	doc = frappe.get_doc("Business Profile", profile)
	if doc.company_logo and not (redo and AUTO_LOGO_NAME.match(doc.company_logo)):
		return
	old_logo = doc.company_logo
	try:
		for file_url in (doc.visiting_card, doc.visiting_card_back):
			if not file_url:
				continue
			file = frappe.get_doc("File", {"file_url": file_url})
			mime_type = mimetypes.guess_type(file.file_name or file_url)[0] or "image/jpeg"
			content = file.get_content()
			details = ai.extract_card_details(content, mime_type)
			if logo_url := save_card_logo(content, details.logo_box, profile):
				doc.db_set("company_logo", logo_url, update_modified=False)
				break
		else:
			# No clean logo found this time: show the initials rather than the old rough cut
			if old_logo:
				doc.db_set("company_logo", None, update_modified=False)
		if old_logo and old_logo != doc.company_logo:
			for name in frappe.get_all("File", filters={"file_url": old_logo}, pluck="name"):
				frappe.delete_doc("File", name, ignore_permissions=True)
	except Exception:
		frappe.db.rollback()
		logger.exception(f"Logo from card failed for {profile}")
		return
	frappe.db.commit()


def save_card_logo(content: bytes, box: list[float] | None, profile: str | None = None) -> str | None:
	"""Cut the logo out of a card photo, using the box the AI found ([ymin, xmin, ymax, xmax] on a
	0-1000 scale), and save it as a public file for the profile page. None if no clean logo is found."""
	import io

	from PIL import Image, ImageOps

	if not box or len(box) != 4:
		return None
	ymin, xmin, ymax, xmax = (min(max(float(v), 0), 1000) / 1000 for v in box)
	# A sliver is a misread; a box over most of the card is the whole card, not a logo
	if ymax - ymin < 0.02 or xmax - xmin < 0.02 or (ymax - ymin) * (xmax - xmin) > 0.7:
		return None

	try:
		image = ImageOps.exif_transpose(Image.open(io.BytesIO(content))).convert("RGB")
	except Exception:
		return None  # a format Pillow can't open, e.g. HEIC

	logo = cut_out_logo(image, (xmin, ymin, xmax, ymax))
	if not logo:
		return None
	buffer = io.BytesIO()
	logo.save(buffer, format="PNG")

	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"logo-{frappe.generate_hash(length=8)}.png",
			"attached_to_doctype": "Business Profile" if profile else None,
			"attached_to_name": profile,
			"attached_to_field": "company_logo" if profile else None,
			"is_private": 0,
			"content": buffer.getvalue(),
		}
	).insert(ignore_permissions=True)
	return file.file_url


# Logo cleanup works on a small copy of the photo; the final cut is made from the full-size one
LOGO_WORK_SIZE = 400
# How far (0-255) a pixel's colour must be from the card's paper to count as printed ink
INK_THRESHOLD = 45
# Ink fades in between these, so the edges of letters stay smooth on the page
INK_FADE = (18, 70)


def cut_out_logo(image, box):
	"""Cut the logo out of a card photo, clean: on a transparent background, without the card's
	other print (names, lines, patterns) or the photo's shadows. `box` is the AI's rough guess
	(left, top, right, bottom as 0-1 fractions). None if no clean logo can be found."""
	from PIL import Image, ImageChops, ImageFilter, ImageOps

	width, height = image.size
	left, top, right, bottom = box
	# Look beyond the AI's box, which is rough and can clip the logo
	margin_x, margin_y = (right - left) * 0.25, (bottom - top) * 0.25
	region = (
		max(0, int((left - margin_x) * width)),
		max(0, int((top - margin_y) * height)),
		min(width, int((right + margin_x) * width)),
		min(height, int((bottom + margin_y) * height)),
	)
	area = image.crop(region)
	scale = min(1, LOGO_WORK_SIZE / max(area.size))
	small = area.resize((max(1, round(area.width * scale)), max(1, round(area.height * scale))))
	w, h = small.size

	paper = paper_colour(small)
	ink = ink_strength(small, paper)
	labels, shapes = find_shapes([v > INK_THRESHOLD for v in ink.getdata()], w, h)

	# Shapes running off the edge are patterns, borders or shadows bigger than any logo;
	# specks are dust and photo noise
	min_size = max(4, w * h * 0.0005)
	shapes = [s for s in shapes if s["size"] >= min_size and not touches_edge(s["box"], w, h)]
	if not shapes:
		return None

	# Start from the biggest shape inside the AI's box, usually the logo's symbol, and take in the
	# shapes close to it (the name, a tagline). Print further away is the rest of the card.
	ai_box = (
		(left * width - region[0]) * scale,
		(top * height - region[1]) * scale,
		(right * width - region[0]) * scale,
		(bottom * height - region[1]) * scale,
	)
	inside = [s for s in shapes if box_gap(s["box"], ai_box) == 0] or shapes
	seed = max(inside, key=lambda s: s["size"])
	reach = max(seed["box"][2] - seed["box"][0], seed["box"][3] - seed["box"][1]) * 0.6
	group, group_box = [seed], seed["box"]
	added = True
	while added:
		added = False
		for shape in shapes:
			if shape not in group and box_gap(shape["box"], group_box) <= reach:
				group.append(shape)
				group_box = union_box(group_box, shape["box"])
				added = True

	# Too small to be read on the page
	if group_box[2] - group_box[0] < w * 0.08 or group_box[3] - group_box[1] < h * 0.06:
		return None

	# A little room so letter edges aren't cut
	pad = max(2, round(max(group_box[2] - group_box[0], group_box[3] - group_box[1]) * 0.03))
	cut_small = (
		max(0, group_box[0] - pad),
		max(0, group_box[1] - pad),
		min(w, group_box[2] + pad),
		min(h, group_box[3] + pad),
	)
	cut = (
		region[0] + int(cut_small[0] / scale),
		region[1] + int(cut_small[1] / scale),
		region[0] + min(area.width, round(cut_small[2] / scale)),
		region[1] + min(area.height, round(cut_small[3] / scale)),
	)
	logo = image.crop(cut)

	# Paper becomes transparent, ink stays; only the logo's own shapes are kept
	low, high = INK_FADE
	alpha = ink_strength(logo, paper).point(
		lambda v: 0 if v <= low else 255 if v >= high else (v - low) * 255 // (high - low)
	)
	keep_labels = {s["label"] for s in group}
	keep = Image.new("L", (w, h))
	keep.putdata([255 if label in keep_labels else 0 for label in labels])
	keep = keep.filter(ImageFilter.MaxFilter(3)).crop(cut_small).resize(logo.size, Image.BILINEAR)
	alpha = ImageChops.multiply(alpha, keep)

	# Photos make print look dull and greyish; stretch the colours back to full strength
	# (preserve_tone keeps the brand's hue instead of stretching each colour channel apart)
	logo = ImageOps.autocontrast(logo, cutoff=1, preserve_tone=True).convert("RGBA")
	logo.putalpha(alpha)
	return logo.crop(alpha.getbbox() or (0, 0, *logo.size))


def paper_colour(image):
	"""The card's background colour: the most common colour, in coarse steps to ignore photo noise."""
	from collections import Counter

	counts = Counter((r >> 4, g >> 4, b >> 4) for r, g, b in image.getdata())
	r, g, b = counts.most_common(1)[0][0]
	return ((r << 4) + 8, (g << 4) + 8, (b << 4) + 8)


def ink_strength(image, paper):
	"""Greyscale image of how far each pixel's colour is from the paper: 0 is paper, 255 is far off."""
	from PIL import Image, ImageChops

	r, g, b = ImageChops.difference(image, Image.new("RGB", image.size, paper)).split()
	return ImageChops.lighter(ImageChops.lighter(r, g), b)


def find_shapes(mask, width, height):
	"""Group touching ink pixels into shapes. Returns a label per pixel (0 for paper) and the shapes,
	each with its label, bounding box (left, top, right, bottom) and size in pixels."""
	labels = [0] * len(mask)
	shapes = []
	for start, is_ink in enumerate(mask):
		if not is_ink or labels[start]:
			continue
		label = len(shapes) + 1
		labels[start] = label
		stack = [start]
		x0 = x1 = start % width
		y0 = y1 = start // width
		size = 0
		while stack:
			i = stack.pop()
			size += 1
			x, y = i % width, i // width
			x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
			for ny in (y - 1, y, y + 1):
				if 0 <= ny < height:
					for nx in (x - 1, x, x + 1):
						if 0 <= nx < width:
							j = ny * width + nx
							if mask[j] and not labels[j]:
								labels[j] = label
								stack.append(j)
		shapes.append({"label": label, "box": (x0, y0, x1 + 1, y1 + 1), "size": size})
	return labels, shapes


def touches_edge(box, width, height):
	return box[0] <= 0 or box[1] <= 0 or box[2] >= width or box[3] >= height


def box_gap(a, b):
	"""Distance between two boxes; 0 when they overlap."""
	dx = max(0, b[0] - a[2], a[0] - b[2])
	dy = max(0, b[1] - a[3], a[1] - b[3])
	return max(dx, dy)


def union_box(a, b):
	return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


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
			for field in (
				"ai_summary",
				"services",
				"business_nature",
				"linkedin_url",
				"facebook_url",
				"established_year",
			):
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
		# The owner's own list wins; the AI only fills an empty one
		if not (doc.services or "").strip() and insights.services:
			doc.services = "\n".join(s.strip() for s in insights.services[:10] if s.strip())
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


def write_faqs(profile: str, replace: bool = False):
	"""Have the AI write FAQs from the profile's facts. Leaves FAQs someone already wrote alone
	unless `replace` (the desk's Write FAQs Again button)."""
	doc = frappe.get_doc("Business Profile", profile)
	if (doc.faqs and not replace) or not doc.company_name:
		return

	try:
		answer = ai.write_faqs(doc.get_facts_for_ai())
		faqs = [f for f in answer.faqs if f.question.strip() and f.answer.strip()][:6]
		if not faqs:
			return

		# The AI call is slow; reload so edits saved meanwhile aren't overwritten
		doc = frappe.get_doc("Business Profile", profile)
		if doc.faqs and not replace:
			return
		doc.set("faqs", [{"question": f.question.strip(), "answer": f.answer.strip()} for f in faqs])
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(f"Writing FAQs failed for {profile}")
		logger.exception(f"Writing FAQs failed for {profile}")
		if replace:
			raise


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


def link_kind(href: str) -> tuple[str, str | None] | None:
	"""(platform, label) of a profile link on a known site (LINK_RULES), else None."""
	parsed = urlparse(href)
	host, path = (parsed.hostname or "").removeprefix("www."), parsed.path or ""
	if parsed.scheme not in ("http", "https") or any(s in path for s in SHARE_PATHS):
		return None
	for suffix, path_part, platform, label in LINK_RULES:
		if (host == suffix or host.endswith("." + suffix)) and path_part in path:
			return platform, label
	return None


def social_links(soups: list[BeautifulSoup]) -> list[tuple[str, str | None, str]]:
	"""Find the company's profile links on its pages, one per platform, as (platform, label, url)."""
	found, seen = [], set()
	for soup in soups:
		for a in soup.find_all("a", href=True):
			href = a["href"].strip()
			if (kind := link_kind(href)) and kind not in seen:
				seen.add(kind)
				found.append((*kind, href))
	return found


def card_links(urls: list[str] | None) -> list[tuple[str, str | None, str]]:
	"""Profile links the AI read off a card, one per platform, as (platform, label, url).
	Only known sites are kept, so a misread website or email never ends up as a profile link."""
	found, seen = [], set()
	for url in urls or []:
		url = (url or "").strip()
		if url and "://" not in url:
			url = "https://" + url
		if (kind := link_kind(url)) and kind not in seen:
			seen.add(kind)
			found.append((*kind, url))
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
