"""Emails say "It's Your Profile", and new business pages get their welcome email (2026-11-12).

- Frappe's own emails (sign-up "Welcome to ...", password reset) take the site name from System
  Settings / Website Settings > App Name, which said "Softworld...". Set both to It's Your Profile.
- Its Your Profile Settings > Send Welcome Email Automatically was off, so owners of new pages got
  no "Your business is live" email unless someone clicked the Desk button. Switch it on.
  (Existing pages are not emailed by this patch: see tasks.send_pending_welcome_emails.)
Runs once on migrate; anything changed by hand afterwards stays as it is.
"""

import frappe

APP_NAME = "It's Your Profile"


def execute():
	for settings in ("System Settings", "Website Settings"):
		if frappe.get_meta(settings).has_field("app_name"):
			frappe.db.set_single_value(settings, "app_name", APP_NAME)
	if frappe.get_meta("Its Your Profile Settings").has_field("send_welcome_email"):
		frappe.db.set_single_value("Its Your Profile Settings", "send_welcome_email", 1)
	frappe.clear_cache()
