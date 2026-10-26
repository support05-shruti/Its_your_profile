import frappe
from frappe.website.utils import clear_cache

from its_your_profile.its_your_profile.doctype.business_profile.business_profile import make_profile_route


def execute():
	"""Give existing profiles the business/iyp-<year>-<month>-<number> address, oldest first,
	so the yearly numbers follow the order the cards were added."""
	profiles = frappe.get_all(
		"Business Profile",
		filters={"route": ("not like", "business/iyp-%")},
		fields=["name", "creation", "company_name"],
		order_by="creation asc",
	)
	for profile in profiles:
		if not profile.company_name:
			continue  # no public page until the card is read
		route = make_profile_route(frappe.utils.get_datetime(profile.creation))
		frappe.db.set_value("Business Profile", profile.name, "route", route, update_modified=False)

	clear_cache()
