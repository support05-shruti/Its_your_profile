"""Public directory at /directory: browse and search every published business profile."""

import frappe
from frappe.utils import strip_html

from its_your_profile.its_your_profile.doctype.business_profile.business_profile import readable_on_white

no_cache = 1

NATURES = ("Service", "Manufacturing", "Hybrid/Trading")
PAGE_SIZE = 60


def get_context(context):
	q = (frappe.form_dict.get("q") or "").strip()[:100]
	nature = frappe.form_dict.get("nature") or ""
	city = (frappe.form_dict.get("city") or "").strip()[:60]

	filters = {"published": 1, "route": ("is", "set")}
	if nature in NATURES:
		filters["business_nature"] = nature
	if city:
		filters["city"] = city

	or_filters = None
	if q:
		like = f"%{q}%"
		or_filters = [
			["company_name", "like", like],
			["about_business", "like", like],
			["ai_summary", "like", like],
			["contact_person", "like", like],
			["city", "like", like],
		]

	businesses = frappe.get_all(
		"Business Profile",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"company_name",
			"route",
			"business_nature",
			"city",
			"state",
			"about_business",
			"ai_summary",
			"name_color",
			"brand_color",
		],
		order_by="creation desc",
		limit_page_length=PAGE_SIZE,
	)
	for b in businesses:
		text = b.about_business or strip_html(b.ai_summary or "")
		b.summary = text if len(text) <= 200 else text[:200].rsplit(" ", 1)[0] + "…"
		b.colour = readable_on_white(b.name_color or b.brand_color)

	context.update(
		{
			"title": "Business Directory",
			"businesses": businesses,
			"q": q,
			"nature": nature if nature in NATURES else "",
			"city": city,
			"natures": NATURES,
			"cities": sorted(
				c
				for c in frappe.get_all(
					"Business Profile", filters={"published": 1}, pluck="city", distinct=True
				)
				if c
			),
			"total": frappe.db.count("Business Profile", {"published": 1, "route": ("is", "set")}),
		}
	)
