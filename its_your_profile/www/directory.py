"""Directory at /directory: browse and search every published business profile.

CHANGE NOTE 2026-11-06: backend only. The live site keeps the directory private, so only System
Users (staff who use /app) can open it; visitors and business owners (Website Users) are refused.
Each business's own profile page stays public."""

import re

import frappe
from frappe import _
from frappe.utils import strip_html

from its_your_profile.its_your_profile.doctype.business_profile.business_profile import readable_on_white
from its_your_profile.portal import redirect

no_cache = 1
sitemap = 0  # keep it out of sitemap.xml, so search engines are not pointed at it


def is_backend_user() -> bool:
	"""True for staff who use the desk (/app): logged in, and a System User."""
	user = frappe.session.user
	return user != "Guest" and frappe.get_cached_value("User", user, "user_type") == "System User"

NATURES = ("Service", "Manufacturing", "Hybrid/Trading")
PAGE_SIZE = 60


def get_context(context):
	if not is_backend_user():
		if frappe.session.user == "Guest":
			# Staff who are not logged in yet: send them to log in, then back here
			redirect("/login?redirect-to=/directory")  # temporary (302), see portal.redirect
		frappe.throw(_("The directory is only available to the It's Your Profile team."), frappe.PermissionError)

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
			"phone",
			"hide_phone",
		],
		order_by="creation desc",
		limit_page_length=PAGE_SIZE,
	)
	for b in businesses:
		text = b.about_business or strip_html(b.ai_summary or "")
		b.summary = text if len(text) <= 200 else text[:200].rsplit(" ", 1)[0] + "…"
		b.colour = readable_on_white(b.name_color or b.brand_color)
		# No Call button for a number the owner keeps private (2026-11-07)
		b.call = re.split(r"[/,]", b.phone)[0] if b.phone and not b.hide_phone else None

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
