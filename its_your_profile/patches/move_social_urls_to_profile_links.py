import frappe


def execute():
	"""Copy the old LinkedIn / Facebook URL fields into the new Profile Links table.

	The fields were removed from the doctype, but migrate leaves their columns in the table.
	"""
	columns = [c for c in ("linkedin_url", "facebook_url") if frappe.db.has_column("Business Profile", c)]
	if not columns:
		return

	platforms = {"linkedin_url": "LinkedIn", "facebook_url": "Facebook"}
	rows = frappe.db.sql(f"select name, {', '.join(columns)} from `tabBusiness Profile`", as_dict=True)
	for row in rows:
		doc = frappe.get_doc("Business Profile", row.name)
		have = {link.platform for link in doc.profile_links}
		changed = False
		for column in columns:
			platform = platforms[column]
			if row.get(column) and platform not in have:
				doc.append("profile_links", {"platform": platform, "url": row.get(column)})
				changed = True
		if changed:
			doc.flags.from_scan = True  # keep scan status as it is
			doc.save(ignore_permissions=True)
