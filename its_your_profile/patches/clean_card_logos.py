import frappe


def execute():
	"""Cut the card logos again with the cleanup (transparent background, no other print on the
	card). Logos uploaded by hand are left alone; see tasks.add_logo_from_card."""
	for name in frappe.get_all(
		"Business Profile", filters={"visiting_card": ("is", "set")}, pluck="name"
	):
		frappe.enqueue(
			"its_your_profile.tasks.add_logo_from_card",
			queue="long",
			profile=name,
			redo=True,
			job_id=f"add_logo_from_card::{name}",
			deduplicate=True,
		)
