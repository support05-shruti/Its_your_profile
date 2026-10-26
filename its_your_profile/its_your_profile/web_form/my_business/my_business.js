frappe.ready(function () {
	const web_form = frappe.web_form;
	const POLL_MS = 3000;

	// Read each side as soon as it is attached, so the details are filled in before Save.
	// The same photo can arrive twice (Take Photo sets the field, which also fires its change).
	const read_urls = new Set();
	const read_card = (file_url) => {
		if (!file_url || read_urls.has(file_url)) return;
		read_urls.add(file_url);
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

	// "Take Photo" on phones: opens the camera straight away. The normal Attach button stays
	// for picking a photo from the gallery.
	const MAX_SIDE = 1600; // px; plenty for the AI to read, and a phone photo uploads in seconds

	const shrink = (file) =>
		new Promise((resolve) => {
			const img = new Image();
			img.onload = () => {
				const scale = Math.min(1, MAX_SIDE / Math.max(img.width, img.height));
				const canvas = document.createElement("canvas");
				canvas.width = Math.round(img.width * scale);
				canvas.height = Math.round(img.height * scale);
				canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
				URL.revokeObjectURL(img.src);
				canvas.toBlob((blob) => resolve(blob || file), "image/jpeg", 0.85);
			};
			img.onerror = () => resolve(file); // a format the browser can't draw: send it as it is
			img.src = URL.createObjectURL(file);
		});

	const upload_photo = async (fieldname, file) => {
		frappe.freeze(__("Uploading photo..."));
		try {
			const form = new FormData();
			form.append("file", await shrink(file), `visiting-card-${Date.now()}.jpg`);
			form.append("is_private", "1");
			const response = await fetch("/api/method/upload_file", {
				method: "POST",
				headers: { "X-Frappe-CSRF-Token": frappe.csrf_token, Accept: "application/json" },
				body: form,
			});
			const data = await response.json();
			if (!response.ok || !data.message) throw new Error(data.exception || response.statusText);
			const file_url = data.message.file_url;
			await web_form.set_value(fieldname, file_url);
			frappe.unfreeze();
			read_card(file_url);
		} catch (e) {
			frappe.unfreeze();
			frappe.msgprint(__("The photo could not be uploaded. Please try again, or use Attach."));
		}
	};

	const on_phone = window.matchMedia("(pointer: coarse)").matches;
	["visiting_card", "visiting_card_back"].forEach((fieldname) => {
		const field = web_form.fields_dict[fieldname];
		if (!on_phone || !field) return;

		const input = document.createElement("input");
		input.type = "file";
		input.accept = "image/*";
		input.setAttribute("capture", "environment"); // the back camera
		input.hidden = true;
		input.addEventListener("change", () => {
			if (input.files[0]) upload_photo(fieldname, input.files[0]);
			input.value = "";
		});

		const button = document.createElement("button");
		button.type = "button";
		button.className = "btn btn-primary btn-sm mt-2";
		button.textContent = __("📷 Take Photo");
		button.addEventListener("click", () => input.click());

		field.$wrapper.append(button, input);
	});

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
			.then(({ message }) => {
				const links = (message && message.links) || [];
				// The website's own map beats one we built from the address, but not one typed in
				const current_map = web_form.get_value("google_maps_url") || "";
				if (message && message.map_url && (!current_map || current_map.startsWith(MAPS_PREFIX))) {
					web_form.set_value("google_maps_url", message.map_url);
				}

				const field = web_form.fields_dict.profile_links;
				const rows = (field.df.data = field.grid.get_data() || []);
				const key = (r) => `${r.platform}|${r.label || ""}`;
				const clean = (u) => (u || "").replace(/\/+$/, "").toLowerCase();
				const have = new Set(rows.map(key));
				const have_urls = new Set(rows.map((r) => clean(r.url)));

				let added = 0;
				links.forEach((link) => {
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
