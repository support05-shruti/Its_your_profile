// CHANGE NOTE 2026-11-13: dark mode for Frappe's own parts of this form. The Links table, its row
// editor, "Add row" and dropdowns are Frappe (Espresso) components; they only turn dark when <html>
// has data-theme="dark". Our site sets data-iyp-theme; mirror it here so they follow the same choice
// (my_business.css then tints them in the site's colours). Runs as soon as the script loads.
(function () {
	const root = document.documentElement;
	const sync = () => root.setAttribute("data-theme", root.getAttribute("data-iyp-theme") === "dark" ? "dark" : "light");
	sync();
	new MutationObserver(sync).observe(root, { attributes: true, attributeFilter: ["data-iyp-theme"] });
})();

frappe.ready(function () {
	const web_form = frappe.web_form;
	const POLL_MS = 3000;

	// CHANGE NOTE 2026-11-12: the same header and phone bottom bar as the dashboard, so "My information"
	// looks and works like the rest of the site. Frappe's own top bar (whose account menu didn't open
	// on phones and offered Desk links) is hidden while ours is shown. Styles in my_business.css.
	const add_site_nav = () => {
		if (document.querySelector(".iyp-wf-head")) return;
		const esc = (s) => String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
		const icon = (d) => `<svg class="iyp-wf-i" viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`;
		const I = {
			home: '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10"/>',
			grid: '<rect x="3.5" y="3.5" width="7" height="9" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="5" rx="1.5"/><rect x="13.5" y="11.5" width="7" height="9" rx="1.5"/><rect x="3.5" y="15.5" width="7" height="5" rx="1.5"/>',
			eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
			id: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M6 16a3 3 0 0 1 6 0M15 10h3M15 14h3"/>',
			share: '<circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.6-4.4M8.2 13.2l7.6 4.4"/>',
			logout: '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3"/><path d="M10 16l-4-4 4-4M6 12h10"/>',
			moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
			sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
		};
		const doc = web_form.doc || {};
		const page_url = doc.published && doc.route ? "/" + doc.route : null;
		const full_name = decodeURIComponent((frappe.get_cookie && frappe.get_cookie("full_name")) || "");
		const first = full_name.split(" ")[0] || __("Account");

		const head = document.createElement("header");
		head.className = "iyp-wf-head";
		head.innerHTML = `<div class="iyp-wf-row">
			<a class="iyp-wf-logo" href="/"><img class="iyp-brand-light" src="/assets/its_your_profile/images/iyp-logo.png" alt="It's Your Profile"><img class="iyp-brand-dark" src="/assets/its_your_profile/images/iyp-logo-dark.png" alt="It's Your Profile"></a>
			<nav class="iyp-wf-links">
				<a href="/">${__("Home")}</a>
				<a href="/notifications">${__("Dashboard")}</a>
				<a href="/account" class="on">${__("My information")}</a>
				<button type="button" class="iyp-wf-theme" aria-label="${__("Dark theme")}">${icon(I.moon)}${icon(I.sun)}</button>
				<div class="iyp-wf-me">
					<button type="button" class="iyp-wf-me-btn" aria-haspopup="true" aria-expanded="false"><span>${esc(first[0] || "?").toUpperCase()}</span><em>${esc(first)}</em></button>
					<div class="iyp-wf-menu" role="menu">
						<a href="/notifications">${icon(I.grid)}${__("Dashboard")}</a>
						<a href="/account">${icon(I.id)}${__("My information")}</a>
						<a href="/">${icon(I.home)}${__("Home")}</a>
						<hr>
						<a href="/logout">${icon(I.logout)}${__("Log out")}</a>
					</div>
				</div>
			</nav>
		</div>`;
		document.body.prepend(head);

		const dock = document.createElement("nav");
		dock.className = "iyp-wf-dock";
		dock.innerHTML = `<a href="/">${icon(I.home)}${__("Home")}</a>
			<a href="/notifications">${icon(I.grid)}${__("Dashboard")}</a>
			${page_url ? `<a href="${esc(page_url)}" target="_blank" rel="noopener">${icon(I.eye)}${__("My page")}</a>` : ""}
			<a href="/account" class="on">${icon(I.id)}${__("My info")}</a>
			${page_url ? `<button type="button" data-wf-share>${icon(I.share)}${__("Share")}</button>` : ""}`;
		document.body.appendChild(dock);
		document.documentElement.classList.add("iyp-own-nav");

		// Account menu
		const me_btn = head.querySelector(".iyp-wf-me-btn");
		const menu = head.querySelector(".iyp-wf-menu");
		me_btn.addEventListener("click", (e) => {
			e.stopPropagation();
			const open = !menu.classList.contains("open");
			menu.classList.toggle("open", open);
			me_btn.setAttribute("aria-expanded", open ? "true" : "false");
		});
		document.addEventListener("click", () => {
			menu.classList.remove("open");
			me_btn.setAttribute("aria-expanded", "false");
		});

		// Light / dark, the same saved choice as every page
		head.querySelector(".iyp-wf-theme").addEventListener("click", () => {
			const root = document.documentElement;
			const next = root.getAttribute("data-iyp-theme") === "dark" ? "light" : "dark";
			root.setAttribute("data-iyp-theme", next);
			try { localStorage.setItem("iyp-theme", next); } catch (e) { /* storage blocked */ }
		});

		const share = dock.querySelector("[data-wf-share]");
		if (share) {
			share.addEventListener("click", () => {
				const url = location.origin + page_url;
				if (window.iypShare) window.iypShare(doc.company_name || document.title, url);
				else window.open(url, "_blank", "noopener");
			});
		}
	};
	add_site_nav();

	// "Add your logo" on the business page and the dashboard opens this form at #logo (2026-11-12):
	// scroll to the logo field and highlight it
	if (location.hash === "#logo") {
		setTimeout(() => {
			const field = web_form.fields_dict.company_logo;
			if (!field) return;
			const section = field.$wrapper.closest(".form-section").get(0);
			if (section) section.classList.add("in");
			field.$wrapper.get(0).scrollIntoView({ behavior: "smooth", block: "center" });
			field.$wrapper.addClass("iyp-logo-focus");
			setTimeout(() => field.$wrapper.removeClass("iyp-logo-focus"), 2600);
		}, 600);
	}

	// CHANGE NOTE 2026-11-06: page decoration that goes with my_business.css: a 1-2-3 steps strip
	// and perks under the introduction, friendlier upload/save labels, and sections that rise in
	// as they scroll into view. Purely visual; the form works the same without it.
	// CHANGE NOTE 2026-11-07: "My information" (editing a page) shows only the business details:
	// no visiting card upload, scan status, scan steps or "from your visiting card" banner. This also
	// hides the card section on sites where the updated web form hasn't been migrated yet.
	["visiting_card", "visiting_card_back", "card_scan_status"].forEach((fieldname) => {
		const field = web_form.fields_dict[fieldname];
		if (field) field.$wrapper.closest(".form-section").hide();
	});

	const decorate = () => {
		const head = document.querySelector(".web-form-head");
		if (head && web_form.is_new && !head.querySelector(".iyp-steps")) {
			const step = web_form.is_new ? 0 : 1;
			const labels = [__("Scan your card"), __("Check the details"), __("Go live & get found")];
			const steps = document.createElement("div");
			steps.className = "iyp-steps";
			labels.forEach((label, i) => {
				if (i) steps.insertAdjacentHTML("beforeend", '<span class="iyp-step-line" aria-hidden="true"></span>');
				const el = document.createElement("div");
				el.className = "iyp-step" + (i === step ? " on" : "");
				el.style.setProperty("--i", i);
				el.innerHTML = `<b>${i + 1}</b>`;
				el.append(label);
				steps.append(el);
			});
			const perks = document.createElement("div");
			perks.className = "iyp-perks";
			[__("⚡ Ready in a minute"), __("🤖 AI fills in the details"), __("🎁 Free for 6 months")].forEach((text, i) => {
				const el = document.createElement("span");
				el.style.setProperty("--i", i);
				el.textContent = text;
				perks.append(el);
			});
			head.append(steps, perks);

			// 2026-11-07: the "easy for AI to find?" banner moved here from the business pages
			const banner = document.createElement("div");
			banner.className = "iyp-ai-banner";
			banner.innerHTML = `<strong><span aria-hidden="true">✦</span> ${__("Is your business easy for")} <em>${__("AI to find?")}</em></strong>
				<p>${__("Get a free profile page from your visiting card, in a minute.")}</p>
				<a href="/">${__("Learn more")} →</a>`;
			head.append(banner);
		}

		const label_attach = (fieldname, text) => {
			const field = web_form.fields_dict[fieldname];
			const button = field && field.$wrapper.find(".btn-attach").get(0);
			if (button) button.textContent = text;
		};
		label_attach("visiting_card", __("📷 Upload your visiting card photo"));
		label_attach("visiting_card_back", __("＋ Add the back side (optional)"));
		label_attach("company_logo", __("＋ Upload your logo"));
		if (web_form.is_new) $(".web-form-footer .submit-btn").text(__("✨ Create my page"));

		// Sections rise in one after another as they come into view
		const sections = document.querySelectorAll(".web-form-wrapper .form-section");
		if (!("IntersectionObserver" in window) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
		document.documentElement.classList.add("iyp-js");
		const io = new IntersectionObserver((entries) => {
			entries.filter((e) => e.isIntersecting).forEach((e, i) => {
				e.target.style.transitionDelay = `${i * 90}ms`;
				e.target.classList.add("in");
				io.unobserve(e.target);
				setTimeout(() => (e.target.style.transitionDelay = ""), 900 + i * 90);
			});
		}, { threshold: 0.05, rootMargin: "0px 0px -30px 0px" });
		sections.forEach((s) => io.observe(s));
	};
	decorate();

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
			.then(({ message }) => {
				const { _links: card_links = [], ...values } = message || {};
				// Only fill empty boxes, so anything already typed (or read from the front) is kept
				const filled = Object.entries(values).filter(([fieldname, value]) => {
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
				if (add_links(card_links)) {
					frappe.show_alert({ message: __("Added links printed on the card."), indicator: "green" });
				}
				// The card may have given us an address and a website: use them straight away
				update_maps_url();
				read_links(web_form.get_value("website_url"));
			});
	};
	web_form.on("visiting_card", (field, file_url) => read_card(file_url));
	web_form.on("visiting_card_back", (field, file_url) => read_card(file_url));

	// Frappe's Upload → crop window has no rotate button, but its Cropper (window.cropper) can rotate;
	// add ↺ ↻ buttons there, as on the desk form. The turn is kept when Crop is clicked.
	const add_cropper_rotate_buttons = () => {
		document.querySelectorAll(".image-cropper-actions").forEach((actions) => {
			if (actions.querySelector(".cropper-rotate")) return;
			const $buttons = $(`<div class="cropper-rotate btn-group ml-2">
				<button type="button" class="btn btn-default btn-sm" data-degrees="-90" title="${__("Rotate Left")}">↺</button>
				<button type="button" class="btn btn-default btn-sm" data-degrees="90" title="${__("Rotate Right")}">↻</button>
			</div>`);
			$buttons.find("button").on("click", function () {
				rotate_cropper($(this).data("degrees"));
			});
			$(actions).children().first().css("display", "flex").append($buttons);
		});
	};

	// Turn the photo itself and load it back into the cropper, which then fits it to the box.
	// (Cropper's own rotate() leaves the turned photo overflowing the box.)
	const rotate_cropper = (degrees) => {
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
	};

	new MutationObserver(add_cropper_rotate_buttons).observe(document.body, { childList: true, subtree: true });

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

	// A card photo chosen on the home page (2026-11-06) waits in this tab's sessionStorage, because
	// the home page cannot upload before login. Upload and read it now, once, on a new form.
	const PENDING_KEY = "iyp-pending-card";
	let pending = null;
	try {
		pending = sessionStorage.getItem(PENDING_KEY);
		sessionStorage.removeItem(PENDING_KEY);
	} catch (e) {
		/* storage blocked: nothing is waiting */
	}
	if (pending && web_form.is_new && !web_form.get_value("visiting_card")) {
		fetch(pending)
			.then((r) => r.blob())
			.then((blob) => upload_photo("visiting_card", blob))
			.catch(() => frappe.msgprint(__("Please attach your visiting card photo again.")));
	}

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

	// Add links to the Profile Links table, skipping platforms (and URLs) it already has
	const add_links = (links) => {
		const field = web_form.fields_dict.profile_links;
		if (!field || !links.length) return 0;
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
		return added;
	};

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

				const added = add_links(links);

				frappe.show_alert({
					message: added
						? __("Added {0} links from the website. Please check them.", [added])
						: __("No new profile links found on the website."),
					indicator: added ? "green" : "orange",
				});
			});
	};
	web_form.on("website_url", (field, url) => read_links(url));

	// CHANGE NOTE 2026-11-07: LinkedIn is compulsory. Save is blocked until the Profile Links table
	// has a LinkedIn row with a link (usually filled in automatically from the card, the website or
	// a web search).
	web_form.validate = () => {
		const rows = (web_form.fields_dict.profile_links && web_form.fields_dict.profile_links.grid.get_data()) || [];
		const linkedin = rows.find((r) => r.platform === "LinkedIn" && (r.url || "").trim());
		if (linkedin) return true;
		frappe.msgprint({
			title: __("LinkedIn is required"),
			indicator: "orange",
			message: __(
				"Please add your LinkedIn page under <b>Links</b>: click <b>Add Row</b>, choose <b>LinkedIn</b> and paste the link (for example https://www.linkedin.com/company/your-company)."
			),
		});
		return false;
	};

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
