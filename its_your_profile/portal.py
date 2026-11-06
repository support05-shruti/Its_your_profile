"""Where business owners land after they log in (2026-11-06)."""

import frappe

OWNER_DASHBOARD = "notifications"


def send_owner_to_dashboard(login_manager):
	"""on_login hook: business owners (Website Users) go to their dashboard at /notifications.

	Only this login request is affected (a request flag, read by get_home_page), so the home page
	at / still shows the home page later. A ?redirect-to= in the login URL still wins."""
	user = getattr(login_manager, "user", None) or frappe.session.user
	if frappe.get_cached_value("User", user, "user_type") == "Website User":
		frappe.local.flags.home_page = OWNER_DASHBOARD
