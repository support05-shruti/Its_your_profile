"""Monthly WhatsApp report to each business on It's Your Profile.

Created: 2026-11-05.

On the 1st of each month (scheduler_events in hooks.py) last month's Profile Visit rows are added
up per Business Profile, and each business with activity gets one WhatsApp message on the first
number shown on its page, sent through the WhatsApp Cloud API with a Meta-approved template.

Only what can be measured honestly is reported:
- AI crawler reads: AI bots fetching the page or its Markdown copy (search crawlers not counted).
- Visitors from AI apps: people whose referrer or utm_source was ChatGPT, Perplexity...  This is a
  minimum, since many mobile AI apps send no referrer and show up as "Direct".
- Page views and taps on WhatsApp, Call and Save Contact.

Nothing is sent until "Send Monthly WhatsApp Report" is ticked in Its Your Profile Settings.
"""

import re

import frappe
import requests
from frappe.query_builder.functions import Count
from frappe.utils import add_months, get_first_day, get_url, nowdate

from its_your_profile.its_your_profile.doctype.business_profile.business_profile import whatsapp_number
from its_your_profile.tracking import AI_SOURCES

SETTINGS = "Its Your Profile Settings"
GRAPH_URL = "https://graph.facebook.com"
# A report already sent is not sent again if the job is re-run (e.g. a manual test) in the same month
SENT_KEY_DAYS = 40


def send_monthly_reports():
	"""Scheduler entry point: queue one report per business that had activity last month."""
	settings = frappe.get_single(SETTINGS)
	if not settings.send_monthly_whatsapp_report:
		return

	start = get_first_day(add_months(nowdate(), -1))
	end = get_first_day(nowdate())
	month = start.strftime("%B %Y")
	for profile, stats in monthly_stats(start, end).items():
		frappe.enqueue(
			"its_your_profile.monthly_report.send_report",
			profile=profile,
			stats=stats,
			month=month,
			period=str(start),
			# Same job id while one is queued, so a double run doesn't send twice
			job_id=f"iyp-monthly-report:{profile}:{start}",
			deduplicate=True,
		)


def monthly_stats(start, end) -> dict:
	"""{profile: counts} for Profile Visit rows created from start (inclusive) to end (exclusive)."""
	visit = frappe.qb.DocType("Profile Visit")
	rows = (
		frappe.qb.from_(visit)
		.select(visit.business_profile, visit.event, visit.visitor, visit.source, Count("*").as_("n"))
		.where((visit.creation >= start) & (visit.creation < end) & visit.business_profile.isnotnull())
		.groupby(visit.business_profile, visit.event, visit.visitor, visit.source)
	).run(as_dict=True)

	stats = {}
	for row in rows:
		s = stats.setdefault(
			row.business_profile, {"crawls": 0, "ai_visits": 0, "views": 0, "whatsapp": 0, "calls": 0, "saves": 0}
		)
		if row.visitor == "AI Crawler":
			s["crawls"] += row.n
		elif row.visitor != "Person":
			continue  # Google / Bing crawlers: not part of this report
		elif row.event == "View":
			s["views"] += row.n
			if row.source in AI_SOURCES:
				s["ai_visits"] += row.n
		elif row.event == "WhatsApp":
			s["whatsapp"] += row.n
		elif row.event == "Call":
			s["calls"] += row.n
		elif row.event == "Save Contact":
			s["saves"] += row.n

	# A month with only search-crawler visits would be a report of zeros
	return {profile: s for profile, s in stats.items() if any(s.values())}


def send_report(profile: str, stats: dict, month: str, period: str):
	"""Send one business its report. Failures go to the Error Log and never stop the other reports."""
	sent_key = f"iyp_monthly_report_sent:{profile}:{period}"
	if frappe.cache.get_value(sent_key):
		return

	values = frappe.db.get_value(
		"Business Profile", profile, ["company_name", "phone", "route", "published"], as_dict=True
	)
	if not values or not values.published or not values.route:
		return
	# Same rule as the page's WhatsApp button: the first of the numbers separated by / or ,
	first_phone = next((p for p in re.split(r"[/,]", values.phone or "") if p), None)
	to = whatsapp_number(first_phone)
	if not to:
		return

	settings = frappe.get_single(SETTINGS)
	version = (settings.whatsapp_api_version or "").strip().strip("/")
	url = "/".join(p for p in (GRAPH_URL, version, settings.whatsapp_phone_number_id, "messages") if p)
	params = [
		values.company_name or profile,
		month,
		stats.get("crawls", 0),
		stats.get("ai_visits", 0),
		stats.get("views", 0),
		stats.get("whatsapp", 0),
		stats.get("calls", 0),
		stats.get("saves", 0),
		get_url(values.route),
	]
	payload = {
		"messaging_product": "whatsapp",
		"to": to,
		"type": "template",
		"template": {
			"name": settings.whatsapp_template_name or "monthly_profile_report",
			"language": {"code": settings.whatsapp_template_language or "en"},
			"components": [{"type": "body", "parameters": [{"type": "text", "text": str(p)} for p in params]}],
		},
	}

	response = None
	try:
		response = requests.post(
			url,
			json=payload,
			headers={"Authorization": f"Bearer {settings.get_password('whatsapp_access_token')}"},
			timeout=15,
		)
		response.raise_for_status()
	except Exception:
		# Meta's error body says why (template not approved, wrong number...); the token is not logged
		frappe.log_error(
			title=f"Monthly WhatsApp report not sent: {profile}",
			message=f"{frappe.get_traceback()}\n\nResponse: {response.text if response is not None else '-'}",
		)
		return

	frappe.cache.set_value(sent_key, 1, expires_in_sec=SENT_KEY_DAYS * 24 * 60 * 60)
