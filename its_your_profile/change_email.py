"""'You updated your business details' email (2026-11-23).

After someone saves "My information" (the my-business web form), the person who saved gets an
email listing each change: what it was before and what it is now. Only saves made on that form
count: background jobs (card scan, website reading, FAQ writing, logo) never send it.
"""

import frappe
from frappe import _

WEB_FORM = "my-business"
# Layout-only and card-scan fields are never listed
SKIP_TYPES = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Heading"}
SKIP_FIELDS = {"visiting_card", "visiting_card_back", "card_scan_status"}
MAX_TEXT = 300


def send_change_email(doc, method=None):
	"""Business Profile on_update. Never stops a save: any problem goes to the Error Log."""
	if not frappe.flags.in_web_form:
		return
	try:
		before = doc.get_doc_before_save()
		if not before:
			return  # a brand-new page gets the welcome email instead
		changes = list_changes(before, doc)
		recipient = saver_email()
		if not changes or not recipient:
			return

		from its_your_profile.its_your_profile.doctype.business_profile.business_profile import (
			welcome_email_account,
		)
		from its_your_profile.page_report import email_link

		account = welcome_email_account()
		frappe.sendmail(
			recipients=[recipient],
			sender=frappe.db.get_value("Email Account", account, "email_id") if account else None,
			subject=_("You updated {0}").format(doc.company_name or _("your business page")),
			template="profile_changed",
			args={
				"doc": doc,
				"changes": changes,
				"who": frappe.utils.get_fullname(frappe.session.user),
				"when": frappe.utils.format_datetime(frappe.utils.now_datetime(), "dd-MM-yyyy hh:mm a"),
				"page_url": frappe.utils.get_url(doc.route) if doc.route and doc.published else None,
				"edit_url": email_link(f"/my-business/{doc.name}/edit", "change_it", campaign="change_email"),
			},
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)
	except Exception:
		frappe.log_error(title=f"Change email failed for {doc.name}")


def saver_email():
	"""The logged-in person who clicked Save (not the business email on the page)."""
	user = frappe.session.user
	if user in ("Guest", "Administrator"):
		return None
	email = frappe.db.get_value("User", user, "email") or user
	return email if frappe.utils.validate_email_address(email) else None


def form_fields():
	"""(fieldname, label, fieldtype) of every field on the My information form, in its order."""
	web_form = frappe.get_cached_doc("Web Form", WEB_FORM)
	seen = set()
	fields = []
	for df in web_form.web_form_fields:
		if df.fieldtype in SKIP_TYPES or df.fieldname in SKIP_FIELDS or not df.fieldname or df.fieldname in seen:
			continue
		seen.add(df.fieldname)
		fields.append((df.fieldname, _(df.label or df.fieldname), df.fieldtype))
	return fields


def list_changes(before, after):
	"""[{label, old, new, image}] for each field whose shown value changed."""
	changes = []
	for fieldname, label, fieldtype in form_fields():
		old, new = shown(before, fieldname, fieldtype), shown(after, fieldname, fieldtype)
		if old == new:
			continue
		image = fieldtype == "Attach Image"
		changes.append(
			{
				"label": label,
				"old": old if not image else (_("A logo") if old else ""),
				"new": new if not image else (_("New logo") if new else _("Removed")),
				"image": frappe.utils.get_url(after.get(fieldname)) if image and after.get(fieldname) else None,
			}
		)
	return changes


def shown(doc, fieldname, fieldtype):
	"""The value as a person reads it: tables as one line per row, Yes/No for ticks."""
	value = doc.get(fieldname)
	if fieldtype == "Table":
		lines = []
		for row in value or []:
			if row.get("platform") or row.get("url"):  # Profile Links
				lines.append(f"{row.get('platform') or _('Link')}: {row.get('url') or ''}".strip())
			elif row.get("question"):  # FAQs
				lines.append(f"{row.get('question')} {row.get('answer') or ''}".strip())
		return "\n".join(lines)
	if fieldtype == "Check":
		return _("Yes") if value else _("No")
	text = " ".join(str(value).split()) if value not in (None, "") else ""
	if fieldtype == "Int" and text == "0":
		text = ""
	return text if len(text) <= MAX_TEXT else text[:MAX_TEXT].rsplit(" ", 1)[0] + "…"
