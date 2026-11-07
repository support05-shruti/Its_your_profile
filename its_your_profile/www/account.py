"""My information at /account (2026-11-07): opens the logged-in owner's own business details.

Goes straight to the edit form of their latest Business Profile (the web form only ever opens a
user's own profiles), or to the scan card on the home page if they have none yet.
Temporary (302) redirects only: the target depends on who is logged in.
"""

import frappe

from its_your_profile.portal import redirect

no_cache = 1
sitemap = 0


def get_context(context):
	user = frappe.session.user
	if user == "Guest":
		redirect("/login?redirect-to=/account")

	name = frappe.db.get_value("Business Profile", {"owner": user}, "name", order_by="creation desc")
	redirect(f"/my-business/{name}/edit" if name else "/#start")
