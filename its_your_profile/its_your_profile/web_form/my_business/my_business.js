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
				// The card may have given us an address and a website: use them straight away
				update_maps_url();
				read_links(web_form.get_value("website_url"));
			});
	};
	web_form.on("visiting_card", (field, file_url) => read_card(file_url));
	web_form.on("visiting_card_back", (field, file_url) => read_card(file_url));

	// Build a Google Maps link from the address while the form is being filled.
	// A link the user pasted is kept; one we built is rebuilt when the address changes.
	const MAPS_PREFIX = "https://www.google.com/maps/search/?api=1&query=";
	const update_maps_url = () => {
		const current = web_form.get_value("google_maps_url") || "";
		if (current && !current.startsWith(MAPS_PREFIX)) return;
		if (!web_form.get_value("address_line") && !web_form.get_value("city")) return;

		const query = ["company_name", "address_line", "city", "state", "pincode"]
			.map((f) => (web_form.get_value(f) || "").replace(/\s+/g, " ").trim())
			.filter(Boolean)
			.join(", ");
		const url = MAPS_PREFIX + encodeURIComponent(query).replace(/%20/g, "+");
		if (url !== current) web_form.set_value("google_maps_url", url);
	};
	["company_name", "address_line", "city", "state", "pincode"].forEach((f) =>
		web_form.on(f, update_maps_url)
	);

	// Read the website's profile links as soon as a website is given, and add them to the table
	let last_links_url = null;
	const read_links = (url) => {
		url = (url || "").trim();
		if (!url || url === last_links_url) return;
		last_links_url = url;

		frappe
			.call({
				method: "its_your_profile.api.read_website_links",
				args: { url },
				freeze: true,
				freeze_message: __("Finding your links on the website..."),
			})
			.then(({ message: links }) => {
				const field = web_form.fields_dict.profile_links;
				const rows = (field.df.data = field.grid.get_data() || []);
				const key = (r) => `${r.platform}|${r.label || ""}`;
				const clean = (u) => (u || "").replace(/\/+$/, "").toLowerCase();
				const have = new Set(rows.map(key));
				const have_urls = new Set(rows.map((r) => clean(r.url)));

				let added = 0;
				(links || []).forEach((link) => {
					if (have.has(key(link)) || have_urls.has(clean(link.url))) return;
					rows.push({ idx: rows.length + 1, __islocal: true, ...link, label: link.label || "" });
					have.add(key(link));
					added++;
				});
				field.grid.refresh();

				frappe.show_alert({
					message: added
						? __("Added {0} links from the website. Please check them.", [added])
						: __("No new profile links found on the website."),
					indicator: added ? "green" : "orange",
				});
			});
	};
	web_form.on("website_url", (field, url) => read_links(url));

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
