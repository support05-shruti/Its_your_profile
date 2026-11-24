"""Leads from business pages (2026-11-14): "Get a call back" and "Send a message".

A visitor leaves their name and phone (and, for a message, an email and a few lines) on a business
page. We save it as a Business Enquiry and tell the owner straight away: a bell alert (the same
Notification Log the visit alerts use, so it shows on /notifications) and an email. The owner sees
every lead on their dashboard and marks it "Contacted" once they have called back.

The visitor shares these details by choice, so unlike page views we know who they are.
Spam guards: a hidden field that only bots fill in, and a per-IP limit of a few sends an hour.
"""

import re

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import escape_html, get_url, validate_email_address

from its_your_profile.tracking import counts_as_visitor, source_of

KINDS = ("Callback", "Message")
PHONE = re.compile(r"^\+?[0-9][0-9 \-()]{6,18}$")


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60 * 60)  # 2026-11-24: per IP; was 5, a demo room on one Wi-Fi shares it
def submit(
	profile: str,
	kind: str,
	visitor_name: str,
	phone: str | None = None,
	email: str | None = None,
	message: str | None = None,
	company_website: str | None = None,
	referrer: str | None = None,
	utm: str | None = None,
):
	"""Called by the form on a business page. Returns {"ok": True} or throws a readable message."""
	# Hidden "company_website" field: people never see it, bots fill every field in
	if company_website:
		return {"ok": True}

	if kind not in KINDS:
		frappe.throw(_("Please choose call back or message."))
	company = frappe.db.get_value("Business Profile", {"name": profile, "published": 1}, "company_name")
	if not company:
		frappe.throw(_("This business page is not available."))

	visitor_name = clean(visitor_name, 80)
	phone = clean(phone, 20)
	email = clean(email, 120).lower()
	message = clean(message, 1000, keep_lines=True)

	if len(visitor_name) < 2:
		frappe.throw(_("Please enter your name."))
	if phone and not PHONE.match(phone):
		frappe.throw(_("Please enter a valid phone number."))
	if email and not validate_email_address(email):
		frappe.throw(_("Please enter a valid email address."))
	if kind == "Callback" and not phone:
		frappe.throw(_("Please enter your phone number so they can call you back."))
	if kind == "Message":
		if not (phone or email):
			frappe.throw(_("Please enter your phone number or email, so they can reply."))
		if len(message) < 3:
			frappe.throw(_("Please write your message."))

	lead = frappe.get_doc(
		{
			"doctype": "Business Enquiry",
			"business_profile": profile,
			"kind": kind,
			"status": "New",
			"visitor_name": visitor_name,
			"phone": phone,
			"email": email,
			"message": message if kind == "Message" else "",
			"source": source_of(referrer, utm),
			"referrer": (referrer or "")[:500],
		}
	).insert(ignore_permissions=True)

	# Staff testing a page don't alert the owner, like page views (tracking.counts_as_visitor)
	if counts_as_visitor():
		alert_owner(lead, company)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def set_status(name: str, status: str):
	"""Dashboard button: mark a lead Contacted (or New again). Only the page's owner or staff."""
	if status not in ("New", "Contacted"):
		frappe.throw(_("Unknown status"))
	profile = frappe.db.get_value("Business Enquiry", name, "business_profile")
	if not profile:
		frappe.throw(_("Not found"), frappe.DoesNotExistError)
	user = frappe.session.user
	is_staff = frappe.get_cached_value("User", user, "user_type") == "System User"
	if not is_staff and frappe.db.get_value("Business Profile", profile, "owner") != user:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	frappe.db.set_value("Business Enquiry", name, "status", status)
	return {"ok": True, "status": status}


def clean(value, limit, keep_lines=False):
	"""Trim, drop control characters and cap the length. Text is escaped again wherever it is shown."""
	text = str(value or "").replace("\r\n", "\n")
	text = re.sub(r"[^\S\n]+" if keep_lines else r"\s+", " ", text)
	text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)
	if keep_lines:
		text = re.sub(r"\n{3,}", "\n\n", text)
	return text.strip()[:limit]


def alert_owner(lead, company):
	"""Bell alert plus an email to the owner. A failure here never loses the saved lead."""
	owner, page_email = frappe.db.get_value("Business Profile", lead.business_profile, ["owner", "email"])
	what = _("wants a call back") if lead.kind == "Callback" else _("sent you a message")
	subject = f"{'📞' if lead.kind == 'Callback' else '✉️'} {lead.visitor_name} {what}"

	if owner and owner not in ("Guest", "Administrator"):
		try:
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"for_user": owner,
					"type": "Alert",
					"document_type": "Business Profile",
					"document_name": lead.business_profile,
					"subject": escape_html(f"{subject} · {company}"),
				}
			).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error("Business Enquiry: could not add the bell alert")

	# The account the owner logs in with, else the email on their page
	to = owner if owner and validate_email_address(owner) and owner != "Administrator" else page_email
	if not (to and validate_email_address(to)):
		return
	try:
		from its_your_profile.its_your_profile.doctype.business_profile.business_profile import (
			welcome_email_account,
		)

		account = welcome_email_account()
		sender = frappe.db.get_value("Email Account", account, "email_id") if account else None
		frappe.sendmail(
			recipients=[to],
			sender=sender,
			reply_to=lead.email or None,
			subject=f"{subject} · {company}",
			message=email_body(lead, company),
			reference_doctype="Business Profile",
			reference_name=lead.business_profile,
			now=True,
		)
	except Exception:
		frappe.log_error("Business Enquiry: could not email the owner")


def email_body(lead, company):
	"""A short, plain email in the site's colours: who, how to reach them, and a dashboard link."""
	e = escape_html
	rows = [(_("Name"), e(lead.visitor_name))]
	if lead.phone:
		digits = re.sub(r"[^0-9+]", "", lead.phone)
		rows.append((_("Phone"), f'<a href="tel:{e(digits)}" style="color:#3B2E7E">{e(lead.phone)}</a>'))
	if lead.email:
		rows.append((_("Email"), f'<a href="mailto:{e(lead.email)}" style="color:#3B2E7E">{e(lead.email)}</a>'))
	if lead.message:
		rows.append((_("Message"), e(lead.message).replace("\n", "<br>")))
	if lead.source and lead.source != "Direct":
		rows.append((_("Found you on"), e(lead.source)))
	table = "".join(
		f'<tr><td style="padding:8px 12px 8px 0;color:#5A5578;vertical-align:top;white-space:nowrap">{label}</td>'
		f'<td style="padding:8px 0;color:#1E1838;font-weight:600">{value}</td></tr>'
		for label, value in rows
	)
	heading = (
		_("{0} would like a call back").format(e(lead.visitor_name))
		if lead.kind == "Callback"
		else _("New message from {0}").format(e(lead.visitor_name))
	)
	return f"""
<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#1E1838">
	<img src="{get_url('/assets/its_your_profile/images/iyp-logo.png')}" alt="It's Your Profile" width="150" style="display:block;margin:0 0 20px">
	<h2 style="margin:0 0 6px;font-size:20px">{heading}</h2>
	<p style="margin:0 0 16px;color:#5A5578">{_("They found {0} on It's Your Profile.").format(e(company))}</p>
	<table style="border-collapse:collapse;font-size:15px;margin:0 0 20px">{table}</table>
	<a href="{get_url('/notifications#leads')}" style="display:inline-block;padding:12px 20px;border-radius:10px;background:#3B2E7E;color:#ffffff;text-decoration:none;font-weight:700">{_("Open my dashboard")}</a>
	<p style="margin:20px 0 0;font-size:13px;color:#7D7898">{_("Please contact them soon. Quick replies win more customers.")}</p>
</div>"""
