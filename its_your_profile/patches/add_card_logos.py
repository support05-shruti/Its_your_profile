import frappe


def execute():
	"""Cut the logo out of the card for profiles made before logos were read from cards.
	Each needs an AI call, so they run as background jobs instead of slowing down the migrate."""
	profiles = frappe.get_all(
		"Business Profile",
		filters={"company_logo": ("is", "not set"), "visiting_card": ("is", "set")},
		pluck="name",
	)
	for name in profiles:
		frappe.enqueue(
			"its_your_profile.tasks.add_logo_from_card",
			queue="long",
			profile=name,
			job_id=f"add_logo_from_card::{name}",
			deduplicate=True,
		)
