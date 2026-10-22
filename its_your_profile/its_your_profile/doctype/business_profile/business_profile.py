# Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd and contributors
# For license information, please see license.txt

import json

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


class BusinessProfile(WebsiteGenerator):
	def validate(self):
		# A profile created from a card upload has no company name until the scan finishes
		if not self.company_name and not (self.visiting_card or self.visiting_card_back):
			frappe.throw(frappe._("Please enter a Company Name or upload a Visiting Card"))

		self.validate_urls()

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

	def validate_urls(self):
		for fieldname in ("website_url", "google_maps_url", "linkedin_url", "facebook_url"):
			url = (self.get(fieldname) or "").strip()
			if url and "://" not in url:
				url = "https://" + url
			if url and not url.lower().startswith(("http://", "https://")):
				frappe.throw(frappe._("{0} must be a web address").format(self.meta.get_label(fieldname)))
			self.set(fieldname, url or None)

	def make_route(self):
		route = super().make_route()
		base, suffix = route, 1
		while frappe.db.exists("Business Profile", {"route": route, "name": ("!=", self.name)}):
			suffix += 1
			route = f"{base}-{suffix}"
		return route

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
			"sameAs": [u for u in (self.website_url, self.linkedin_url, self.facebook_url) if u] or None,
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
