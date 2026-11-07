"""Public home page at /: what It's Your Profile does, with a start bar that leads to /create."""

import frappe

from its_your_profile.www.directory import is_backend_user

# Where "Create my page" goes: the existing sign-up form until the no-login /create page is built
CREATE_URL = "/my-business/new"

AUDIENCES = (
	("Chartered Accountants", "blue"),
	("Interior Designers", "peach"),
	("Doctors & Clinics", "mint"),
	("Manufacturers", "lilac"),
	("Traders & Distributors", "lemon"),
	("BNI Members", "blue"),
	("Lawyers", "rose"),
	("Consultants", "mint"),
	("Shops & Showrooms", "peach"),
	("Freelancers", "lilac"),
)


def get_context(context):
	context.update(
		{
			"title": "It's Your Profile · Get found by AI",
			"description": "Turn your visiting card into a business page that ChatGPT, Gemini and Claude can find and recommend. Free, ready in a minute.",
			"audiences": AUDIENCES,
			"create_url": CREATE_URL,
			"logged_in": frappe.session.user != "Guest",
			"total": frappe.db.count("Business Profile", {"published": 1, "route": ("is", "set")}),
			# The directory is backend-only (2026-11-06): its links show only to staff
			"is_backend_user": is_backend_user(),
		}
	)
