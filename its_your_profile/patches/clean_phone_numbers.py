import frappe

from its_your_profile.its_your_profile.doctype.business_profile.business_profile import clean_phone


def execute():
	"""Remove spaces, dashes, brackets and dots from phone numbers saved before this was done on save."""
	for profile in frappe.get_all("Business Profile", filters={"phone": ("is", "set")}, fields=["name", "phone"]):
		cleaned = clean_phone(profile.phone)
		if cleaned != profile.phone:
			frappe.db.set_value("Business Profile", profile.name, "phone", cleaned, update_modified=False)
