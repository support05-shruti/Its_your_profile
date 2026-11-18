"""Stop robot sign-ups (2026-11-18).

Robots were posting straight to Frappe's sign-up method with made-up names ("Wfsyudsor") and other
people's email addresses, so those people got "Welcome to It's Your Profile" emails. Our login page
script (public/js/iyp_footer.js, guardSignup) adds a small "iyp_human" value to the sign-up request,
but only after someone has actually typed or tapped on the page. A sign-up without it is refused
before the account (and its welcome email) is created. Accounts made any other way (by staff in the
desk, by our own code) are not affected.
"""

import frappe
from frappe import _

SIGNUP_METHOD = "frappe.core.doctype.user.user.sign_up"
HUMAN_VALUE = "iyp-1"


def is_signup_request() -> bool:
	form = getattr(frappe.local, "form_dict", None) or {}
	if form.get("cmd") == SIGNUP_METHOD:
		return True
	request = getattr(frappe.local, "request", None)
	return bool(request and (request.path or "").rstrip("/").endswith(SIGNUP_METHOD))


def check_new_user(doc, method=None):
	"""User before_insert: refuse a website sign-up that didn't come from a person on our form."""
	if not is_signup_request():
		return
	form = getattr(frappe.local, "form_dict", None) or {}
	if form.get("iyp_human") == HUMAN_VALUE:
		return
	frappe.throw(
		_("Please sign up using the form on itsyourprofile.com."),
		frappe.PermissionError,
		title=_("Not Allowed"),
	)
