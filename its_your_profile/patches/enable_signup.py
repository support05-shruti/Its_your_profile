"""Turn website sign-up on (2026-11-12).

Business owners create their own account (Sign up on the home page and the login page). With
Website Settings > Disable Signup ticked, the sign-up page only says "Signups have been disabled for
this website" and Frappe refuses new accounts, so the whole flow stops. Runs once on migrate; if
someone ticks the box again later on purpose, it stays ticked.
"""

import frappe


def execute():
	if frappe.db.get_single_value("Website Settings", "disable_signup"):
		frappe.db.set_single_value("Website Settings", "disable_signup", 0)
		frappe.clear_cache()
