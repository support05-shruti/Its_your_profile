"""Keep the Frappe backend out of sight for the public (2026-11-06).

Frappe already refuses outsiders at /desk and /app (guests get its login page, business owners a
"not permitted" page), but the Frappe screens still show. This sends anyone who is not staff
(a System User) straight to our home page instead. Staff log in at /login as usual and are let in.
"""

import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

DESK_PATHS = ("/desk", "/app")

# The first part of every address that belongs to our website, or that Frappe needs to work
# (login, password reset from emails, two-factor QR, the API, files, real-time updates).
SITE_PATHS = {
	"", "login", "logout", "update-password", "qrcode", "terms", "notifications", "account",
	"directory", "business", "my-business", "me", "apps", "desk", "app", "404",
	"api", "assets", "files", "private", "socket.io", "website_script.js",
}  # fmt: skip


def is_frappe_page(path: str) -> bool:
	"""True for an existing Frappe / ERPNext / HRMS website page that is not part of our website.
	Addresses that don't exist at all are left to Frappe, which shows our "Page not found"."""
	first = path.strip("/").split("/", 1)[0]
	if first in SITE_PATHS or "." in first:
		return False
	return first in frappe_page_routes()


def frappe_page_routes() -> set[str]:
	"""First part of the address of every page the installed apps provide: their www pages, web forms
	(except ours) and doctype list pages. Kept for 10 minutes."""
	cached = frappe.cache.get_value("iyp_frappe_page_routes")
	if cached is not None:
		return set(cached)
	routes = set()
	try:
		from frappe.website.router import get_doctypes_with_web_view, get_pages

		routes |= {route.strip("/").split("/", 1)[0] for route in get_pages()}
		routes |= {
			(r or "").strip("/").split("/", 1)[0]
			for r in frappe.get_all("Web Form", filters={"published": 1}, pluck="route")
		}
		for doctype in get_doctypes_with_web_view():
			routes.add(frappe.scrub(doctype).replace("_", "-"))
		# Pages Frappe renders without a www file
		routes |= {"printview", "list", "error", "message", "portal", "support", "issues", "projects",
			"orders", "invoices", "addresses", "third_party_apps", "newsletters", "blog", "search",
			"dashboard", "unsubscribe", "contact", "about"}  # fmt: skip
	except Exception:
		frappe.log_error("desk_guard: could not list Frappe page routes")
	routes -= SITE_PATHS
	frappe.cache.set_value("iyp_frappe_page_routes", list(routes), expires_in_sec=600)
	return routes


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

	# 2026-11-13: no Frappe / ERPNext / HRMS website page opens for the public. Frappe and the other
	# installed apps bring their own pages (/portal, /support, /issues, /projects, /orders,
	# /invoices, /addresses, /printview, /list, /error...), which look like Frappe, not our site.
	# Anyone who is not staff opening a page outside our own site goes to the home page.
	# Files (anything with a "." in its name: robots.txt, sitemap.xml, images...) are not affected.
	if is_frappe_page(path):
		user = frappe.session.user if getattr(frappe.local, "session", None) else "Guest"
		if not (user != "Guest" and frappe.get_cached_value("User", user, "user_type") == "System User"):
			raise HTTPException(response=redirect("/", code=302))

	if not any(path == p or path.startswith(p + "/") for p in DESK_PATHS):
		return

	user = frappe.session.user if getattr(frappe.local, "session", None) else "Guest"
	if user != "Guest" and frappe.get_cached_value("User", user, "user_type") == "System User":
		return

	# Werkzeug exceptions carrying a response are sent as they are by Frappe's request handler
	raise HTTPException(response=redirect("/", code=302))
