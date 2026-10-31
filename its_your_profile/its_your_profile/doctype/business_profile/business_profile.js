// Copyright (c) 2026, SoftWorld Solutions Pvt. Ltd and contributors
// For license information, please see license.txt

// Wrapped so the desk can load this script more than once without "already declared" errors
(() => {
const MAPS_PREFIX = "https://www.google.com/maps/search/?api=1&query=";
// preview field → the attach field it shows
const CARD_PREVIEWS = {
	visiting_card_preview: "visiting_card",
	visiting_card_back_preview: "visiting_card_back",
};

// Show the card photos as small thumbnails with rotate buttons; click one to open it full size
function style_card_previews(frm) {
	Object.entries(CARD_PREVIEWS).forEach(([preview, source]) => {
		const field = frm.fields_dict[preview];
		if (!field) return;
		field.$wrapper
			.find("img")
			.css({ "max-width": "260px", "max-height": "160px", "object-fit": "contain", cursor: "zoom-in" })
			.addClass("border rounded")
			.off("click.card")
			.on("click.card", function () {
				window.open(this.src, "_blank");
			});

		field.$wrapper.find(".card-rotate").remove();
		if (frm.is_new() || !frm.doc[source]) return;
		const $buttons = $(`<div class="card-rotate mt-2">
			<button class="btn btn-xs btn-default" data-direction="left">↺ ${__("Rotate Left")}</button>
			<button class="btn btn-xs btn-default ml-2" data-direction="right">↻ ${__("Rotate Right")}</button>
		</div>`).appendTo(field.$wrapper);
		$buttons.find("button").on("click", function () {
			rotate_card(frm, source, $(this).data("direction"));
		});
	});
}

// Frappe's Upload → crop window has no rotate button, but its Cropper (window.cropper) can rotate;
// add ↺ ↻ buttons there while a Business Profile is open. The turn is kept when Crop is clicked.
function add_cropper_rotate_buttons() {
	document.querySelectorAll(".image-cropper-actions").forEach((actions) => {
		if (actions.querySelector(".cropper-rotate")) return;
		if (!window.cur_frm || cur_frm.doctype !== "Business Profile") return;
		const $buttons = $(`<div class="cropper-rotate btn-group ml-2">
			<button type="button" class="btn btn-default btn-sm" data-degrees="-90" title="${__("Rotate Left")}">↺</button>
			<button type="button" class="btn btn-default btn-sm" data-degrees="90" title="${__("Rotate Right")}">↻</button>
		</div>`);
		$buttons.find("button").on("click", function () {
			rotate_cropper($(this).data("degrees"));
		});
		$(actions).children().first().css("display", "flex").append($buttons);
	});
}

// Turn the photo itself and load it back into the cropper, which then fits it to the box.
// (Cropper's own rotate() leaves the turned photo overflowing the box.)
function rotate_cropper(degrees) {
	const cropper = window.cropper;
	if (!cropper) return;
	const source = cropper.element;
	const width = source.naturalWidth;
	const height = source.naturalHeight;

	const canvas = document.createElement("canvas");
	canvas.width = height;
	canvas.height = width;
	const ctx = canvas.getContext("2d");
	ctx.translate(height / 2, width / 2);
	ctx.rotate((degrees * Math.PI) / 180);
	ctx.drawImage(source, -width / 2, -height / 2);

	// Frappe's cropper builds a new Cropper on every image load, which would replace the working one
	source.onload = null;
	cropper.replace(canvas.toDataURL("image/jpeg", 0.95));
}

if (!window.__card_cropper_observer) {
	window.__card_cropper_observer = new MutationObserver(add_cropper_rotate_buttons);
	window.__card_cropper_observer.observe(document.body, { childList: true, subtree: true });
}

function rotate_card(frm, fieldname, direction) {
	const run = () =>
		frappe
			.call({
				method: "its_your_profile.api.rotate_visiting_card",
				args: { name: frm.doc.name, fieldname, direction },
				freeze: true,
				freeze_message: __("Rotating..."),
			})
			.then(() => frm.reload_doc());
	// Unsaved edits would be lost by the reload afterwards, so save first
	frm.is_dirty() ? frm.save().then(run) : run();
}
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
		.then(({ message }) => {
			const links = (message && message.links) || [];
			// The website's own map beats one we built from the address, but not one typed in
			const current_map = frm.doc.google_maps_url || "";
			if (message && message.map_url && (!current_map || current_map.startsWith(MAPS_PREFIX))) {
				frm.set_value("google_maps_url", message.map_url);
			}

			const key = (r) => `${r.platform}|${r.label || ""}`;
			const clean = (u) => (u || "").replace(/\/+$/, "").toLowerCase();
			const have = new Set((frm.doc.profile_links || []).map(key));
			const have_urls = new Set((frm.doc.profile_links || []).map((r) => clean(r.url)));

			let added = 0;
			links.forEach((link) => {
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

// Send or resend the welcome email by hand
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

// Read the attached card again, e.g. after attaching a clearer photo; fills only empty fields
function add_read_again_button(frm) {
	if (frm.is_new() || !(frm.doc.visiting_card || frm.doc.visiting_card_back)) return;
	frm.add_custom_button(__("Read Card Again"), () => {
		if (frm.doc.visiting_card) read_card(frm, "visiting_card");
		if (frm.doc.visiting_card_back) read_card(frm, "visiting_card_back");
	});
}

// Read the website again (or search Google for the company) and rewrite the AI Summary
function add_refresh_summary_button(frm) {
	if (frm.is_new() || !frm.doc.website_url) return;
	frm.add_custom_button(__("Refresh AI Summary"), () => {
		const run = () =>
			frappe
				.call({
					method: "its_your_profile.api.refresh_ai_summary",
					args: { name: frm.doc.name },
					freeze: true,
					freeze_message: __("Reading the website and writing a summary..."),
				})
				.then(({ message }) => {
					frappe.show_alert({
						message: message.ai_summary
							? __("AI Summary updated")
							: __("Could not find enough about this business for a summary"),
						indicator: message.ai_summary ? "green" : "orange",
					});
					frm.reload_doc();
				});
		// Unsaved edits would be lost by the reload afterwards, so save first
		frm.is_dirty() ? frm.save().then(run) : run();
	});
}

const handlers = {
	refresh(frm) {
		add_welcome_email_button(frm);
		add_read_again_button(frm);
		add_refresh_summary_button(frm);
		style_card_previews(frm);
	},
	visiting_card(frm) {
		read_card(frm, "visiting_card");
		// The preview image is redrawn after the new value is set
		setTimeout(() => style_card_previews(frm), 300);
	},
	visiting_card_back(frm) {
		read_card(frm, "visiting_card_back");
		setTimeout(() => style_card_previews(frm), 300);
	},
	website_url(frm) {
		read_links(frm);
	},
};
ADDRESS_FIELDS.forEach((f) => (handlers[f] = (frm) => update_maps_url(frm)));

frappe.ui.form.on("Business Profile", handlers);
})();
