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
	"""on_login hook: everyone lands on the dashboard at /notifications after logging in.

	CHANGE 2026-11-12: staff (System Users) too. Before, they were sent to the Desk, and no button
	on the website may open the Desk; staff open it themselves by typing /desk.
	Only this login request is affected (a request flag, read by get_home_page), so the home page
	at / still shows the home page later. A ?redirect-to= in the login URL still wins."""
	frappe.local.flags.home_page = OWNER_DASHBOARD


LOGO = "/assets/its_your_profile/images/iyp-logo.png"


def use_our_logo(context):
	"""update_website_context hook (2026-11-07): the sign-in, sign-up and forgot-password page shows
	our logo. Frappe's login page takes its logo from Website/Navbar Settings or else the first app's
	app_logo_url hook, which is Frappe's own logo when several apps are installed. This runs after
	the page's own get_context, so it wins. A logo uploaded in Website Settings > App Logo is kept."""
	# 2026-11-13: also the set / reset password page (from emails), which showed Frappe's logo
	if (context.get("path") or getattr(frappe.local, "path", "") or "").strip("/") not in ("login", "update-password"):
		return None
	if frappe.get_website_settings("app_logo"):
		return None
	return {"logo": LOGO}


# Runs in <head> before anything is drawn: the visitor's saved light/dark choice (set with the
# 🌙 button on the home page or the dashboard, key "iyp-theme"), else the phone's own setting.
THEME_SCRIPT = (
	"<script>(function(){var s=null;try{s=localStorage.getItem('iyp-theme')}catch(e){}"
	"var d=s?s==='dark':!!(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches);"
	"document.documentElement.setAttribute('data-iyp-theme',d?'dark':'light');})();</script>"
	# Sent inside every page (never a stale cached file), 2026-11-12:
	# - the right logo for light / dark in Frappe's top bar (brand_html has both) and on the login card
	# - Frappe's "Switch To Desk" and "Apps" menu items never shown (no website button opens the Desk)
	"<style>"
	".iyp-brand-dark{display:none!important}"
	"[data-iyp-theme=dark] .iyp-brand-light{display:none!important}"
	"[data-iyp-theme=dark] .iyp-brand-dark{display:inline-block!important}"
	"[data-iyp-theme=dark] img.app-logo{content:url('/assets/its_your_profile/images/iyp-logo-dark.png')}"
	".switch-to-desk,.dropdown-item.apps,a[href='/desk'],a[href='/app'],a[href='/apps']{display:none!important}"
	"</style>"
)


def add_theme_script(context):
	"""update_website_context hook (2026-11-12): dark mode on every website page, not only the home
	page and the dashboard. Adds THEME_SCRIPT to <head>; the dark colours are in iyp_site.css and in
	each page's own styles.

	CHANGE 2026-11-13: through head_html (printed by templates/includes/head.html, which no page
	replaces), not head_include: Frappe's login page replaces the head_include block without keeping
	it, so the login / sign-up page never followed dark mode. Website Settings > Head HTML is kept."""
	head_html = context.get("head_html") or ""
	if THEME_SCRIPT in head_html:
		return None
	return {"head_html": head_html + THEME_SCRIPT}
