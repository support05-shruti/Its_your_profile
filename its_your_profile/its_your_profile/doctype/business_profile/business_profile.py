# Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd and contributors
# For license information, please see license.txt

import json
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
)


# Set only when the welcome email goes out; never taken from a submitted form
WELCOME_FIELDS = ("welcome_email_sent", "welcome_email_sent_on")


def welcome_email_settings():
	"""(enabled, sending account) from Its Your Profile Settings. Off until it is ticked there."""
	try:
		enabled, account = frappe.db.get_value(
			"Its Your Profile Settings",
			"Its Your Profile Settings",
			["send_welcome_email", "welcome_email_account"],
		) or (0, None)
	except Exception:
		return False, None  # settings not migrated yet
	return bool(frappe.utils.cint(enabled)), account


def make_profile_route(when):
	"""Next public page address for a card made at `when`. One counter per year (Frappe's Series
	table, key "iyp-<year>-"), so numbers never repeat and each year starts at 00001."""
	from frappe.model.naming import getseries

	number = getseries(f"iyp-{when.year}-", 5)
	return f"business/iyp-{when.year}-{when.month:02d}-{number}"


def clean_url(url, label):
	"""Add https:// when missing, and allow only web links (no javascript: etc. on a public page)."""
	url = (url or "").strip()
	if url and "://" not in url:
		url = "https://" + url
	if url and not url.lower().startswith(("http://", "https://")):
		frappe.throw(frappe._("{0} must be a web address").format(label))
	return url or None


class BusinessProfile(WebsiteGenerator):
	def validate(self):
		# A profile created from a card upload has no company name until the scan finishes
		if not self.company_name and not (self.visiting_card or self.visiting_card_back):
			frappe.throw(frappe._("Please enter a Company Name or upload a Visiting Card"))

		self.validate_urls()
		self.set_google_maps_url()
		self.keep_welcome_fields()

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
			if all(frappe.cache.get_value(card_read_cache_key(url)) for url in new_sides):
				self.card_scan_status = "Completed"
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

	def keep_welcome_fields(self):
		"""These change only when the email is sent (db_set), so a form opened earlier and saved
		with stale values must not reset them and trigger a second email."""
		before = None if self.is_new() else self.get_doc_before_save()
		if before:
			for fieldname in WELCOME_FIELDS:
				self.set(fieldname, before.get(fieldname))

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
			self.google_maps_url = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(query)

	def make_route(self):
		"""business/iyp-<year>-<month>-<5-digit number>, e.g. business/iyp-2026-10-00001.
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

		# Automatic welcome: only when switched on, once per business, and only when the email is
		# new on this save (a new profile, or a card scan that just filled it). Existing businesses
		# are not mailed when the switch is turned on; use the Desk button for those.
		enabled, _account = welcome_email_settings()
		if enabled and not self.welcome_email_sent and self.has_value_changed("email") and self.ready_for_welcome():
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

		_enabled, account = welcome_email_settings()
		sender = frappe.db.get_value("Email Account", account, "email_id") if account else None

		frappe.sendmail(
			recipients=[self.email],
			sender=sender,
			subject=frappe._("Your business is live: {0}").format(self.company_name),
			template="business_profile_welcome",
			args={
				"doc": self,
				"details": self.get_details_for_email(),
				"page_url": frappe.utils.get_url(self.route),
				"edit_url": frappe.utils.get_url(f"/my-business/{self.name}/edit"),
			},
			reference_doctype=self.doctype,
			reference_name=self.name,
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
		context.no_cache = 1
		context.json_ld = self.get_json_ld()
		context.metatags = {
			"title": self.company_name,
			"description": frappe.utils.strip_html(self.ai_summary or "")[:300],
		}

	def get_json_ld(self):
		data = {
			"@context": "https://schema.org",
			"@type": "LocalBusiness",
			"name": self.company_name,
			"url": frappe.utils.get_url(self.route),
			"description": frappe.utils.strip_html(self.ai_summary or "") or None,
			"telephone": self.phone,
			"email": self.email,
			"foundingDate": str(self.established_year) if self.established_year else None,
			"numberOfEmployees": self.employee_range,
			"hasMap": self.google_maps_url,
			"sameAs": [u for u in (self.website_url, *(row.url for row in self.profile_links)) if u] or None,
			# Private cards (/private/files/...) can't be opened by visitors, so don't advertise them
			"image": frappe.utils.get_url(self.visiting_card)
			if (self.visiting_card or "").startswith("/files/")
			else None,
		}

		if self.address_line or self.city:
			data["address"] = {
				"@type": "PostalAddress",
				"streetAddress": self.address_line,
				"addressLocality": self.city,
				"addressRegion": self.state,
				"postalCode": self.pincode,
				"addressCountry": "IN",
			}

		if self.contact_person:
			data["employee"] = {"@type": "Person", "name": self.contact_person, "jobTitle": self.designation}

		data = {k: v for k, v in data.items() if v}
		# Escape "</" so the JSON can never close the surrounding <script> tag
		return json.dumps(data, indent=2, ensure_ascii=False).replace("</", "<\\/")
