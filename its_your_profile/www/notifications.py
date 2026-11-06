"""Owner's notifications at /notifications: who viewed or tapped their page, and which AI read it.

The alerts are Notification Logs written by tracking.notify_owner, so Desk users see the same
ones in the bell. Opening this page marks them read.
"""

import frappe
from frappe import _
from frappe.utils import add_days, format_date, getdate, now_datetime, pretty_date

from its_your_profile.tracking import LEADS

no_cache = 1

LIMIT = 100
WEEK = 7


def get_context(context):
	user = frappe.session.user
	if user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/notifications"
		raise frappe.Redirect

	# CHANGE NOTE 2026-11-06: this page is now the owner's dashboard (where they land after login),
	# so it also shows who they are and their business page(s) with View / Edit / Share.
	profiles = frappe.get_all(
		"Business Profile",
		filters={"owner": user},
		fields=["name", "route", "company_name", "city", "state", "business_nature", "company_logo", "published"],
		order_by="creation desc",
	)
	routes = {p.name: p.route for p in profiles}
	for p in profiles:
		p.page_url = "/" + p.route if p.published and p.route else None
		p.edit_url = f"/my-business/{p.name}/edit"
		p.logo = p.company_logo if (p.company_logo or "").startswith("/files/") else None
		words = [w for w in (p.company_name or "?").split() if w not in ("&", "-", "|")][:2]
		p.initials = "".join(w[0] for w in words).upper() or "?"

	alerts = frappe.get_all(
		"Notification Log",
		filters={"for_user": user, "document_type": "Business Profile"},
		fields=["name", "subject", "document_name", "creation", "read"],
		order_by="creation desc",
		limit_page_length=LIMIT,
	)
	days = []
	for alert in alerts:
		alert.when = pretty_date(alert.creation)
		alert.url = "/" + routes[alert.document_name] if routes.get(alert.document_name) else None
		alert.kind = kind_of(alert.subject)
		label = day_label(alert.creation)
		if not days or days[-1]["label"] != label:
			days.append({"label": label, "alerts": []})
		days[-1]["alerts"].append(alert)

	unread = sum(1 for a in alerts if not a.read)
	if unread:
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
			"days": days,
			"unread": unread,
			"has_profile": bool(profiles),
			"profiles": profiles,
			"full_name": frappe.utils.get_fullname(user),
			"user_email": user,
			"week": week_counts([p.name for p in profiles]),
		}
	)


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


def kind_of(subject):
	"""Colour of the alert: a lead, an AI visit or a plain view."""
	if subject.startswith("🤖"):
		return "ai"
	if subject.startswith("👀"):
		return "view"
	return "lead"
