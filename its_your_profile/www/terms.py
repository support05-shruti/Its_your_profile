"""Terms and Conditions at /terms (2026-11-07). The text is in terms.html."""

from frappe.utils import getdate, format_date

sitemap = 1

# Change this date whenever the terms in terms.html change
LAST_UPDATED = "2026-11-07"


def get_context(context):
	context.title = "Terms and Conditions · It's Your Profile"
	context.description = "The terms for creating and publishing a business page on It's Your Profile."
	context.last_updated = format_date(getdate(LAST_UPDATED), "d MMMM yyyy")
	context.year = getdate().year
