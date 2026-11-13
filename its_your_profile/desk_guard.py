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

	# 2026-11-12: Frappe v16 accepts ?cmd=web_logout only as POST, so the old "Log out" link (still
	# cached on phones) showed "403 Not Permitted". Send that link to Frappe's /logout page instead.
	if request.method == "GET" and request.args.get("cmd") in ("web_logout", "logout"):
		raise HTTPException(response=redirect("/logout", code=302))

	path = request.path.rstrip("/") or "/"

	# 2026-11-12: business pages live at /business/<name>; /business on its own made Frappe try to
	# build an automatic list of all profiles, which failed with "500: There was an error building
	# this page". Staff go to the (staff-only) directory, everyone else to the home page.
	if path == "/business":
		user = frappe.session.user if getattr(frappe.local, "session", None) else "Guest"
		staff = user != "Guest" and frappe.get_cached_value("User", user, "user_type") == "System User"
		raise HTTPException(response=redirect("/directory" if staff else "/", code=302))

	# 2026-11-12: Frappe's own About and Contact pages, when switched off in their settings, answered
	# with a 301 redirect to /404. Crawlers should get a plain "404 Not Found" at the address itself.
	settings = {"/about": "About Us Settings", "/contact": "Contact Us Settings"}.get(path)
	if settings and frappe.db.get_single_value(settings, "is_disabled"):
		try:
			from frappe.website.page_renderers.not_found_page import NotFoundPage

			response = NotFoundPage(path.strip("/")).render()
		except Exception:
			from werkzeug.wrappers import Response

			response = Response("Page not found", status=404, mimetype="text/plain")
		response.status_code = 404
		raise HTTPException(response=response)

	# 2026-11-13: Frappe's own list of business pages (/my-business, /my-business/list) is a plain page
	# we never styled (unreadable in dark mode); the Dashboard already lists every business with View,
	# Edit and Share, so it goes there. Frappe's read-only view of one page (/my-business/<name>) opens
	# its edit form (My information) instead. /my-business/new and /<name>/edit are left alone.
	if path in ("/my-business", "/my-business/list"):
		raise HTTPException(response=redirect("/notifications", code=302))
	parts = path.split("/")
	if len(parts) == 3 and parts[1] == "my-business" and parts[2] not in ("new", "list"):
		raise HTTPException(response=redirect(f"{path}/edit", code=302))

	# 2026-11-12: Frappe's "My Account" (/me) and app switcher (/apps) pages link to the Desk, which no
	# website button may open. Everyone goes to our dashboard instead (it sends guests to log in).
	if path in ("/me", "/apps"):
		raise HTTPException(response=redirect("/notifications", code=302))

	if not any(path == p or path.startswith(p + "/") for p in DESK_PATHS):
		return

	user = frappe.session.user if getattr(frappe.local, "session", None) else "Guest"
	if user != "Guest" and frappe.get_cached_value("User", user, "user_type") == "System User":
		return

	# Werkzeug exceptions carrying a response are sent as they are by Frappe's request handler
	raise HTTPException(response=redirect("/", code=302))
