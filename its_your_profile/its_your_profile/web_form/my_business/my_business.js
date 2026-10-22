frappe.ready(function () {
	const web_form = frappe.web_form;
	const POLL_MS = 3000;

	// Open the camera directly on phones when picking the visiting card
	new MutationObserver(() => {
		document.querySelectorAll('input[type="file"]:not([capture])').forEach((input) => {
			input.setAttribute("accept", "image/*");
			input.setAttribute("capture", "environment");
		});
	}).observe(document.body, { childList: true, subtree: true });

	// Read each side as soon as it is attached, so the details are filled in before Save
	const read_card = (file_url) => {
		if (!file_url) return;
		frappe
			.call({
				method: "its_your_profile.api.read_visiting_card",
				args: { file_url },
				freeze: true,
				freeze_message: __("Reading your visiting card..."),
			})
			.then(({ message: values }) => {
				// Only fill empty boxes, so anything already typed (or read from the front) is kept
				const filled = Object.entries(values || {}).filter(([fieldname, value]) => {
					if (web_form.get_value(fieldname) || !web_form.fields_dict[fieldname]) return false;
					web_form.set_value(fieldname, value);
					return true;
				});
				frappe.show_alert({
					message: filled.length
						? __("Filled {0} fields from the card. Please check them and click Save.", [filled.length])
						: __("No new details found on this side of the card."),
					indicator: filled.length ? "green" : "orange",
				});
			});
	};
	web_form.on("visiting_card", (field, file_url) => read_card(file_url));
	web_form.on("visiting_card_back", (field, file_url) => read_card(file_url));

	// After a new card is submitted, go to its edit page so the user can watch the scan finish
	const handle_success = web_form.handle_success.bind(web_form);
	web_form.handle_success = (data) => {
		if (web_form.is_new && data && data.name && data.card_scan_status === "Pending") {
			window.location.href = `/${web_form.route}/${data.name}/edit`;
			return;
		}
		handle_success(data);
	};

	let polling = false;
	const watch_scan = () => {
		const doc = web_form.doc || {};
		if (polling || !doc.name || !["Pending", "Processing"].includes(doc.card_scan_status)) return;
		polling = true;

		frappe.show_alert({ message: __("Reading your visiting card..."), indicator: "blue" });
		const timer = setInterval(() => {
			frappe
				.call("its_your_profile.api.get_scan_status", { name: doc.name })
				.then(({ message: status }) => {
					if (status === "Completed") {
						clearInterval(timer);
						window.location.reload();
					} else if (status === "Failed") {
						clearInterval(timer);
						frappe.msgprint(
							__("We couldn't read the card. Please fill in the details manually.")
						);
					}
				});
		}, POLL_MS);
	};

	// The form may finish loading before this script runs, so check now as well as on after_load
	web_form.after_load = watch_scan;
	watch_scan();
});
