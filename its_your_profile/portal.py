"""Where business owners land after they log in (2026-11-06)."""

import frappe

OWNER_DASHBOARD = "notifications"


def redirect(url: str):
	"""Send the browser to url with a TEMPORARY (302) redirect (2026-11-07).

	frappe.redirect() sends 301 "moved permanently", which browsers remember forever: a page once
	visited while logged out (/account → login) then always jumped to the login page, even after
	logging in. These pages redirect depending on who is logged in, so they must be 302."""
	frappe.local.flags.redirect_location = url
	raise frappe.Redirect(302)


def send_owner_to_dashboard(login_manager):
	"""on_login hook: business owners (Website Users) go to their dashboard at /notifications.

	Only this login request is affected (a request flag, read by get_home_page), so the home page
	at / still shows the home page later. A ?redirect-to= in the login URL still wins."""
	user = getattr(login_manager, "user", None) or frappe.session.user
	if frappe.get_cached_value("User", user, "user_type") == "Website User":
		frappe.local.flags.home_page = OWNER_DASHBOARD
