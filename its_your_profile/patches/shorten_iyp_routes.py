import re

import frappe
from frappe.website.utils import clear_cache

LONG_ROUTE = re.compile(r"^business/iyp-20(\d\d)-(\d\d)-(\d{5})$")


def execute():
	"""business/iyp-2026-10-00001 → business/iyp-26-10-00001 (same number, two-digit year)."""
	for profile in frappe.get_all(
		"Business Profile", filters={"route": ("like", "business/iyp-20%")}, fields=["name", "route"]
	):
		if match := LONG_ROUTE.match(profile.route):
			short = "business/iyp-{}-{}-{}".format(*match.groups())
			frappe.db.set_value("Business Profile", profile.name, "route", short, update_modified=False)

	clear_cache()
