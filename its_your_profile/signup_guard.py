"""Stop robot sign-ups (2026-11-18, captcha added 2026-11-19).

Robots were posting straight to Frappe's sign-up method with made-up names ("Wfsyudsor") and other
people's email addresses, so those people got "Welcome to It's Your Profile" emails.

Two checks, both before the account (and its welcome email) is created:
1. "iyp_human": our login page script (public/js/iyp_footer.js, guardSignup) adds it only after
   someone has actually typed or tapped on the page.
2. A captcha: the sign-up form shows a 5-character code of letters and numbers to type in ("Type
   this code: K7M4P"). It comes from new_captcha(), which keeps it on the server (cache, 15 minutes,
   usable once). The sign-up must send the captcha id and the same code.
Accounts made any other way (by staff in the desk, by our own code) are not affected.
"""

import secrets

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

SIGNUP_METHOD = "frappe.core.doctype.user.user.sign_up"
HUMAN_VALUE = "iyp-1"
CAPTCHA_SECONDS = 15 * 60
CAPTCHA_LETTERS = "ACDEFGHJKMNPQRTUVWXY"
CAPTCHA_DIGITS = "34679"
CAPTCHA_CHARS = CAPTCHA_LETTERS + CAPTCHA_DIGITS


def is_signup_request() -> bool:
	form = getattr(frappe.local, "form_dict", None) or {}
	if form.get("cmd") == SIGNUP_METHOD:
		return True
	request = getattr(frappe.local, "request", None)
	return bool(request and (request.path or "").rstrip("/").endswith(SIGNUP_METHOD))


def captcha_key(captcha_id: str) -> str:
	return f"iyp_captcha:{captcha_id}"


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=200, seconds=10 * 60)  # 2026-11-24: per IP; was 40, room-sized for demos
def new_captcha():
	"""A 5-character code of letters and numbers to copy, e.g. "K7M4P" (2026-11-19). Look-alike
	characters (0/O, 1/I/L, 5/S, 2/Z, 8/B) are left out, and capital or small letters both count. The
	page gets the code to show and an id; the server keeps the code to compare, once, for 15 minutes."""
	code = "".join(secrets.choice(CAPTCHA_CHARS) for i in range(5))
	if code.isdigit() or code.isalpha():  # always a mix of both
		code = code[:4] + (secrets.choice(CAPTCHA_LETTERS) if code.isdigit() else secrets.choice(CAPTCHA_DIGITS))
	captcha_id = secrets.token_urlsafe(16)
	frappe.cache.set_value(captcha_key(captcha_id), code, expires_in_sec=CAPTCHA_SECONDS)
	return {"id": captcha_id, "question": code}


def captcha_passed(captcha_id: str | None, answer: str | None) -> bool:
	"""True once for the right answer; the question can't be used again either way."""
	if not captcha_id or answer is None:
		return False
	key = captcha_key(str(captcha_id)[:64])
	expected = frappe.cache.get_value(key)
	frappe.cache.delete_value(key)
	return bool(expected) and str(answer).strip().upper() == str(expected).upper()


def check_new_user(doc, method=None):
	"""User before_insert: refuse a website sign-up that didn't come from a person on our form."""
	if not is_signup_request():
		return
	form = getattr(frappe.local, "form_dict", None) or {}
	if form.get("iyp_human") != HUMAN_VALUE:
		frappe.throw(
			_("Please sign up using the form on itsyourprofile.com."),
			frappe.PermissionError,
			title=_("Not Allowed"),
		)
	if not captcha_passed(form.get("iyp_captcha_id"), form.get("iyp_captcha_answer")):
		frappe.throw(
			_("The code you typed didn't match. Please type the new code."),
			frappe.ValidationError,
			title=_("Quick check"),
		)
