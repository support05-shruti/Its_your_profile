app_name = "its_your_profile"
app_title = "Its Your Profile"
app_publisher = "SoftWorld Solutions Pvt. Ltd"
app_description = "AI-optimized business directory"
app_email = "support05@softworld.co.in"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "its_your_profile",
# 		"logo": "/assets/its_your_profile/logo.png",
# 		"title": "Its Your Profile",
# 		"route": "/its_your_profile",
# 		"has_permission": "its_your_profile.api.permission.has_app_permission",
# 	}
# ]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `its_your_profile/dock/its_your_profile/its_your_profile.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Owners' menu after they log in (the web form's account pages)
standard_portal_menu_items = [
	{"title": "My Dashboard", "route": "/notifications"},
]

# Browser tab icon (2026-11-06): our magnifier logo on every website page instead of Frappe's.
# An icon uploaded in Website Settings > Favicon still takes priority over this.
website_context = {
	"favicon": "/assets/its_your_profile/images/iyp-favicon.png",
	# Loading splash (after login and while the backend loads) shows our logo, not Frappe's (2026-11-06)
	"splash_image": "/assets/its_your_profile/images/iyp-logo.png",
	# Our logo in Frappe's top bar (web forms, login and other standard pages)
	"brand_html": '<img src="/assets/its_your_profile/images/iyp-logo.png" alt="It\'s Your Profile" style="height:46px;width:auto;max-height:none;max-width:none">',  # Frappe caps brand images at 22px
	# Footer credit on every standard page (web form, business pages, directory, login...),
	# in place of Frappe's "Built on Frappe". The home page has its own footer with the same line.
	"footer_powered": 'Developed by <a href="https://softworld.co.in" target="_blank" rel="noopener" style="color:#3B2E7E;font-weight:600">SoftWorld Solutions Pvt. Ltd.</a>',
}

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/its_your_profile/css/its_your_profile.css"
# app_include_js = "/assets/its_your_profile/js/its_your_profile.js"

# include js, css files in header of web template
# web_include_css = "/assets/its_your_profile/css/its_your_profile.css"
# web_include_js = "/assets/its_your_profile/js/its_your_profile.js"
# "Developed by SoftWorld Solutions Pvt. Ltd." badge fixed on every website page (2026-11-06)
web_include_js = ["/assets/its_your_profile/js/iyp_credit.js"]
# Site look for Frappe's standard pages: login page with our logo, owner's dashboard (2026-11-06)
web_include_css = ["/assets/its_your_profile/css/iyp_site.css"]

# Business owners land on their dashboard (/notifications) right after logging in (2026-11-06)
on_login = ["its_your_profile.portal.send_owner_to_dashboard"]

# Only staff (System Users) see the Frappe backend; everyone else opening /desk or /app is sent
# to the home page (2026-11-06). Staff log in at /login.
before_request = ["its_your_profile.desk_guard.keep_desk_private"]

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "its_your_profile/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "its_your_profile/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# The public landing page in www/home.html
home_page = "home"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
website_generators = ["Business Profile"]

# Serves /llms.txt, /llms-full.txt and /robots.txt as plain text
page_renderer = ["its_your_profile.llms_txt.CrawlerTextPage"]

# Visit logs never stop a Business Profile from being deleted
ignore_links_on_delete = ["Profile Visit"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "its_your_profile.utils.jinja_methods",
# 	"filters": "its_your_profile.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "its_your_profile.install.before_install"
# after_install = "its_your_profile.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "its_your_profile.uninstall.before_uninstall"
# after_uninstall = "its_your_profile.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "its_your_profile.utils.before_app_install"
# after_app_install = "its_your_profile.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "its_your_profile.utils.before_app_uninstall"
# after_app_uninstall = "its_your_profile.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "its_your_profile.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "its_your_profile.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["its_your_profile.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"its_your_profile.tasks.all"
# 	],
# 	"daily": [
# 		"its_your_profile.tasks.daily"
# 	],
# 	"hourly": [
# 		"its_your_profile.tasks.hourly"
# 	],
# 	"weekly": [
# 		"its_your_profile.tasks.weekly"
# 	],
# 	"monthly": [
# 		"its_your_profile.tasks.monthly"
# 	],
# }

# CHANGE NOTE 2026-11-05: monthly WhatsApp report to each business, 1st of the month at 10:00
# (site time zone). Does nothing until switched on in Its Your Profile Settings.
scheduler_events = {
	"cron": {
		"0 10 1 * *": ["its_your_profile.monthly_report.send_monthly_reports"],
	},
}

# Testing
# -------

# before_tests = "its_your_profile.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "its_your_profile.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "its_your_profile.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "its_your_profile.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["its_your_profile.utils.before_request"]
# after_request = ["its_your_profile.utils.after_request"]

# Job Events
# ----------
# before_job = ["its_your_profile.utils.before_job"]
# after_job = ["its_your_profile.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"its_your_profile.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

