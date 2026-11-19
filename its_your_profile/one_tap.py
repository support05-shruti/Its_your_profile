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
	try:
		response = requests.get(TOKENINFO, params={"id_token": credential}, timeout=8)
	except requests.RequestException:
		frappe.throw(_("Could not reach Google. Please try again."))
	if response.status_code != 200:
		frappe.throw(_("Google sign-in failed. Please try again."))
	info = response.json()

	if info.get("aud") != expected_client_id or info.get("iss") not in GOOGLE_ISSUERS:
		frappe.throw(_("Google sign-in failed. Please try again."))
	if str(info.get("email_verified")).lower() != "true":
		frappe.throw(_("Please use a Google account with a verified email."))
	try:
		# 2026-11-19: real Unix time. now_datetime() is India time without a zone, and .timestamp()
		# read it as the server's UTC: 5½ hours ahead, so every Google token looked expired
		if int(info.get("exp", 0)) < time.time():
			frappe.throw(_("Google sign-in expired. Please try again."))
	except (TypeError, ValueError):
		frappe.throw(_("Google sign-in failed. Please try again."))

	email = validate_email_address((info.get("email") or "").strip().lower())
	if not email:
		frappe.throw(_("Google sign-in failed. Please try again."))
	name = " ".join((info.get("name") or "").split())[:80] or email.split("@")[0]
	first_name = " ".join((info.get("given_name") or "").split())[:40] or name.split(" ")[0]
	return {"name": name, "first_name": first_name, "email": email}
