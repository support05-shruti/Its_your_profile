"""Business Directory at /directory: every business whose card we scanned, open to everyone.

CHANGE 2026-11-16: PUBLIC now, no login (it was staff-only). Anyone, and AI assistants and search
engines, can browse and search all published businesses with their details: logo, what they do,
city, contact person, phone (unless the owner keeps it private), email, website and LinkedIn, with
a link to each business's full page. Listed in sitemap.xml, with an ItemList for AI search.
"""

import html
import json
import re

import frappe
from frappe import _
from frappe.utils import get_url, strip_html

from its_your_profile.its_your_profile.doctype.business_profile.business_profile import (
	readable_on_white,
	whatsapp_number,
)

no_cache = 1
sitemap = 1

NATURES = ("Service", "Manufacturing", "Hybrid/Trading")
PAGE_SIZE = 200


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
			["segment", "like", like],
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
			"name", "company_name", "route", "business_nature", "segment", "city", "state",
			"about_business", "ai_summary", "name_color", "brand_color", "company_logo",
			"contact_person", "designation", "phone", "hide_phone", "email", "website_url",
		],
		order_by="company_name asc",
		limit_page_length=PAGE_SIZE,
	)

	linkedin = {}
	if businesses:
		for row in frappe.get_all(
			"Business Profile Link",
			filters={
				"parenttype": "Business Profile",
				"parent": ("in", [b.name for b in businesses]),
				"platform": "LinkedIn",
			},
			fields=["parent", "url"],
			order_by="idx asc",
		):
			linkedin.setdefault(row.parent, row.url)

	for b in businesses:
		# html.unescape: the AI summary is stored as HTML, so "&" came out as "&amp;" (2026-11-16)
		text = html.unescape(strip_html(b.ai_summary or "")) or b.about_business or ""
		text = " ".join(text.split())
		b.summary = text if len(text) <= 220 else text[:220].rsplit(" ", 1)[0] + "…"
		b.colour = readable_on_white(b.name_color or b.brand_color) or "#3B2E7E"
		b.logo = b.company_logo if (b.company_logo or "").startswith("/files/") else None
		words = [w for w in (b.company_name or "?").split() if w not in ("&", "-", "|")][:2]
		b.initials = "".join(w[0] for w in words).upper() or "?"
		b.place = ", ".join(x for x in (b.city, b.state) if x)
		b.person = " · ".join(x for x in (b.contact_person, b.designation) if x)
		# Phone only when the owner keeps it public (2026-11-07)
		b.call = re.split(r"[/,]", b.phone)[0].strip() if b.phone and not b.hide_phone else None
		b.wa = whatsapp_number(b.call) if b.call else None
		site = (b.website_url or "").strip()
		b.site_href = site if site.startswith(("http://", "https://")) else ("https://" + site if site else None)
		b.site_text = re.sub(r"^https?://(www\.)?", "", site).rstrip("/")
		b.linkedin = linkedin.get(b.name)
		b.url = "/" + b.route

	total = frappe.db.count("Business Profile", {"published": 1, "route": ("is", "set")})
	context.update(
		{
			"title": _("Business Directory"),
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
			"total": total,
			"filtered": bool(q or nature or city),
			"metatags": {
				"title": _("Business Directory · It's Your Profile"),
				"description": _(
					"All {0} businesses on It's Your Profile, with what they do, where they are and how to contact them."
				).format(total),
				"image": get_url("/assets/its_your_profile/images/iyp-logo.png"),
			},
			"canonical_url": get_url("/directory"),
			"item_list": json.dumps(item_list(businesses)).replace("</", "<\\/"),
		}
	)


def item_list(businesses):
	"""schema.org ItemList: tells AI assistants and search engines what this page lists."""
	return {
		"@context": "https://schema.org",
		"@type": "ItemList",
		"name": "It's Your Profile business directory",
		"numberOfItems": len(businesses),
		"itemListElement": [
			{
				"@type": "ListItem",
				"position": i,
				"item": {
					"@type": "LocalBusiness",
					"name": b.company_name,
					"url": get_url(b.url),
					**({"telephone": b.call} if b.call else {}),
					**(
						{"address": {"@type": "PostalAddress", "addressLocality": b.city, "addressRegion": b.state}}
						if b.city
						else {}
					),
				},
			}
			for i, b in enumerate(businesses, 1)
		],
	}
