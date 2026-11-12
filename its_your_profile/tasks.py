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

	# CHANGE 2026-11-12: drop stray pieces. Small marks that are not part of a word (no letter next to
	# them on the same line) and much smaller than the symbol are bits of the card's other print,
	# e.g. the descenders "g g" of a faint line under the 2M logo. Letters of the logo's name and
	# tagline always have neighbours, so they stay.
	def has_neighbour(shape):
		height = shape["box"][3] - shape["box"][1]
		for other in group:
			if other is shape:
				continue
			gap = box_gap(shape["box"], other["box"])
			same_line = min(shape["box"][3], other["box"][3]) - max(shape["box"][1], other["box"][1]) > 0
			# A letter beside it on the same line, or something right next to it in any direction
			# (the dot of an "i", an accent, a part of the symbol)
			if (same_line and gap <= max(3, height * 1.2)) or gap <= max(2, height * 0.6):
				return True
		return False

	group = [
		s for s in group
		if s is seed or s["size"] >= seed["size"] * 0.05 or has_neighbour(s)
	]
	group_box = seed["box"]
	for shape in group:
		group_box = union_box(group_box, shape["box"])

	# CHANGE 2026-11-12: a block of text is not a logo. Cards without a designed logo made the AI
	# mark the name plus the lines under it ("Distributor for...", product lists), which showed as
	# a paragraph in the logo box. Count the lines of print; a logo is a mark, a name and at most a
	# short tagline, so more than 3 lines means plain text: no logo (the website's logo or the
	# generated initials are used instead).
	if count_lines(group) > 3:
		return None

	# CHANGE 2026-11-12: photo noise is not a logo. Shadows, table edges and paper texture come out as
	# thin, scratchy streaks (seen on a VSC HVAC card): every piece is a long hairline, and the ink
	# covers very little of the area. A real logo has at least one solid shape (a symbol or letters
	# of a readable height) and reasonable ink coverage.
	def is_streak(shape):
		sw, sh = shape["box"][2] - shape["box"][0], shape["box"][3] - shape["box"][1]
		return sh < max(4, h * 0.035) or sw > sh * 8

	if all(is_streak(s) for s in group):
		return None
	box_area = max(1, (group_box[2] - group_box[0]) * (group_box[3] - group_box[1]))
	if sum(s["size"] for s in group) / box_area < 0.04:
		return None

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


def count_lines(shapes):
	"""How many lines of print the shapes make: their vertical spans merged where they overlap.
	A symbol taller than the text counts as one line with the text beside it."""
	spans = sorted((s["box"][1], s["box"][3]) for s in shapes)
	lines, end = 0, None
	for top, bottom in spans:
		if end is None or top >= end:
			lines += 1
			end = bottom
		else:
			end = max(end, bottom)
	return lines


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
		if not insights.ai_summary and ai.can_search():
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


def has_linkedin(doc) -> bool:
	"""The page already shows a LinkedIn link (company page or a profile)."""
	return any(row.platform == "LinkedIn" and row.url for row in doc.profile_links)


def name_in_slug(name: str | None, url: str) -> bool:
	"""linkedin.com/in/darshan-shinde-12ab matches "Mr. Darshan Shinde" (first and last name)."""
	words = [w for w in re.findall(r"[a-z]+", (name or "").lower()) if len(w) > 2 and w not in ("mr", "mrs", "ms", "dr")]
	slug = urlparse(url).path.lower()
	return bool(words) and all(w in slug for w in (words[0], words[-1]))


def linkedin_from_website(url: str) -> list[str]:
	"""LinkedIn links on the company's own website: home page, then its contact and about pages."""
	try:
		home = fetch_page(url)
	except Exception:
		return []
	pages = [home]
	for word in ("contact", "about"):
		if (page_url := find_contact_page(home, url, word)) and page_url.rstrip("/") != url.rstrip("/"):
			try:
				pages.append(fetch_page(page_url))
			except Exception:
				pass  # the other pages are still useful
	found = []
	for html in pages:
		for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
			href = a["href"].strip()
			if link_kind(href) == ("LinkedIn", None) and href not in found:
				found.append(href)
	return found


def find_linkedin(profile: str):
	"""CHANGE NOTE 2026-11-07: every page must show a LinkedIn link. When the card gave none:
	1. look on the company's own website (home, contact and about pages) for its LinkedIn links;
	2. if still none, search the web with AI (Gemini, or OpenAI web search when Gemini isn't set up).
	The contact person's own profile (linkedin.com/in/...) is filled in too when it clearly matches."""
	doc = frappe.get_doc("Business Profile", profile)
	need_person = bool(doc.contact_person) and not doc.contact_linkedin_url
	if has_linkedin(doc) and not need_person:
		return

	doc.db_set("linkedin_status", "Searching", commit=True)

	try:
		person_url = company_url = other_url = None

		# 1. The company's own website
		if doc.website_url:
			for href in linkedin_from_website(doc.website_url):
				company_url = company_url or clean_linkedin_url(href, LINKEDIN_COMPANY)
				if found := clean_linkedin_url(href, LINKEDIN_PERSON):
					if need_person and not person_url and name_in_slug(doc.contact_person, found):
						person_url = found
					other_url = other_url or found

		# 2. A web search, for what the website didn't give
		if ai.can_search() and ((not company_url and not has_linkedin(doc)) or (need_person and not person_url)):
			match = ai.find_linkedin(
				doc.contact_person, doc.designation, doc.company_name, doc.city, doc.website_url
			)
			company_url = company_url or clean_linkedin_url(match.company_url, LINKEDIN_COMPANY)
			if need_person and not person_url:
				person_url = clean_linkedin_url(match.person_url, LINKEDIN_PERSON)

		# The AI call is slow; reload so edits saved meanwhile aren't overwritten (TimestampMismatchError)
		doc = frappe.get_doc("Business Profile", profile)
		if person_url and not doc.contact_linkedin_url:
			doc.contact_linkedin_url = person_url
		# The page's LinkedIn link: the company page, else a profile found on the website or the person's
		if not has_linkedin(doc) and (page_url := company_url or other_url or doc.contact_linkedin_url):
			add_profile_links(doc, [("LinkedIn", None, page_url)])
		doc.linkedin_status = "Found" if has_linkedin(doc) else "Not Found"

		doc.save(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(f"LinkedIn search failed for {profile}")
		logger.exception(f"LinkedIn search failed for {profile}")
		frappe.db.set_value("Business Profile", profile, "linkedin_status", "Failed")
		frappe.db.commit()


def find_linkedin_for_all():
	"""One-time fill for pages made before LinkedIn was compulsory (2026-11-07). Run with:
	bench --site <site> execute its_your_profile.tasks.find_linkedin_for_all"""
	names = frappe.get_all("Business Profile", filters={"company_name": ("is", "set")}, pluck="name")
	queued = 0
	for name in names:
		doc = frappe.get_doc("Business Profile", name)
		if has_linkedin(doc):
			continue
		frappe.enqueue(
			"its_your_profile.tasks.find_linkedin",
			queue="long",
			profile=name,
			job_id=f"find_linkedin::{name}",
			deduplicate=True,
		)
		queued += 1
	return f"Queued a LinkedIn search for {queued} of {len(names)} pages"


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


def find_contact_page(html: str, base_url: str, word: str = "contact") -> str | None:
	"""The site's own page whose link mentions `word` ("contact", or "about" for LinkedIn search)."""
	base_host = urlparse(base_url).hostname
	for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
		label = (a.get_text() + " " + a["href"]).lower()
		if word in label:
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


# ---------------------------------------------------------------------------------------------
# Automatic logo (2026-11-12). Every page gets a logo without the owner uploading one:
# 1. the logo cut from the visiting card (save_card_logo, during the scan), else
# 2. the logo from the company's website, else
# 3. a generated logo: the company's initials on its brand colour.
# Logos made here are named logo-web-*.png / logo-auto-*.png. A generated one is replaced when a
# website logo is found later. A logo uploaded by the owner, or cut from the card, is never touched.

GENERATED_LOGO_NAME = re.compile(r"^/files/logo-auto-[0-9a-f]{8}\.png$")
LOGO_MIN_SIDE = 48  # px; smaller website icons look blurry on the page
LOGO_MAX_SIDE = 512


def ensure_logo(profile: str):
	"""Give the profile the best logo we can find automatically.

	CHANGE 2026-11-12: the company's own logo file from its website is the cleanest, so it now also
	replaces a logo cut out of the card photo (a photo cut-out is never as sharp). Order:
	website logo > logo cut from the card > generated initials. A logo the owner uploaded is never
	replaced."""
	doc = frappe.get_doc("Business Profile", profile)
	current = doc.company_logo or ""
	replaceable = GENERATED_LOGO_NAME.match(current) or AUTO_LOGO_NAME.match(current)
	if current and not replaceable:
		return
	if doc.card_scan_status in ("Pending", "Processing"):
		return  # the card scan may still cut the real logo; it saves again when done

	logo_url = None
	try:
		if doc.website_url:
			# A card cut-out is only replaced by a proper logo image, not a tiny favicon
			min_side = 120 if AUTO_LOGO_NAME.match(current) else LOGO_MIN_SIDE
			logo_url = logo_from_website(doc.website_url, profile, min_side)
	except Exception:
		logger.exception(f"Website logo failed for {profile}")

	if not logo_url and not current:
		try:
			logo_url = generated_logo(doc, profile)
		except Exception:
			logger.exception(f"Generated logo failed for {profile}")

	if not logo_url:
		return
	# Reload: the profile may have been saved meanwhile (a logo uploaded by hand wins)
	latest = frappe.db.get_value("Business Profile", profile, "company_logo") or ""
	if latest and not (GENERATED_LOGO_NAME.match(latest) or AUTO_LOGO_NAME.match(latest)):
		return
	frappe.db.set_value("Business Profile", profile, "company_logo", logo_url, update_modified=False)
	if latest and latest != logo_url:
		for name in frappe.get_all("File", filters={"file_url": latest}, pluck="name"):
			frappe.delete_doc("File", name, ignore_permissions=True)
	frappe.db.commit()


def logo_candidates(html: str, base_url: str) -> list[str]:
	"""Possible logo images on a website, best first: the logo the site declares for search engines,
	a header image named "logo", its app icon, then its favicon."""
	soup = BeautifulSoup(html, "html.parser")
	found = []

	def add(url):
		url = (url or "").strip()
		if url and not url.startswith("data:"):
			url = urljoin(base_url, url)
			if url not in found:
				found.append(url)

	# Schema.org "logo" in JSON-LD
	for script in soup.find_all("script", type="application/ld+json"):
		for match in re.finditer(r'"logo"\s*:\s*(?:\{[^{}]*?"url"\s*:\s*)?"([^"]+)"', script.string or ""):
			add(match.group(1))
	for attrs in ({"property": "og:logo"}, {"itemprop": "logo"}):
		if tag := soup.find("meta", attrs=attrs):
			add(tag.get("content"))
	# <img> that calls itself a logo, in page order (the header comes first)
	for img in soup.find_all("img"):
		label = " ".join(str(img.get(a) or "") for a in ("class", "id", "alt", "src", "data-src")).lower()
		if "logo" in label and not any(w in label for w in ("partner", "client", "payment", "award")):
			add(img.get("src") or img.get("data-src"))
	for link in soup.find_all("link", href=True):
		rels = [r.lower() for r in (link.get("rel") or [])]
		if "apple-touch-icon" in rels or "apple-touch-icon-precomposed" in rels:
			add(link["href"])
	for link in soup.find_all("link", href=True):
		if "icon" in [r.lower() for r in (link.get("rel") or [])]:
			add(link["href"])
	return found


def fetch_image(url: str):
	"""A website image as a Pillow image (RGBA), or None if it isn't a usable picture."""
	import io

	from PIL import Image

	ensure_public_url(url)
	response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20, allow_redirects=True)
	ensure_public_url(response.url)
	if not response.ok or len(response.content) > 5_000_000:
		return None
	try:
		image = Image.open(io.BytesIO(response.content))
		image.load()
	except Exception:
		return None  # SVG and other formats Pillow can't draw
	return image.convert("RGBA")


def logo_from_website(website_url: str, profile: str, min_side: int = LOGO_MIN_SIDE) -> str | None:
	"""Save the company's own logo from its website as the profile logo; None if none is usable."""
	try:
		html = fetch_page(website_url)
	except Exception:
		return None
	for url in logo_candidates(html, website_url)[:8]:
		try:
			image = fetch_image(url)
		except Exception:
			continue
		# Header logos are often wide and short (e.g. 300 x 60): judge by the long side
		if not image or max(image.size) < min_side or min(image.size) < 24:
			continue
		width, height = image.size
		if width / height > 6 or height / width > 3:
			continue  # a banner or a strip, not a logo
		if bbox := image.getbbox():  # trim empty transparent edges
			image = image.crop(bbox)
		image.thumbnail((LOGO_MAX_SIDE, LOGO_MAX_SIDE))
		return save_logo_file(image, "web", profile)
	return None


def generated_logo(doc, profile: str) -> str | None:
	"""A square logo with the company's initials, white on the card's brand colour."""
	from PIL import Image, ImageDraw, ImageFont

	name = doc.company_name or doc.contact_person
	if not name:
		return None
	skip = ("pvt", "ltd", "llp", "the", "and", "of", "co", "inc", "m/s")
	words = [w for w in re.findall(r"[A-Za-z0-9]+", name) if w.lower() not in skip]
	initials = "".join(w[0] for w in words[:2]).upper() or name[:1].upper()

	colour = doc.brand_color if re.fullmatch(r"#[0-9A-Fa-f]{6}", doc.brand_color or "") else "#3B2E7E"
	rgb = tuple(int(colour[i : i + 2], 16) for i in (1, 3, 5))
	if sum(rgb) / 3 > 170:  # a very light brand colour would hide white letters: darken it
		rgb = tuple(int(c * 0.55) for c in rgb)

	size = 512
	image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
	draw = ImageDraw.Draw(image)
	draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=96, fill=(*rgb, 255))
	font = ImageFont.load_default(size=230 if len(initials) == 1 else 200)
	left, top, right, bottom = draw.textbbox((0, 0), initials, font=font)
	position = ((size - (right - left)) / 2 - left, (size - (bottom - top)) / 2 - top)
	draw.text(position, initials, font=font, fill=(255, 255, 255, 255))
	return save_logo_file(image, "auto", profile)


def save_logo_file(image, kind: str, profile: str) -> str:
	import io

	buffer = io.BytesIO()
	image.save(buffer, format="PNG")
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"logo-{kind}-{frappe.generate_hash(length=8)}.png",
			"attached_to_doctype": "Business Profile",
			"attached_to_name": profile,
			"attached_to_field": "company_logo",
			"is_private": 0,
			"content": buffer.getvalue(),
		}
	).insert(ignore_permissions=True)
	return file.file_url


def refresh_logo(profile: str):
	"""Read one page's logo again (2026-11-12): cut it from the card once more with the cleaner method
	(no stray marks), then take the website's own logo instead if it has a good one. Logos the owner
	uploaded are left alone."""
	current = frappe.db.get_value("Business Profile", profile, "company_logo") or ""
	if AUTO_LOGO_NAME.match(current):
		add_logo_from_card(profile, redo=True)
	ensure_logo(profile)


def ensure_logo_for_all():
	"""Read the logo again for every page whose logo was made automatically (cut from the card or
	generated), and fill pages that have none. Logos uploaded by owners are not touched. Run with:
	bench --site <site> execute its_your_profile.tasks.ensure_logo_for_all"""
	rows = frappe.get_all(
		"Business Profile", filters={"company_name": ("is", "set")}, fields=["name", "company_logo"]
	)
	names = [
		r.name
		for r in rows
		if not r.company_logo or AUTO_LOGO_NAME.match(r.company_logo) or GENERATED_LOGO_NAME.match(r.company_logo)
	]
	for name in names:
		frappe.enqueue(
			"its_your_profile.tasks.refresh_logo",
			queue="long",
			profile=name,
			job_id=f"refresh_logo::{name}",
			deduplicate=True,
		)
	return f"Reading the logo again for {len(names)} of {len(rows)} pages"
