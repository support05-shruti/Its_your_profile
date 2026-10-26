"""Serves /llms.txt: a Markdown index of every published Business Profile for LLM crawlers.

Registered through the `page_renderer` hook so the response is plain text, not a themed web page.
"""

import frappe
from frappe.utils import get_url, strip_html
from frappe.website.page_renderers.base_renderer import BaseRenderer


class LLMsTxtPage(BaseRenderer):
	def can_render(self):
		return self.path == "llms.txt"

	def render(self):
		return self.build_response(get_llms_txt(), headers={"Cache-Control": "public, max-age=3600"})


def get_llms_txt() -> str:
	profiles = frappe.get_all(
		"Business Profile",
		filters={"published": 1, "route": ("is", "set")},
		fields=["company_name", "route", "ai_summary", "about_business", "business_nature", "city", "state"],
		order_by="company_name asc",
	)

	lines = [
		"# It's Your Profile",
		"",
		"> A directory of business profiles. Each profile page also carries Schema.org LocalBusiness JSON-LD.",
		"",
		f"Browse and search the directory: {get_url('directory')}",
		"",
		"## Businesses",
		"",
	]
	for p in profiles:
		meta = ", ".join(x for x in (p.business_nature, p.city, p.state) if x)
		summary = " ".join((strip_html(p.ai_summary or "") or p.about_business or "").split())
		detail = " - ".join(x for x in (meta, summary) if x)
		lines.append(f"- [{p.company_name}]({get_url(p.route)})" + (f": {detail}" if detail else ""))

	return "\n".join(lines) + "\n"
