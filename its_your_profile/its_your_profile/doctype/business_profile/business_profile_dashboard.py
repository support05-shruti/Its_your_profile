from frappe import _


def get_data():
	"""Shows the Profile Visit count on the Business Profile form."""
	return {
		"fieldname": "business_profile",
		"transactions": [{"label": _("Visitors"), "items": ["Profile Visit"]}],
	}
