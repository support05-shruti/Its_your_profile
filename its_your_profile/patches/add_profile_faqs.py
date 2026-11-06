import frappe


def execute():
	"""Write FAQs for profiles published before FAQs existed. Each needs an AI call, so they run
	as background jobs instead of slowing down the migrate."""
	profiles = frappe.get_all(
		"Business Profile",
		filters={"published": 1, "company_name": ("is", "set")},
		pluck="name",
	)
	have_faqs = set(frappe.get_all("Business Profile FAQ", filters={"parenttype": "Business Profile"}, pluck="parent"))
	for name in profiles:
		if name in have_faqs:
			continue
		frappe.enqueue(
			"its_your_profile.tasks.write_faqs",
			queue="long",
			profile=name,
			job_id=f"write_faqs::{name}",
			deduplicate=True,
		)
