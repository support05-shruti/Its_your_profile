// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd and contributors
// For license information, please see license.txt

// Read a card side as soon as it is attached, so the details are filled in before Save
function read_card(frm, fieldname) {
	const file_url = frm.doc[fieldname];
	if (!file_url) return;
	frappe
		.call({
			method: "its_your_profile.api.read_visiting_card",
			args: { file_url },
			freeze: true,
			freeze_message: __("Reading the visiting card..."),
		})
		.then(({ message: values }) => {
			// Only fill empty fields, so anything already typed (or read from the front) is kept
			const empty = Object.entries(values || {}).filter(([field]) => !frm.doc[field]);
			frm.set_value(Object.fromEntries(empty));
			frappe.show_alert({
				message: empty.length
					? __("Filled {0} fields from the card. Please check them and Save.", [empty.length])
					: __("No new details found on this side of the card."),
				indicator: empty.length ? "green" : "orange",
			});
		});
}

frappe.ui.form.on("Business Profile", {
	visiting_card(frm) {
		read_card(frm, "visiting_card");
	},
	visiting_card_back(frm) {
		read_card(frm, "visiting_card_back");
	},
});
