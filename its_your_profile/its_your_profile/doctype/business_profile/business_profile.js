// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd and contributors
// For license information, please see license.txt

// Wrapped so the desk can load this script more than once without "already declared" errors
(() => {
const MAPS_PREFIX = "https://www.google.com/maps/search/?api=1&query=";
const ADDRESS_FIELDS = ["company_name", "address_line", "city", "state", "pincode"];

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
		.then(async ({ message: values }) => {
			// Only fill empty fields, so anything already typed (or read from the front) is kept
			const empty = Object.entries(values || {}).filter(([field]) => !frm.doc[field]);
			await frm.set_value(Object.fromEntries(empty));
			frappe.show_alert({
				message: empty.length
					? __("Filled {0} fields from the card. Please check them and Save.", [empty.length])
					: __("No new details found on this side of the card."),
				indicator: empty.length ? "green" : "orange",
			});
			update_maps_url(frm);
			read_links(frm);
		});
}

// Build a Google Maps link from the address; a link the user pasted is kept
function update_maps_url(frm) {
	const current = frm.doc.google_maps_url || "";
	if (current && !current.startsWith(MAPS_PREFIX)) return;
	if (!frm.doc.address_line && !frm.doc.city) return;

	const query = ADDRESS_FIELDS.map((f) => (frm.doc[f] || "").replace(/\s+/g, " ").trim())
		.filter(Boolean)
		.join(", ");
	const url = MAPS_PREFIX + encodeURIComponent(query).replace(/%20/g, "+");
	if (url !== current) frm.set_value("google_maps_url", url);
}

// Read the website's profile links and add the new ones to the table
function read_links(frm) {
	const url = (frm.doc.website_url || "").trim();
	if (!url || url === frm.__last_links_url) return;
	frm.__last_links_url = url;

	frappe
		.call({
			method: "its_your_profile.api.read_website_links",
			args: { url },
			freeze: true,
			freeze_message: __("Finding links on the website..."),
		})
		.then(({ message: links }) => {
			const key = (r) => `${r.platform}|${r.label || ""}`;
			const clean = (u) => (u || "").replace(/\/+$/, "").toLowerCase();
			const have = new Set((frm.doc.profile_links || []).map(key));
			const have_urls = new Set((frm.doc.profile_links || []).map((r) => clean(r.url)));

			let added = 0;
			(links || []).forEach((link) => {
				if (have.has(key(link)) || have_urls.has(clean(link.url))) return;
				frm.add_child("profile_links", link);
				have.add(key(link));
				added++;
			});
			frm.refresh_field("profile_links");

			frappe.show_alert({
				message: added
					? __("Added {0} links from the website. Please check them.", [added])
					: __("No new profile links found on the website."),
				indicator: added ? "green" : "orange",
			});
		});
}

// Send the welcome email by hand (works even while the automatic switch is off)
function add_welcome_email_button(frm) {
	if (frm.is_new() || !frm.doc.email) return;
	const label = frm.doc.welcome_email_sent ? __("Resend Welcome Email") : __("Send Welcome Email");
	frm.add_custom_button(label, () => {
		frappe.confirm(
			__("Send the welcome email with the page link to {0}?", [
				`<b>${frappe.utils.escape_html(frm.doc.email)}</b>`,
			]),
			() =>
				frappe
					.call({
						method: "its_your_profile.api.send_welcome_email",
						args: { name: frm.doc.name },
						freeze: true,
						freeze_message: __("Sending..."),
					})
					.then(({ message }) => {
						frappe.show_alert({
							message: __("Welcome email queued for {0}", [message.sent_to]),
							indicator: "green",
						});
						frm.reload_doc();
					})
		);
	});
}

const handlers = {
	refresh(frm) {
		add_welcome_email_button(frm);
	},
	visiting_card(frm) {
		read_card(frm, "visiting_card");
	},
	visiting_card_back(frm) {
		read_card(frm, "visiting_card_back");
	},
	website_url(frm) {
		read_links(frm);
	},
};
ADDRESS_FIELDS.forEach((f) => (handlers[f] = (frm) => update_maps_url(frm)));

frappe.ui.form.on("Business Profile", handlers);
})();
