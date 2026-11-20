"""Google One Tap on every page (2026-11-16): know WHO visited, with the visitor's consent.

A website can't read the Google or Chrome account a visitor is logged into. Google One Tap shows the
visitor a small Google box, "Continue as Shruti"; only if they tap it does Google give the page a
signed token with their name and email. We check that token with Google and save them as a Site
Visitor (staff dashboard: "People on It's Your Profile"); on a business page also a "Signed In" visit
(Known Person) and tell the owner: "👤 Shruti Palande viewed your page".

Off until switched on in Its Your Profile Settings → Google One Tap, with a Google Client ID.
Google only allows it on https domains (and localhost), so it works on itsyourprofile.com, not on
an office IP address like 192.168.1.30.
"""

import base64
import hashlib
import hmac
import time

import frappe
import requests
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_to_date, escape_html, now_datetime, validate_email_address

from its_your_profile.tracking import log_known_visit, notify_owner, source_of

GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
REPEAT_GAP_HOURS = 6  # the same person on the same page is logged again only after this
KNOWN_ALERT_GAP = 6 * 60 * 60


def client_id() -> str | None:
	"""The Google Client ID when One Tap is switched on, else None."""
	try:
		settings = frappe.get_cached_doc("Its Your Profile Settings")
	except Exception:
		return None
	if not settings.get("google_one_tap"):
		return None
	return (settings.get("google_client_id") or "").strip() or None


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60)
def identify(
	credential: str,
	path: str | None = None,
	profile: str | None = None,
	referrer: str | None = None,
	utm: str | None = None,
):
	"""Called by iyp_onetap.js (every website page) after the visitor taps "Continue as …".

	CHANGE 2026-11-16: One Tap is on the whole site, not only business pages. Every person is saved
	as a Site Visitor, which staff see on the dashboard ("People on It's Your Profile"). On a business
	page the visit is also logged for that business, so its owner sees the name too."""
	expected = client_id()
	if not expected:
		frappe.throw(_("Google sign-in is not switched on."))

	person = verify(credential, expected)
	name, email = person["name"], person["email"]
	source = source_of(referrer, utm)
	path = "/" + (path or "").strip().lstrip("/")[:200]

	save_site_visitor(name, email, path, source)
	remember_visitor(email)

	if profile and frappe.db.exists("Business Profile", {"name": profile, "published": 1}):
		since = add_to_date(now_datetime(), hours=-REPEAT_GAP_HOURS)
		seen = frappe.db.exists(
			"Profile Visit",
			{"business_profile": profile, "visitor_email": email, "creation": (">=", since)},
		)
		if not seen:
			log_known_visit(profile, name, email, source, referrer)
			came_from = "" if source in ("Direct", "It's Your Profile") else f" · came from {source}"
			notify_owner(
				profile,
				f"👤 {escape_html(name)} ({escape_html(email)}) viewed your page{came_from}",
				f"Known:{email}",
				KNOWN_ALERT_GAP,
			)
	return {"name": name, "first_name": person["first_name"], "email": email}

# 2026-11-19: a visitor who tapped Continue once is remembered on that device, so later visits show
# their name too (tracking.track reads it). A signed cookie: it holds their email and a signature
# made with the site's secret key, so nobody can fake someone else's name by editing it.
VISITOR_COOKIE = "iyp_visitor"
VISITOR_COOKIE_DAYS = 365


def _signature(email: str) -> str:
	from frappe.utils.password import get_encryption_key

	return hmac.new(get_encryption_key().encode(), email.encode(), hashlib.sha256).hexdigest()[:32]


def remember_visitor(email: str):
	try:
		value = base64.urlsafe_b64encode(email.encode()).decode().rstrip("=") + "." + _signature(email)
		frappe.local.cookie_manager.set_cookie(
			VISITOR_COOKIE,
			value,
			expires=add_to_date(now_datetime(), days=VISITOR_COOKIE_DAYS),
			httponly=True,
		)
	except Exception:
		frappe.log_error("Google One Tap: could not remember the visitor")


def remembered_visitor() -> dict | None:
	"""{'name', 'email'} of the visitor who shared their name earlier on this device, else None."""
	try:
		value = (frappe.request.cookies.get(VISITOR_COOKIE) or "") if frappe.request else ""
		encoded, _dot, signature = value.partition(".")
		if not encoded or not signature:
			return None
		email = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
		if not hmac.compare_digest(signature, _signature(email)):
			return None
		name = frappe.db.get_value("Site Visitor", {"email": email}, "full_name")
		# Removed from Site Visitor by staff: no longer named
		return {"name": name or email.split("@")[0], "email": email} if name is not None else None
	except Exception:
		return None


def refuse(reason: str, message: str | None = None):
	"""Log why Google sign-in was refused (Error Log, title 'Google One Tap refused'), then stop."""
	try:
		frappe.log_error(title="Google One Tap refused", message=reason)
		frappe.db.commit()  # the throw below rolls the request back
	except Exception:
		pass
	frappe.throw(message or _("Google sign-in failed. Please try again."))


VISIT_GAP_MINUTES = 30  # page changes within this time are the same visit


def save_site_visitor(name, email, path, source):
	"""One Site Visitor row per person: first and last seen, pages, where they came from, visits."""
	now = now_datetime()
	existing = frappe.db.get_value("Site Visitor", {"email": email}, ["name", "last_seen", "visits"], as_dict=True)
	if not existing:
		frappe.get_doc(
			{
				"doctype": "Site Visitor",
				"full_name": name,
				"email": email,
				"visits": 1,
				"first_seen": now,
				"last_seen": now,
				"first_page": path,
				"last_page": path,
				"source": source,
				"first_source": source,
			}
		).insert(ignore_permissions=True)
		return
	new_visit = not existing.last_seen or existing.last_seen < add_to_date(now, minutes=-VISIT_GAP_MINUTES)
	values = {"full_name": name, "last_seen": now, "last_page": path}
	if new_visit:
		values["visits"] = (existing.visits or 0) + 1
		values["source"] = source
	frappe.db.set_value("Site Visitor", existing.name, values, update_modified=False)


def verify(credential: str, expected_client_id: str) -> dict:
	"""Check the ID token with Google: made for OUR client, by Google, not expired, email verified."""
	if not credential or len(credential) > 4096:
		frappe.throw(_("Google sign-in failed. Please try again."))
	# 2026-11-19: every refusal below is written to Error Log ("Google One Tap refused") with the reason,
	# never the token, so a failing sign-in can be traced from Desk
	try:
		response = requests.get(TOKENINFO, params={"id_token": credential}, timeout=8)
	except requests.RequestException as e:
		refuse(f"Could not reach Google: {e}", _("Could not reach Google. Please try again."))
	if response.status_code != 200:
		refuse(f"Google tokeninfo answered {response.status_code}: {response.text[:300]}")
	info = response.json()

	if info.get("aud") != expected_client_id:
		refuse(f"Token is for client {info.get('aud')!r}, Settings has {expected_client_id!r}")
	if info.get("iss") not in GOOGLE_ISSUERS:
		refuse(f"Unexpected issuer {info.get('iss')!r}")
	if str(info.get("email_verified")).lower() != "true":
		refuse("Email not verified", _("Please use a Google account with a verified email."))
	try:
		# 2026-11-19: real Unix time. now_datetime() is India time without a zone, and .timestamp()
		# read it as the server's UTC: 5½ hours ahead, so every Google token looked expired
		if int(info.get("exp", 0)) < time.time():
			refuse(f"Token expired: exp {info.get('exp')}, server time {int(time.time())}", _("Google sign-in expired. Please try again."))
	except (TypeError, ValueError):
		refuse(f"Bad exp value {info.get('exp')!r}")

	email = validate_email_address((info.get("email") or "").strip().lower())
	if not email:
		frappe.throw(_("Google sign-in failed. Please try again."))
	name = " ".join((info.get("name") or "").split())[:80] or email.split("@")[0]
	first_name = " ".join((info.get("given_name") or "").split())[:40] or name.split(" ")[0]
	return {"name": name, "first_name": first_name, "email": email}
