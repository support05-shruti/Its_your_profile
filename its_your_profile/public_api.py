"""Public, read-only business data for other websites (2026-11-12), e.g. the separate directory site
(app iyp_directory). No login needed. Only PUBLISHED businesses, and only what their public page
already shows: a phone number the owner keeps private is never included, nor are internal fields
(visiting card photos, owner, email-sent flags...).

    GET /api/method/its_your_profile.public_api.businesses        → every published business
    GET /api/method/its_your_profile.public_api.business?route=business/iyp-26-11-00016

Answers are cached for 10 minutes and rate-limited, so other sites can call it freely.
"""

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import get_url

CACHE_KEY = "iyp_public_businesses"
CACHE_SECONDS = 600


def public_record(doc) -> dict:
	"""One business as other websites may show it."""
	return {
		"route": doc.route,
		"url": get_url(doc.route),
		"company_name": doc.company_name,
		"segment": doc.segment,
		"business_nature": doc.business_nature,
		"summary": doc.get_summary(),
		"services": doc.get_services(),
		"established_year": doc.established_year or None,
		"employee_range": doc.employee_range,
		"contact_person": doc.contact_person,
		"designation": doc.designation,
		"phone": doc.public_phone,
		"email": doc.email,
		"website": doc.website_url,
		"address": ", ".join(x for x in (doc.address_line, doc.city, doc.state, doc.pincode) if x),
		"city": doc.city,
		"state": doc.state,
		"map_url": doc.google_maps_url,
		"logo": doc.get_logo_url(),
		"brand_color": doc.brand_color,
		"links": [{"label": row.label or row.platform, "url": row.url} for row in doc.profile_links if row.url],
		"faqs": [{"question": f.question, "answer": f.answer} for f in doc.get_page_faqs()],
		"updated": frappe.utils.getdate(doc.modified).isoformat() if doc.modified else None,
	}


def all_records() -> list[dict]:
	cached = frappe.cache.get_value(CACHE_KEY)
	if cached is not None:
		return cached
	names = frappe.get_all(
		"Business Profile",
		filters={"published": 1, "route": ("is", "set"), "company_name": ("is", "set")},
		pluck="name",
		order_by="company_name asc",
	)
	records = [public_record(frappe.get_doc("Business Profile", name)) for name in names]
	frappe.cache.set_value(CACHE_KEY, records, expires_in_sec=CACHE_SECONDS)
	return records


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=120, seconds=60)
def businesses():
	"""Every published business, A to Z."""
	return all_records()


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=60)
def business(route: str):
	"""One published business by its page address (business/iyp-...)."""
	route = (route or "").strip("/")
	for record in all_records():
		if record["route"] == route:
			return record
	frappe.throw(frappe._("Business not found"), frappe.DoesNotExistError)
