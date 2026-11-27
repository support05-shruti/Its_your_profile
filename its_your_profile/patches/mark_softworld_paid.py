"""2026-11-27: Milind sir (SoftWorld Solutions Pvt. Ltd.) has paid. His 10-year subscription counts
from 31 Dec 2026, so: Paid Plan ticked, Paid From 31-12-2026, Paid Until 30-12-2036.

Runs once (patches.txt). Only touches SoftWorld pages that are not marked paid yet, so a plan
someone already set by hand in Desk is never overwritten.
"""

import frappe

PAID_FROM = "2026-12-31"
PAID_UNTIL = "2036-12-30"


def execute():
	if not frappe.db.has_column("Business Profile", "paid_from"):
		return  # the Paid From field comes with the same deploy; migrate adds it before patches run

	names = frappe.get_all(
		"Business Profile",
		filters={"company_name": ("like", "SoftWorld Solutions%"), "paid_plan": 0},
		pluck="name",
	)
	for name in names:
		frappe.db.set_value(
			"Business Profile",
			name,
			{"paid_plan": 1, "paid_from": PAID_FROM, "paid_until": PAID_UNTIL},
			update_modified=False,
		)
	frappe.db.commit()
