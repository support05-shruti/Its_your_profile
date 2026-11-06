"""Keep the Frappe backend out of sight for the public (2026-11-06).

Frappe already refuses outsiders at /desk and /app (guests get its login page, business owners a
"not permitted" page), but the Frappe screens still show. This sends anyone who is not staff
(a System User) straight to our home page instead. Staff log in at /login as usual and are let in.
"""

import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

DESK_PATHS = ("/desk", "/app")


def keep_desk_private():
	"""before_request hook: send non-staff visitors of /desk or /app to the home page."""
	request = getattr(frappe.local, "request", None)
	if not request:
		return
	path = request.path.rstrip("/") or "/"
	if not any(path == p or path.startswith(p + "/") for p in DESK_PATHS):
		return

	user = frappe.session.user if getattr(frappe.local, "session", None) else "Guest"
	if user != "Guest" and frappe.get_cached_value("User", user, "user_type") == "System User":
		return

	# Werkzeug exceptions carrying a response are sent as they are by Frappe's request handler
	raise HTTPException(response=redirect("/", code=302))
