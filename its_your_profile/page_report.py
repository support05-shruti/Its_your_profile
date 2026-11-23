"""Page report email: the owner's dashboard in their inbox, like LinkedIn's page analytics (2026-11-23).

- Paid businesses (Business Profile → Plan → Paid Plan, Paid Until not passed): every morning,
  for yesterday.
- Everyone else: every Monday morning, for the last 7 days.

Same layout as the dashboard (/notifications): the three numbers with the change from the period
before, "Views this week" (bar chart), "Who visited your page" (the activity feed), and "Page
completeness" with EVERY item still missing. Sent to the owner's login email, or the business
email when staff own the page. A business with no activity in two periods gets nothing.

Separate from monthly_report.py (WhatsApp, off by default). Switch off without a deploy:
site_config "iyp_page_report": 0.
"""

import frappe
from frappe import _
from frappe.utils import add_days, format_date, get_url, getdate, today, validate_email_address

from its_your_profile.tracking import AI_SOURCES, LEADS

FEED_LIMIT = 15  # lines of "Who visited your page" in one email
TAPS = set(LEADS) | {"Website"}


def is_paid(doc) -> bool:
	if not doc.get("paid_plan"):
		return False
	return not doc.get("paid_until") or getdate(doc.paid_until) >= getdate(today())


def send_daily_reports():
	"""Every morning: paid businesses, yesterday."""
	queue_reports(paid=True, days=1)


def send_weekly_reports():
	"""Monday morning: unpaid businesses, the last 7 days."""
	queue_reports(paid=False, days=7)


def queue_reports(paid: bool, days: int):
	if not frappe.conf.get("iyp_page_report", 1):
		return
	if not frappe.db.has_column("Business Profile", "paid_plan"):
		return  # before `bench migrate`
	end = getdate(today())  # today 00:00, not included
	start = add_days(end, -days)
	for row in frappe.get_all(
		"Business Profile",
		filters={"published": 1, "route": ("is", "set")},
		fields=["name", "paid_plan", "paid_until"],
	):
		if is_paid(row) != paid:
			continue
		frappe.enqueue(
			"its_your_profile.page_report.send_report",
			profile=row.name,
			start=str(start),
			end=str(end),
			queue="long",
			job_id=f"iyp-page-report:{row.name}:{start}:{days}",
			deduplicate=True,
		)


def visits_between(profile, start, end):
	return frappe.get_all(
		"Profile Visit",
		filters={"business_profile": profile, "creation": ["between", [start, add_days(end, -1)]]},
		fields=[
			"event", "visitor", "visitor_name", "visitor_email", "source", "crawler", "creation",
			"business_profile", "visitor_company", "visitor_city",
		],
		order_by="creation desc",
		limit_page_length=0,
	)


def counts(profile, visits, start, end) -> frappe._dict:
	"""The dashboard's three numbers (views, calls & chats incl. enquiries, AI visits)."""
	views = sum(1 for v in visits if v.event == "View" and v.visitor in ("Person", "Known Person"))
	taps = sum(1 for v in visits if v.event in TAPS and v.visitor in ("Person", "Known Person"))
	ai = sum(1 for v in visits if v.visitor == "AI Crawler" or (v.event == "View" and v.source in AI_SOURCES))
	enquiries = frappe.db.count(
		"Business Enquiry", {"business_profile": profile, "creation": ["between", [start, add_days(end, -1)]]}
	)
	return frappe._dict(views=views, leads=taps + enquiries, ai=ai)


def change(now: int, before: int) -> str | None:
	"""'▲ 133%', '▼ 20%', 'New' or None, like LinkedIn."""
	if now == before:
		return None
	if not before:
		return _("New")
	pct = round((now - before) * 100 / before)
	return f"▲ {pct}%" if pct > 0 else f"▼ {abs(pct)}%"


def chart(profile, end):
	"""Views on each of the 7 days before `end` (oldest first), with bar heights in pixels."""
	start = add_days(end, -7)
	rows = frappe.db.sql(
		"""select date(creation) as day, count(*) as views from `tabProfile Visit`
		where business_profile = %(p)s and event = 'View' and creation >= %(start)s and creation < %(end)s
		group by date(creation)""",
		{"p": profile, "start": start, "end": end},
		as_dict=True,
	)
	by_day = {getdate(r.day): r.views for r in rows}
	days = [add_days(start, i) for i in range(7)]
	top = max([by_day.get(d, 0) for d in days] + [1])
	return [
		{"label": format_date(d, "EEE"), "views": by_day.get(d, 0), "height": max(4, round(by_day.get(d, 0) * 90 / top))}
		for d in days
	]


def feed(visits):
	"""'Who visited your page', grouped by day, with the dashboard's own wording."""
	from its_your_profile.www.notifications import describe_visit

	days = []
	for visit in visits[:FEED_LIMIT]:
		item = describe_visit(visit)
		item.time = visit.creation.strftime("%I:%M %p").lstrip("0")
		label = format_date(visit.creation, "EEEE, d MMMM")
		if not days or days[-1]["label"] != label:
			days.append({"label": label, "items": []})
		days[-1]["items"].append(item)
	return days


def email_link(path: str, content: str, campaign: str = "page_report", anchor: str = "") -> str:
	"""Like LinkedIn's email links: opens the exact place, and says which email and button was
	clicked (utm_source=iyp_email → source "Our email" in tracking.source_of)."""
	from urllib.parse import urlencode

	query = urlencode({"utm_source": "iyp_email", "utm_medium": "email", "utm_campaign": campaign, "utm_content": content})
	return f"{get_url(path)}?{query}" + (f"#{anchor}" if anchor else "")


def tip_links(doc, tips):
	"""Each missing item opens My information; the logo goes straight to the logo box."""
	edit = f"/my-business/{doc.name}/edit"
	return [
		{"text": tip, "url": email_link(edit, "missing_" + str(i), anchor="logo" if tip == _("Add your logo") else "")}
		for i, tip in enumerate(tips or [], 1)
	]


def recipient(doc) -> str | None:
	"""The owner's login email; when staff own the page (they create pages for others), the business email."""
	owner = doc.owner
	if owner and owner not in ("Guest", "Administrator"):
		user = frappe.db.get_value("User", owner, ["email", "user_type", "enabled"], as_dict=True)
		if user and user.enabled and user.user_type == "Website User" and validate_email_address(user.email):
			return user.email
	return validate_email_address(doc.email or "") or None


def scheduler_on() -> bool:
	try:
		from frappe.utils.scheduler import is_scheduler_disabled

		return not is_scheduler_disabled()
	except Exception:
		return False


def explain(profile: str | None = None, start: str | None = None, end: str | None = None, to: str | None = None):
	"""Staff check from the server (2026-11-23), prints why a report would or wouldn't go:
	bench --site <site> execute its_your_profile.page_report.explain --kwargs "{'to': 'me@x.com'}"
	With `to`, the report is sent to that address now (re-sent even if already sent), and the
	Email Queue status is shown. Without `profile`, the business with the most visits is used."""
	end_d = getdate(end or today())
	start_d = getdate(start) if start else add_days(end_d, -7)
	if not profile:
		row = frappe.db.sql(
			"""select business_profile from `tabProfile Visit` where business_profile is not null
			and creation >= %s group by business_profile order by count(*) desc limit 1""",
			add_days(end_d, -30),
		)
		profile = row[0][0] if row else frappe.db.get_value("Business Profile", {"published": 1}, "name")
	doc = frappe.get_doc("Business Profile", profile)
	visits = visits_between(profile, start_d, end_d)
	now = counts(profile, visits, start_d, end_d)
	out = {
		"profile": f"{profile} ({doc.company_name})",
		"period": f"{start_d} to {add_days(end_d, -1)}",
		"published": bool(doc.published and doc.route),
		"paid": is_paid(doc),
		"visits_in_period": len(visits),
		"views / calls & chats / ai": f"{now.views} / {now.leads} / {now.ai}",
		"owner": doc.owner,
		"would_send_to": recipient(doc),
		"outgoing_email_account": frappe.db.get_value("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}, "email_id"),
		"scheduler_enabled": scheduler_on(),
	}
	if to:
		frappe.cache.delete_value(f"iyp_page_report_sent:{profile}:{start_d}:{(end_d - start_d).days}")
		frappe.flags.iyp_report_to = to
		send_report(profile, str(start_d), str(end_d))
		frappe.db.commit()
		last = frappe.get_all(
			"Email Queue", filters={"reference_name": profile}, fields=["name", "status", "error", "creation"],
			order_by="creation desc", limit=1,
		)
		out["email_queue"] = last[0] if last else "nothing queued"
		error = frappe.get_all(
			"Error Log",
			filters={"method": f"Page report not sent: {profile}", "creation": (">=", add_days(frappe.utils.now_datetime(), -1))},
			fields=["error"], order_by="creation desc", limit=1,
		)
		if error:
			out["error"] = (error[0].error or "")[-1500:]
	for key, value in out.items():
		print(f"{key:28} {value}")
	return out


def send_report(profile: str, start: str, end: str):
	"""One business's report. Problems go to the Error Log and never stop the others."""
	start_d, end_d = getdate(start), getdate(end)
	days = (end_d - start_d).days
	sent_key = f"iyp_page_report_sent:{profile}:{start}:{days}"
	if frappe.cache.get_value(sent_key):
		return
	try:
		doc = frappe.get_doc("Business Profile", profile)
		if not doc.published or not doc.route:
			return
		visits = visits_between(profile, start_d, end_d)
		now = counts(profile, visits, start_d, end_d)
		before_start = add_days(start_d, -days)
		before = counts(profile, visits_between(profile, before_start, start_d), before_start, start_d)
		test_to = frappe.flags.iyp_report_to  # explain(to=...): a test copy, sent even with no activity
		if not test_to and not any((now.views, now.leads, now.ai, before.views, before.leads, before.ai, len(visits))):
			return  # nothing at all for two periods: no email full of zeros
		to = test_to or recipient(doc)
		if not to:
			return

		from its_your_profile.its_your_profile.doctype.business_profile.business_profile import (
			welcome_email_account,
		)
		from its_your_profile.www.notifications import page_strength

		daily = days == 1
		period = (
			format_date(start_d, "EEEE, d MMMM yyyy")
			if daily
			else f"{format_date(start_d, 'd MMM')} – {format_date(add_days(end_d, -1), 'd MMM yyyy')}"
		)
		account = welcome_email_account()
		strength = page_strength(profile, limit=None)
		frappe.sendmail(
			recipients=[to],
			sender=frappe.db.get_value("Email Account", account, "email_id") if account else None,
			subject=(_("Daily page report for {0}") if daily else _("Weekly page report for {0}")).format(
				doc.company_name or profile
			),
			template="page_report",
			args={
				"doc": doc,
				"daily": daily,
				"period": period,
				"now": now,
				"views_change": change(now.views, before.views),
				"leads_change": change(now.leads, before.leads),
				"ai_change": change(now.ai, before.ai),
				"chart": chart(profile, end_d),
				"feed": feed(visits),
				"more_visits": max(len(visits) - FEED_LIMIT, 0),
				"strength": strength,
				"tips": tip_links(doc, (strength or {}).get("tips")),
				"page_url": get_url(doc.route),
				"dashboard_url": email_link("/notifications", "dashboard_button"),
				"views_url": email_link("/notifications", "views_this_week", anchor="views"),
				"activity_url": email_link("/notifications", "who_visited", anchor="activity"),
				"paid": is_paid(doc),
			},
			reference_doctype="Business Profile",
			reference_name=profile,
			now=bool(test_to),  # a test copy goes out at once, so any sending error shows straight away
		)
		frappe.cache.set_value(sent_key, 1, expires_in_sec=(days + 1) * 24 * 60 * 60)
	except Exception:
		frappe.log_error(title=f"Page report not sent: {profile}")
