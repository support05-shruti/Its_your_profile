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

	// After a new card is submitted, go to its edit page so the user can watch the scan finish
	const handle_success = web_form.handle_success.bind(web_form);
	web_form.handle_success = (data) => {
		if (web_form.is_new && data && data.name && data.visiting_card) {
			window.location.href = `/${web_form.route}/${data.name}/edit`;
			return;
		}
		handle_success(data);
	};

	web_form.after_load = () => {
		const doc = web_form.doc || {};
		if (!doc.name || !["Pending", "Processing"].includes(doc.card_scan_status)) return;

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
});
