import frappe

from its_your_profile.its_your_profile.doctype.business_profile.business_profile import iyp_id_from_route


def execute():
	"""2026-11-25: fill the new IYP ID field (IYP-26-11-00003) for pages that already exist."""
	for profile in frappe.get_all("Business Profile", fields=["name", "route", "iyp_id"]):
		iyp_id = iyp_id_from_route(profile.route)
		if iyp_id and iyp_id != profile.iyp_id:
			frappe.db.set_value("Business Profile", profile.name, "iyp_id", iyp_id, update_modified=False)
