"""Owner's notifications at /notifications: who viewed or tapped their page, and which AI read it.

The alerts are Notification Logs written by tracking.notify_owner, so Desk users see the same
ones in the bell. Opening this page marks them read.
"""

import re

import frappe
from frappe import _
from frappe.utils import add_days, format_date, getdate, now_datetime, pretty_date

from its_your_profile.portal import redirect
from its_your_profile.tracking import AI_SOURCES, ALERTS, LEADS

no_cache = 1

LIMIT = 100
WEEK = 7
SEEN_KEY = "iyp_dashboard_seen"  # user → when they last opened the dashboard (for "new" dots)


def get_context(context):
	user = frappe.session.user
	if user == "Guest":
		redirect("/login?redirect-to=/notifications")  # temporary (302), see portal.redirect

	# CHANGE NOTE 2026-11-06: this page is now the owner's dashboard (where they land after login),
	# so it also shows who they are and their business page(s) with View / Edit / Share.
	# CHANGE NOTE 2026-11-12: staff (System Users) land here too now, and their own account owns no
	# pages, so they saw "You don't have a business page yet". Staff see every business instead
	# (an overview: all cards, all visits, totals); owners still see only their own.
	is_staff = frappe.get_cached_value("User", user, "user_type") == "System User"
	profiles = frappe.get_all(
		"Business Profile",
		filters={} if is_staff else {"owner": user},
		fields=[
			"name", "route", "company_name", "city", "state", "business_nature", "segment", "company_logo",
			"published", "brand_color", "contact_person", "designation", "phone", "hide_phone", "email", "website_url",
		],
		order_by="creation desc",
	)
	routes = {p.name: p.route for p in profiles}
	for p in profiles:
		p.page_url = "/" + p.route if p.published and p.route else None
		p.edit_url = f"/my-business/{p.name}/edit"
		p.logo = p.company_logo if (p.company_logo or "").startswith("/files/") else None
		words = [w for w in (p.company_name or "?").split() if w not in ("&", "-", "|")][:2]
		p.initials = "".join(w[0] for w in words).upper() or "?"
		# Cover colour of the dashboard card (2026-11-07): the card's brand colour, else our indigo
		p.cover = p.brand_color if re.fullmatch(r"#[0-9A-Fa-f]{6}", p.brand_color or "") else "#3B2E7E"
		# 2026-11-07: each card lists the company's own details, so every business shows its information
		p.place = ", ".join(x for x in (p.city, p.state) if x)
		p.person = " · ".join(x for x in (p.contact_person, p.designation) if x)
		site = (p.website_url or "").strip()
		p.site_href = site if site.startswith(("http://", "https://")) else ("https://" + site if site else None)
		p.site_text = re.sub(r"^https?://(www\.)?", "", site).rstrip("/")

	# CHANGE NOTE 2026-11-07: "Who visited your page" is built from the visit records themselves
	# (Profile Visit), not from the bell alerts, which are sent at most once per hour per kind and
	# so missed most visits. Every view and tap is listed, with where the visitor came from.
	# "New" means since the owner last opened this page.
	names = [p.name for p in profiles]
	companies = {p.name: p.company_name for p in profiles} if len(profiles) > 1 else {}
	last_seen = frappe.cache.hget(SEEN_KEY, user)
	visits = (
		frappe.get_all(
			"Profile Visit",
			filters={"business_profile": ("in", names)},
			fields=["event", "visitor", "source", "crawler", "creation", "business_profile"],
			order_by="creation desc",
			limit_page_length=LIMIT,
		)
		if names
		else []
	)
	days = []
	unread = 0
	for visit in visits:
		item = describe_visit(visit, companies)
		item.when = pretty_date(visit.creation)
		item.url = "/" + routes[visit.business_profile] if routes.get(visit.business_profile) else None
		item.read = not (last_seen and visit.creation > last_seen)
		unread += 0 if item.read else 1
		label = day_label(visit.creation)
		if not days or days[-1]["label"] != label:
			days.append({"label": label, "alerts": []})
		days[-1]["alerts"].append(item)
	frappe.cache.hset(SEEN_KEY, user, now_datetime())

	# The bell's alerts count as seen once the owner has looked here
	if frappe.db.exists("Notification Log", {"for_user": user, "document_type": "Business Profile", "read": 0}):
		frappe.db.set_value(
			"Notification Log",
			{"for_user": user, "document_type": "Business Profile", "read": 0},
			"read",
			1,
			update_modified=False,
		)
		# Pages are GET requests, which Frappe rolls back
		frappe.db.commit()

	context.update(
		{
			"title": _("My Dashboard"),
			"is_staff": is_staff,
			"days": days,
			"unread": unread,
			"has_profile": bool(profiles),
			"profiles": profiles,
			"full_name": frappe.utils.get_fullname(user),
			"user_email": user,
			"week": week_counts([p.name for p in profiles]),
			# 2026-11-07: views per day for the bar chart, and how complete the main page is
			"chart": daily_views([p.name for p in profiles]),
			# Page completeness is advice for an owner about their own page, not for the staff overview
			"strength": page_strength(profiles[0].name) if profiles and not is_staff else None,
			"today": format_date(getdate(), "EEEE, d MMMM"),
		}
	)


def daily_views(names):
	"""Views on each of the last 7 days (oldest first), with bar heights for the dashboard chart."""
	today = getdate()
	counts = {}
	if names:
		rows = frappe.db.sql(
			"""select date(creation) as day, count(*) as views from `tabProfile Visit`
			where business_profile in %(names)s and event = 'View' and creation >= %(since)s
			group by date(creation)""",
			{"names": tuple(names), "since": add_days(today, -(WEEK - 1))},
			as_dict=True,
		)
		counts = {getdate(r.day): r.views for r in rows}
	days = [add_days(today, -i) for i in range(WEEK - 1, -1, -1)]
	top = max([counts.get(d, 0) for d in days] + [1])
	return [
		{
			"label": _("Today") if d == today else format_date(d, "EEE"),
			"views": counts.get(d, 0),
			"height": max(6, round(counts.get(d, 0) * 100 / top)),
			"today": d == today,
		}
		for d in days
	]


# What makes a page strong for customers and AI search, with the tip shown when it's missing
STRENGTH_CHECKS = (  # tips are translated when the page is built, not at import
	("company_logo", "Add your logo"),
	("phone", "Add a phone number"),
	("email", "Add an email address"),
	("website_url", "Add your website"),
	("address_line", "Add your address"),
	("about_business", "Say what your business does"),
	("services", "List your products or services"),
	("contact_person", "Add the contact person"),
)


def page_strength(name):
	"""How complete the owner's page is (0-100), and up to three tips for what to add next."""
	doc = frappe.db.get_value(
		"Business Profile", name, [field for field, _tip in STRENGTH_CHECKS] + ["ai_summary"], as_dict=True
	)
	if not doc:
		return None
	# The AI summary from the website also tells customers what the business does
	if not doc.about_business and doc.ai_summary:
		doc.about_business = doc.ai_summary
	# Generated initials are a stand-in, not the business's logo (2026-11-12): keep asking for one
	from its_your_profile.tasks import GENERATED_LOGO_NAME

	if GENERATED_LOGO_NAME.match(doc.company_logo or ""):
		doc.company_logo = None
	# LinkedIn is compulsory (2026-11-07), so it is checked on its own
	has_linkedin = frappe.db.count(
		"Business Profile Link", {"parent": name, "parenttype": "Business Profile", "platform": "LinkedIn"}
	)
	checks = [(bool(str(doc.get(field) or "").strip()), _(tip)) for field, tip in STRENGTH_CHECKS]
	checks.insert(0, (bool(has_linkedin), _("Add your LinkedIn page (required)")))
	done = sum(1 for ok, _tip in checks if ok)
	return {"percent": round(done * 100 / len(checks)), "tips": [tip for ok, tip in checks if not ok][:3]}


def week_counts(names):
	if not names:
		return {"views": 0, "leads": 0, "ai": 0}
	since = add_days(now_datetime(), -WEEK)
	base = {"business_profile": ("in", names), "creation": (">=", since)}
	return {
		"views": frappe.db.count("Profile Visit", {**base, "event": "View"}),
		"leads": frappe.db.count("Profile Visit", {**base, "event": ("in", LEADS)}),
		"ai": frappe.db.count("Profile Visit", {**base, "visitor": "AI Crawler"}),
	}


def day_label(when):
	gap = (getdate() - getdate(when)).days
	if gap == 0:
		return _("Today")
	if gap == 1:
		return _("Yesterday")
	return format_date(when)


def describe_visit(visit, companies=None):
	"""One line for the activity feed: an icon, what happened, where the visitor came from, and its
	kind for the filter chips (lead = a call or chat tap, ai = AI read it or sent the visitor)."""
	if visit.visitor == "AI Crawler":
		icon, kind, text = "🤖", "ai", _("{0} read your page").format(visit.crawler or _("An AI assistant"))
	elif visit.visitor == "Search Crawler":
		icon, kind, text = "🔎", "ai", _("{0} checked your page").format(visit.crawler or _("A search engine"))
	else:
		icon, did = ALERTS.get(visit.event, ("👀", "visited your page"))
		kind = "lead" if visit.event in LEADS else ("ai" if visit.source in AI_SOURCES else "view")
		text = _("Someone {0}").format(_(did))
		if visit.source and visit.source not in ("Direct", "It's Your Profile"):
			text += " · " + _("from {0}").format(visit.source)
	if companies and companies.get(visit.business_profile):
		text += " · " + companies[visit.business_profile]
	return frappe._dict(icon=icon, glyph=GLYPHS.get(icon, "eye"), kind=kind, subject=text)


# The dashboard draws line icons (an SVG sprite in notifications.html) instead of the alert emoji
GLYPHS = {
	"👀": "eye", "📞": "phone", "💬": "chat", "✉️": "mail", "📍": "pin", "🌐": "globe",
	"📇": "user", "🔗": "link", "🤖": "bot", "🔎": "search",
}
