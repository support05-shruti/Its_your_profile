# Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd and contributors
# For license information, please see license.txt

import html
import json
import re
from urllib.parse import quote_plus

import frappe
from frappe.website.website_generator import WebsiteGenerator


# Front is the main card photo; the back side is optional
CARD_SIDES = ("visiting_card", "visiting_card_back")

# Fields the card scan fills; kept if a stale form save sends them back empty
CARD_FIELDS = (
	"company_name",
	"contact_person",
	"designation",
	"phone",
	"email",
	"website_url",
	"address_line",
	"city",
	"state",
	"pincode",
	"name_color",
	"brand_color",
)


# Set only when the welcome email goes out; never taken from a submitted form
WELCOME_FIELDS = ("welcome_email_sent", "welcome_email_sent_on")


def welcome_emails_automatic():
	"""Its Your Profile Settings → Send Welcome Email Automatically (off by default)."""
	try:
		return bool(frappe.utils.cint(frappe.db.get_single_value("Its Your Profile Settings", "send_welcome_email")))
	except Exception:
		return False  # settings not migrated yet


def welcome_email_account():
	"""The Email Account chosen in Its Your Profile Settings → Send From (None = default outgoing)."""
	try:
		return frappe.db.get_single_value("Its Your Profile Settings", "welcome_email_account")
	except Exception:
		return None  # settings not migrated yet


def make_profile_route(when):
	"""Next public page address for a card made at `when`: business/iyp-<yy>-<mm>-<number>,
	e.g. business/iyp-26-10-00005. One counter per year (Frappe's Series table, key
	"iyp-<yyyy>-"), so numbers never repeat and each year starts at 00001."""
	from frappe.model.naming import getseries

	number = getseries(f"iyp-{when.year}-", 5)
	return f"business/iyp-{when:%y}-{when.month:02d}-{number}"


# Maps links we build from the address start with this; a map found on the website replaces them
MAPS_SEARCH_PREFIX = "https://www.google.com/maps/search/?api=1&query="
MAP_EMBED = re.compile(r"^https://(www\.|maps\.)?google\.[a-z.]+/maps/embed", re.I)

COLOUR_FIELDS = ("name_color", "brand_color")
HEX_COLOUR = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def clean_hex(value):
	"""'#e8711a', 'E8711A' or '#e71' → '#E8711A'; anything else → None (never reaches the page)."""
	match = HEX_COLOUR.match((value or "").strip())
	if not match:
		return None
	digits = match.group(1)
	if len(digits) == 3:
		digits = "".join(c * 2 for c in digits)
	return "#" + digits.upper()


def card_colours(details):
	"""Colours the AI read from a card, as clean hex codes for the colour fields."""
	return {fieldname: clean_hex(getattr(details, fieldname, None)) for fieldname in COLOUR_FIELDS}


def readable_on_white(hex_colour, min_contrast=3.0):
	"""Darken a card colour until it can be read on the white page (3:1, for large text and
	headings). Pale card colours like yellow would otherwise be invisible."""
	if not hex_colour:
		return None
	r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))

	def contrast(r, g, b):
		def channel(c):
			c /= 255
			return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

		luminance = 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
		return 1.05 / (luminance + 0.05)

	while contrast(r, g, b) < min_contrast and (r or g or b):
		r, g, b = int(r * 0.9), int(g * 0.9), int(b * 0.9)
	return f"#{r:02X}{g:02X}{b:02X}"


PHONE_SEPARATORS = re.compile(r"[\s\-().]")


def clean_phone(phone):
	"""'+91 20 2447-1409' → '+912024471409'. Keeps '+', and '/' or ',' between two numbers."""
	return PHONE_SEPARATORS.sub("", phone or "") or None


def whatsapp_number(phone):
	"""'+912024471409' → '912024471409'; a 10-digit Indian number gets the 91 country code."""
	digits = re.sub(r"\D", "", phone or "")
	if len(digits) == 11 and digits.startswith("0"):
		digits = digits[1:]
	if len(digits) == 10:
		digits = "91" + digits
	return digits if len(digits) >= 11 else None


def clean_url(url, label):
	"""Add https:// when missing, and allow only web links (no javascript: etc. on a public page)."""
	url = (url or "").strip()
	if url and "://" not in url:
		url = "https://" + url
	if url and not url.lower().startswith(("http://", "https://")):
		frappe.throw(frappe._("{0} must be a web address").format(label))
	return url or None


BUSINESS_KINDS = {
	"Service": "service business",
	"Manufacturing": "manufacturer",
	"Hybrid/Trading": "trading business",
}


def join_words(items):
	"""["a", "b", "c"] → "a, b and c"."""
	return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def drop_empty(data):
	return {k: v for k, v in data.items() if v}


class BusinessProfile(WebsiteGenerator):
	def validate(self):
		# A profile created from a card upload has no company name until the scan finishes
		if not self.company_name and not (self.visiting_card or self.visiting_card_back):
			frappe.throw(frappe._("Please enter a Company Name or upload a Visiting Card"))

		self.phone = clean_phone(self.phone)
		self.set_website_from_email()
		self.validate_urls()
		for fieldname in COLOUR_FIELDS:
			self.set(fieldname, clean_hex(self.get(fieldname)))
		self.set_google_maps_url()
		self.keep_welcome_fields()
		self.make_logo_public()

		if self.company_name:
			self.set_route()

		new_sides = [
			self.get(side)
			for side in CARD_SIDES
			if self.get(side) and (self.is_new() or self.has_value_changed(side))
		]
		if new_sides:
			from its_your_profile.api import card_read_cache_key

			# Sides already read in the form before Save (api.read_visiting_card) need no background scan
			reads = [frappe.cache.get_value(card_read_cache_key(url)) for url in new_sides]
			if all(reads):
				self.card_scan_status = "Completed"
				# Front first, so its colours win over the back's
				for read in reads:
					colours = read.get("colours", {}) if isinstance(read, dict) else {}
					for fieldname, value in colours.items():
						if value and not self.get(fieldname):
							self.set(fieldname, value)
					if isinstance(read, dict) and read.get("logo") and not self.company_logo:
						self.company_logo = read["logo"]
			else:
				self.card_scan_status = "Pending"
		elif not self.is_new() and not self.flags.from_scan and self.get_doc_before_save():
			# Status is owned by the scan job: a form saved with a stale "Pending" must not
			# restart the scan, and must not wipe the fields the scan just filled
			before = self.get_doc_before_save()
			self.card_scan_status = before.card_scan_status
			if before.card_scan_status == "Completed":
				for fieldname in CARD_FIELDS:
					if not self.get(fieldname) and before.get(fieldname):
						self.set(fieldname, before.get(fieldname))

	def set_website_from_email(self):
		"""No website given: try the company domain of the email (info@acme.in → https://acme.in).
		Only when the email is new on this save, as it means a quick check that the site opens."""
		if self.website_url or not self.email or not self.has_value_changed("email"):
			return
		from its_your_profile.tasks import website_from_email

		self.website_url = website_from_email(self.email)

	def keep_welcome_fields(self):
		"""These change only when the email is sent (db_set), so a form opened earlier and saved
		with stale values must not reset them and trigger a second email."""
		before = None if self.is_new() else self.get_doc_before_save()
		if before:
			for fieldname in WELCOME_FIELDS:
				self.set(fieldname, before.get(fieldname))

	def make_logo_public(self):
		"""The logo is for the public page, but the uploader may have marked it private."""
		if not (self.company_logo or "").startswith("/private/files/"):
			return
		file_name = frappe.db.get_value("File", {"file_url": self.company_logo})
		if not file_name:
			return
		file = frappe.get_doc("File", file_name)
		file.is_private = 0
		file.save(ignore_permissions=True)
		self.company_logo = file.file_url

	def validate_urls(self):
		for fieldname in ("website_url", "google_maps_url"):
			self.set(fieldname, clean_url(self.get(fieldname), self.meta.get_label(fieldname)))

		for row in self.profile_links:
			row.url = clean_url(row.url, frappe._("Link in row {0}").format(row.idx))
			if row.platform != "Other":
				row.label = None

	def set_google_maps_url(self):
		"""Cards carry an address, not a Maps link, so build a Maps search link from the address."""
		if self.google_maps_url:
			return
		parts = [self.company_name, self.address_line, self.city, self.state, self.pincode]
		query = ", ".join(" ".join(p.split()) for p in parts if p and p.strip())
		if self.address_line or self.city:
			self.google_maps_url = MAPS_SEARCH_PREFIX + quote_plus(query)

	def get_map_embed_url(self):
		"""A map that can be shown inside the public page: the website's own embedded map when
		we found one, otherwise Google's address search in embed mode (no API key needed)."""
		if MAP_EMBED.match(self.google_maps_url or ""):
			return self.google_maps_url
		if not (self.address_line or self.city):
			return None
		parts = [self.company_name, self.address_line, self.city, self.state, self.pincode]
		query = ", ".join(" ".join(p.split()) for p in parts if p and p.strip())
		return "https://maps.google.com/maps?q=" + quote_plus(query) + "&output=embed"

	def make_route(self):
		"""business/iyp-<yy>-<mm>-<5-digit number>, e.g. business/iyp-26-10-00005.
		The number counts every card in the year and starts again from 00001 each January."""
		return make_profile_route(frappe.utils.get_datetime(self.creation or frappe.utils.now_datetime()))

	def on_update(self):
		super().on_update()

		if (self.visiting_card or self.visiting_card_back) and self.card_scan_status == "Pending":
			frappe.enqueue(
				"its_your_profile.tasks.scan_visiting_card",
				queue="long",
				profile=self.name,
				job_id=f"scan_visiting_card::{self.name}",
				deduplicate=True,
				enqueue_after_commit=True,
			)

		if self.website_url and self.has_value_changed("website_url"):
			frappe.enqueue(
				"its_your_profile.tasks.scrape_website",
				queue="long",
				profile=self.name,
				job_id=f"scrape_website::{self.name}",
				deduplicate=True,
				enqueue_after_commit=True,
			)

		# FAQs for AI search, once the page is live. A new website is read first: its summary and
		# services make better FAQs, and that job's save brings us back here.
		website_pending = self.website_url and self.has_value_changed("website_url")
		if self.published and self.company_name and not self.faqs and not website_pending:
			frappe.enqueue(
				"its_your_profile.tasks.write_faqs",
				queue="long",
				profile=self.name,
				job_id=f"write_faqs::{self.name}",
				deduplicate=True,
				enqueue_after_commit=True,
			)

		if self.contact_person and (
			self.has_value_changed("contact_person") or self.has_value_changed("company_name")
		):
			frappe.enqueue(
				"its_your_profile.tasks.find_linkedin",
				queue="long",
				profile=self.name,
				job_id=f"find_linkedin::{self.name}",
				deduplicate=True,
				enqueue_after_commit=True,
			)

		# Automatic welcome, only while the switch in Settings is on: once per business, when the
		# email is new on this save. With the switch off, staff use the Desk button instead.
		if (
			welcome_emails_automatic()
			and not self.welcome_email_sent
			and self.has_value_changed("email")
			and self.ready_for_welcome()
		):
			try:
				self.send_welcome_email()
			except Exception:
				# A missing or broken email account must not stop the profile from saving
				frappe.log_error(f"Welcome email failed for {self.name}")

	def ready_for_welcome(self):
		"""The email needs a real address to go to and a live page to link to."""
		return bool(
			self.company_name and self.route and self.published and frappe.utils.validate_email_address(self.email)
		)

	def send_welcome_email(self):
		"""Email the owner the link to their public page, from the account chosen in Settings."""
		if not self.ready_for_welcome():
			frappe.throw(frappe._("Add a valid Email and a Company Name, and keep the page Published, first."))

		account = welcome_email_account()
		sender = frappe.db.get_value("Email Account", account, "email_id") if account else None

		# Attach the card photos (front, and back if added) so the owner sees what we read
		attachments = [
			{"fid": file_name}
			for file_name in (
				frappe.db.get_value("File", {"file_url": self.get(side)}, "name")
				for side in CARD_SIDES
				if self.get(side)
			)
			if file_name
		]

		frappe.sendmail(
			recipients=[self.email],
			sender=sender,
			attachments=attachments,
			subject=frappe._("Your business is live: {0}").format(self.company_name),
			template="business_profile_welcome",
			args={
				"doc": self,
				"details": self.get_details_for_email(),
				"page_url": frappe.utils.get_url(self.route),
				"edit_url": frappe.utils.get_url(f"/my-business/{self.name}/edit"),
				"has_card": bool(attachments),
			},
			reference_doctype=self.doctype,
			reference_name=self.name,
			# Send right away; the queue is otherwise only emptied every 4 minutes by the scheduler
			now=True,
		)
		self.db_set(
			{"welcome_email_sent": 1, "welcome_email_sent_on": frappe.utils.now_datetime()},
			update_modified=False,
		)

	def get_details_for_email(self):
		address = ", ".join(p for p in (self.address_line, self.city, self.state, self.pincode) if p)
		rows = [
			(frappe._("Company Name"), self.company_name),
			(frappe._("Contact Person"), self.contact_person),
			(frappe._("Designation"), self.designation),
			(frappe._("Phone"), self.phone),
			(frappe._("Email"), self.email),
			(frappe._("Website"), self.website_url),
			(frappe._("Address"), address),
		]
		return [(label, value) for label, value in rows if value]

	def get_context(self, context):
		from its_your_profile.tracking import log_crawler_visit

		context.no_cache = 1
		# People are counted by the page's script; crawlers don't run it, so count them here
		log_crawler_visit(self.name)
		context.json_ld = self.get_json_ld()
		# Card colours, made readable on the white page; the template falls back to its own
		context.page_name_color = readable_on_white(self.name_color or self.brand_color)
		context.page_brand_color = readable_on_white(self.brand_color or self.name_color)
		context.map_embed_url = self.get_map_embed_url()
		context.page_url = frappe.utils.get_url(self.route)
		context.phone_numbers = [p for p in re.split(r"[/,]", self.phone or "") if p]
		context.whatsapp_number = whatsapp_number(context.phone_numbers[0]) if context.phone_numbers else None
		# Only public files can be shown to visitors
		context.card_images = [
			self.get(side) for side in CARD_SIDES if (self.get(side) or "").startswith("/files/")
		]
		context.logo_url = self.get_logo_url()
		context.og_image = (
			frappe.utils.get_url(context.card_images[0]) if context.card_images else context.logo_url
		)
		context.years_in_business = (
			frappe.utils.now_datetime().year - self.established_year
			if self.established_year and self.established_year > 1800
			else None
		)
		context.vcard = json.dumps(self.get_vcard(context.phone_numbers)).replace("</", "<\\/")
		context.services = self.get_services()
		context.faq_items = [row for row in self.faqs if row.question and row.answer]
		context.markdown_url = frappe.utils.get_url(self.route + ".md")
		# Shown when there is no AI summary yet, so every page has a plain factual description
		context.entity_summary = None if self.ai_summary else self.get_entity_summary()
		context.metatags = {
			"title": self.company_name,
			"description": self.get_summary()[:300],
		}

	def get_vcard(self, phone_numbers):
		"""Contact file for the page's "Save Contact" button."""

		def esc(value):
			return (value or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")

		lines = [
			"BEGIN:VCARD",
			"VERSION:3.0",
			f"FN:{esc(self.contact_person or self.company_name)}",
			f"ORG:{esc(self.company_name)}",
		]
		if self.designation:
			lines.append(f"TITLE:{esc(self.designation)}")
		lines += [f"TEL;TYPE=WORK,VOICE:{esc(p)}" for p in phone_numbers]
		if self.email:
			lines.append(f"EMAIL;TYPE=WORK:{esc(self.email)}")
		if self.website_url:
			lines.append(f"URL:{esc(self.website_url)}")
		if self.address_line or self.city:
			adr = ";".join(esc(p) for p in ("", "", self.address_line, self.city, self.state, self.pincode, "India"))
			lines.append(f"ADR;TYPE=WORK:{adr}")
		lines += [f"NOTE:{esc(frappe.utils.get_url(self.route))}", "END:VCARD"]
		return "\r\n".join(lines)

	def get_logo_url(self):
		"""Full URL of the logo, or None while there is no public logo to show."""
		if (self.company_logo or "").startswith("/files/"):
			return frappe.utils.get_url(self.company_logo)

	def get_facts_for_ai(self):
		"""What the FAQ writer may use, one fact per line; nothing else is known to be true."""
		facts = [
			("Business name", self.company_name),
			("Type of business", self.business_nature),
			("City", ", ".join(p for p in (self.city, self.state) if p)),
			("Established", self.established_year),
			("Team size", self.employee_range and f"{self.employee_range} people"),
			("Contact person", ", ".join(p for p in (self.contact_person, self.designation) if p)),
			("Summary", self.get_summary()),
			("Products and services", ", ".join(self.get_services())),
			("In the owner's words", " ".join((self.about_business or "").split())),
			("Has a website", "yes" if self.website_url else None),
			("Can be contacted by", ", ".join(
				c for c, has in (("phone", self.phone), ("WhatsApp", self.phone), ("email", self.email)) if has
			)),
		]
		return "\n".join(f"- {label}: {value}" for label, value in facts if value)

	def as_markdown(self, level=1):
		"""The whole profile as Markdown for AI crawlers: served at <route>.md (level 1) and in
		/llms-full.txt (level 2, under the directory's own heading)."""
		h1, h2, h3 = ("#" * n for n in (level, level + 1, level + 2))
		page_url = frappe.utils.get_url(self.route)
		lines = [f"{h1} {self.company_name}", "", self.get_summary(), ""]

		facts = [
			("Profile page", page_url),
			("Business type", self.business_nature),
			("Established", self.established_year),
			("Team size", self.employee_range and f"{self.employee_range} people"),
			("Contact person", ", ".join(x for x in (self.contact_person, self.designation) if x)),
			("Contact person's LinkedIn", self.contact_linkedin_url),
			("Phone", self.phone),
			("Email", self.email),
			("Website", self.website_url),
			("Address", ", ".join(x for x in (self.address_line, self.city, self.state, self.pincode) if x)),
			("Map", self.google_maps_url),
			("Last updated", frappe.utils.getdate(self.modified).isoformat() if self.modified else None),
		]
		lines += [f"- {label}: {value}" for label, value in facts if value]

		if services := self.get_services():
			lines += ["", f"{h2} Products and services", ""] + [f"- {s}" for s in services]
		if self.about_business:
			lines += ["", f"{h2} In the owner's words", "", " ".join(self.about_business.split())]
		if faqs := [row for row in self.faqs if row.question and row.answer]:
			lines += ["", f"{h2} Questions and answers", ""]
			for row in faqs:
				lines += [f"{h3} {' '.join(row.question.split())}", "", " ".join(row.answer.split()), ""]
		if links := [row for row in self.profile_links if row.url]:
			lines += ["", f"{h2} Elsewhere online", ""]
			lines += [f"- {row.label or row.platform}: {row.url}" for row in links]
		return "\n".join(lines).rstrip() + "\n"

	def get_services(self):
		"""The Products & Services field as a list, one entry per line, without repeats."""
		services = {}
		for line in (self.services or "").splitlines():
			line = line.strip(" \t-•*")
			if line:
				services.setdefault(line.lower(), line)
		return list(services.values())

	def get_entity_summary(self):
		"""Plain third-person facts for AI search engines, built from the fields."""
		if not self.company_name:
			return ""
		kind = BUSINESS_KINDS.get(self.business_nature, "business")
		place = ", ".join(p for p in (self.city, self.state) if p)
		first = f"{self.company_name} is a {kind}"
		if place:
			first += f" based in {place}, India"
		if self.established_year:
			first += f", established in {self.established_year}"
		sentences = [first + "."]
		if services := self.get_services():
			sentences.append(f"It offers {join_words(services[:8])}.")
		if self.contact_person:
			role = f"the {self.designation} of" if self.designation else "the contact person at"
			sentences.append(f"{self.contact_person} is {role} {self.company_name}.")
		return " ".join(sentences)

	def get_summary(self):
		"""The AI summary once written, else the summary built from the fields."""
		# The AI summary is stored as escaped HTML; plain text needs "&" back, not "&amp;"
		text = html.unescape(frappe.utils.strip_html(self.ai_summary or ""))
		return " ".join(text.split()) or self.get_entity_summary()

	def get_json_ld(self):
		"""Schema.org graph for search and AI engines: the page, the business, its contact person and its services."""
		page_url = frappe.utils.get_url(self.route)
		business_id = f"{page_url}#business"
		person_id = f"{page_url}#person"
		services = self.get_services()

		business = {
			"@type": ["LocalBusiness", "Organization"],
			"@id": business_id,
			"name": self.company_name,
			"url": self.website_url or page_url,
			"mainEntityOfPage": page_url,
			"description": self.get_summary(),
			"telephone": self.phone,
			"email": self.email,
			"foundingDate": str(self.established_year) if self.established_year else None,
			"numberOfEmployees": self.employee_range,
			"hasMap": self.google_maps_url,
			"knowsAbout": services,
			"areaServed": {"@type": "City", "name": self.city} if self.city else None,
			# LinkedIn, X, Facebook, BNI... tie this business to its profiles elsewhere
			"sameAs": [row.url for row in self.profile_links if row.url],
			"logo": self.get_logo_url(),
			# Private cards (/private/files/...) can't be opened by visitors, so don't advertise them
			"image": frappe.utils.get_url(self.visiting_card)
			if (self.visiting_card or "").startswith("/files/")
			else None,
		}

		if self.address_line or self.city:
			business["address"] = drop_empty(
				{
					"@type": "PostalAddress",
					"streetAddress": self.address_line,
					"addressLocality": self.city,
					"addressRegion": self.state,
					"postalCode": self.pincode,
					"addressCountry": "IN",
				}
			)

		if services:
			business["hasOfferCatalog"] = {
				"@type": "OfferCatalog",
				"name": f"Products and services of {self.company_name}",
				"itemListElement": [
					{
						"@type": "Offer",
						"itemOffered": drop_empty(
							{
								"@type": "Service",
								"name": service,
								"provider": {"@id": business_id},
								"areaServed": business["areaServed"],
							}
						),
					}
					for service in services
				],
			}

		graph = [
			{
				"@type": "ProfilePage",
				"@id": page_url,
				"url": page_url,
				"name": self.company_name,
				"mainEntity": {"@id": business_id},
				# AI search prefers fresh facts; tell it when they were last checked
				"dateModified": frappe.utils.get_datetime(self.modified).isoformat() if self.modified else None,
			},
			business,
		]

		# Ready-made answers Google and AI assistants can quote
		if faqs := [row for row in self.faqs if row.question and row.answer]:
			graph.append(
				{
					"@type": "FAQPage",
					"@id": f"{page_url}#faq",
					"about": {"@id": business_id},
					"mainEntity": [
						{
							"@type": "Question",
							"name": " ".join(row.question.split()),
							"acceptedAnswer": {"@type": "Answer", "text": " ".join(row.answer.split())},
						}
						for row in faqs
					],
				}
			)

		if self.contact_person:
			business["employee"] = {"@id": person_id}
			graph.append(
				{
					"@type": "Person",
					"@id": person_id,
					"name": self.contact_person,
					"jobTitle": self.designation,
					"worksFor": {"@id": business_id},
					"sameAs": [self.contact_linkedin_url] if self.contact_linkedin_url else None,
				}
			)

		data = {"@context": "https://schema.org", "@graph": [drop_empty(node) for node in graph]}
		# Escape "</" so the JSON can never close the surrounding <script> tag
		return json.dumps(data, indent=2, ensure_ascii=False).replace("</", "<\\/")
