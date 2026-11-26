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

	// 2026-11-17: a page that already exists (it has a name) is never shown as "new", even if Frappe says so
	const is_new_page = !!web_form.is_new && !(web_form.doc && web_form.doc.name);
	const decorate = () => {
		const head = document.querySelector(".web-form-head");
		if (head && is_new_page && !head.querySelector(".iyp-steps")) {
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
			[__("⚡ Ready in a minute"), __("🤖 AI fills in the details"), __("🎁 Free for 3 months")].forEach((text, i) => {
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
		if (is_new_page) $(".web-form-footer .submit-btn").text(__("✨ Create my page"));

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
	// 2026-11-17: only listen to fields this form has. The visiting card fields were removed from the
	// form, and web_form.on() on a missing field threw "Cannot read properties of undefined (reading
	// 'df')", which stopped the rest of this script (links, LinkedIn check, scan polling).
	const on_field = (fieldname, handler) => web_form.fields_dict[fieldname] && web_form.on(fieldname, handler);
	on_field("visiting_card", (field, file_url) => read_card(file_url));
	on_field("visiting_card_back", (field, file_url) => read_card(file_url));

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
		on_field(f, update_maps_url)
	);

	// CHANGE NOTE 2026-11-17: our own editor for the Profile Links table. Frappe v16's table in web
	// forms did not show the saved rows on the edit page (only newly added ones), and its "Editing
	// Row" panel opened empty and out of place, so links could not be added or changed. Frappe's table
	// stays on the page, hidden, and keeps the data: this editor edits the same row objects
	// (field.df.data), so Save, add_links() and the LinkedIn check work exactly as before.
	const PLATFORMS = ["LinkedIn", "Facebook", "Google Profile", "BNI", "Other"];
	const links_field = web_form.fields_dict.profile_links;
	const link_rows = () => {
		if (!links_field) return [];
		if (!Array.isArray(links_field.df.data)) links_field.df.data = (links_field.grid.get_data() || []).slice();
		return links_field.df.data;
	};
	let render_links = () => {};
	if (links_field) {
		const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
		const box = document.createElement("div");
		box.className = "iyp-links";
		box.innerHTML = `
			<div class="iyp-links-label">${__("Profile Links")}</div>
			<p class="iyp-links-help">${__("LinkedIn, Facebook, Google Profile, BNI or any other page. LinkedIn is required.")}</p>
			<div class="iyp-links-list"></div>
			<div class="iyp-links-actions">
				<button type="button" class="iyp-links-add">＋ ${__("Add link")}</button>
			</div>`;
		links_field.$wrapper.addClass("iyp-links-grid-hidden").after(box);
		const list = box.querySelector(".iyp-links-list");

		// Frappe's (hidden) table reads field.df.data when the form is saved; no need to redraw it
		const changed = () => web_form.make_form_dirty && web_form.make_form_dirty();
		render_links = () => {
			const rows = link_rows();
			rows.forEach((r, i) => (r.idx = i + 1));
			list.innerHTML = rows.length
				? rows
						.map(
							(r, i) => `
				<div class="iyp-link-row" data-i="${i}">
					<select class="iyp-link-platform" aria-label="${__("Platform")}">
						<option value="">${__("Choose…")}</option>
						${PLATFORMS.map((p) => `<option value="${p}"${r.platform === p ? " selected" : ""}>${__(p)}</option>`).join("")}
					</select>
					<input class="iyp-link-label" type="text" value="${esc(r.label)}" placeholder="${__("Name (optional)")}" aria-label="${__("Name")}">
					<input class="iyp-link-url" type="url" value="${esc(r.url)}" placeholder="https://…" aria-label="${__("Link")}">
					<button type="button" class="iyp-link-del" title="${__("Remove")}" aria-label="${__("Remove")}">✕</button>
				</div>`
						)
						.join("")
				: `<div class="iyp-links-empty">${__("No links yet. Links on the visiting card are added by themselves; to add one more, click “Add link”.")}</div>`;
		};
		list.addEventListener("input", (e) => {
			const row_el = e.target.closest(".iyp-link-row");
			if (!row_el) return;
			const row = link_rows()[+row_el.dataset.i];
			if (!row) return;
			if (e.target.classList.contains("iyp-link-label")) row.label = e.target.value;
			if (e.target.classList.contains("iyp-link-url")) row.url = e.target.value.trim();
			web_form.make_form_dirty && web_form.make_form_dirty();
		});
		list.addEventListener("change", (e) => {
			const row_el = e.target.closest(".iyp-link-row");
			if (!row_el || !e.target.classList.contains("iyp-link-platform")) return;
			const row = link_rows()[+row_el.dataset.i];
			if (row) row.platform = e.target.value;
			changed();
		});
		list.addEventListener("click", (e) => {
			const del = e.target.closest(".iyp-link-del");
			if (!del) return;
			const i = +del.closest(".iyp-link-row").dataset.i;
			const row = link_rows()[i] || {};
			const what = [row.platform, row.url].filter(Boolean).join(" · ");
			// 2026-11-18: ask before removing; a link with nothing typed in goes straight away
			const remove = () => {
				link_rows().splice(i, 1);
				render_links();
				changed();
			};
			if (!(row.url || "").trim() && !(row.label || "").trim()) return remove();
			frappe.confirm(
				__("Do you really want to delete this link?") + (what ? `<br><b>${esc(what)}</b>` : ""),
				remove
			);
		});
		box.querySelector(".iyp-links-add").addEventListener("click", () => {
			const rows = link_rows();
			const has_linkedin = rows.some((r) => r.platform === "LinkedIn");
			rows.push({ idx: rows.length + 1, __islocal: true, platform: has_linkedin ? "" : "LinkedIn", label: "", url: "" });
			render_links();
			changed();
			const last = list.querySelector(".iyp-link-row:last-child .iyp-link-url");
			if (last) last.focus();
		});
		render_links();
	}

	// CHANGE NOTE 2026-11-18: owners add, change and remove their own FAQs here (question + answer),
	// built like the Links editor above: Frappe's FAQs table is hidden and keeps the data
	// (field.df.data) for Save. Empty when the AI hasn't written any yet; the page then shows basic
	// questions made from its facts.
	const faqs_field = web_form.fields_dict.faqs;
	const faq_rows = () => {
		if (!faqs_field) return [];
		if (!Array.isArray(faqs_field.df.data)) faqs_field.df.data = (faqs_field.grid.get_data() || []).slice();
		return faqs_field.df.data;
	};
	let render_faqs = () => {};
	if (faqs_field) {
		const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
		const box = document.createElement("div");
		box.className = "iyp-links iyp-faqs";
		box.innerHTML = `
			<div class="iyp-links-label">${__("Questions & answers")}</div>
			<p class="iyp-links-help">${__("Questions your customers ask, with your answers. Shown on your page and read by Google and AI search.")}</p>
			<div class="iyp-faq-list"></div>
			<div class="iyp-links-actions">
				<button type="button" class="iyp-links-add iyp-faq-add">＋ ${__("Add question")}</button>
			</div>`;
		faqs_field.$wrapper.addClass("iyp-links-grid-hidden").after(box);
		const list = box.querySelector(".iyp-faq-list");
		const dirty = () => web_form.make_form_dirty && web_form.make_form_dirty();

		render_faqs = () => {
			const rows = faq_rows();
			rows.forEach((r, i) => (r.idx = i + 1));
			list.innerHTML = rows.length
				? rows
						.map(
							(r, i) => `
				<div class="iyp-faq-row" data-i="${i}">
					<div class="iyp-faq-num">${i + 1}</div>
					<div class="iyp-faq-fields">
						<input class="iyp-faq-q" type="text" value="${esc(r.question)}" placeholder="${__("Question, e.g. Do you deliver outside Pune?")}" aria-label="${__("Question")}">
						<textarea class="iyp-faq-a" rows="2" placeholder="${__("Your answer")}" aria-label="${__("Answer")}">${esc(r.answer)}</textarea>
					</div>
					<button type="button" class="iyp-link-del" title="${__("Remove")}" aria-label="${__("Remove")}">✕</button>
				</div>`
						)
						.join("")
				: `<div class="iyp-links-empty">${__("No questions yet. Click “Add question” to add one.")}</div>`;
		};
		list.addEventListener("input", (e) => {
			const row_el = e.target.closest(".iyp-faq-row");
			const row = row_el && faq_rows()[+row_el.dataset.i];
			if (!row) return;
			if (e.target.classList.contains("iyp-faq-q")) row.question = e.target.value;
			if (e.target.classList.contains("iyp-faq-a")) row.answer = e.target.value;
			dirty();
		});
		list.addEventListener("click", (e) => {
			const del = e.target.closest(".iyp-link-del");
			if (!del) return;
			const i = +del.closest(".iyp-faq-row").dataset.i;
			const row = faq_rows()[i] || {};
			// 2026-11-18: ask before removing; an empty question goes straight away
			const remove = () => {
				faq_rows().splice(i, 1);
				render_faqs();
				dirty();
			};
			if (!(row.question || "").trim() && !(row.answer || "").trim()) return remove();
			frappe.confirm(
				__("Do you really want to delete this question?") +
					((row.question || "").trim() ? `<br><b>${esc(row.question.trim())}</b>` : ""),
				remove
			);
		});
		box.querySelector(".iyp-faq-add").addEventListener("click", () => {
			const rows = faq_rows();
			rows.push({ idx: rows.length + 1, __islocal: true, question: "", answer: "" });
			render_faqs();
			dirty();
			const last = list.querySelector(".iyp-faq-row:last-child .iyp-faq-q");
			if (last) last.focus();
		});
		render_faqs();
	}

	// CHANGE NOTE 2026-11-26: Testimonials and Certificates, for paid plans only. Same kind of editor
	// as the FAQs (Frappe's tables stay hidden and keep the data in field.df.data for Save). Without
	// an active plan the section shows a lock with "See plans" instead; the server refuses changes
	// too (BusinessProfile.guard_paid_sections), so this is only the friendly side.
	const esc_html = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
	const table_rows = (field) => {
		if (!field) return [];
		if (!Array.isArray(field.df.data)) field.df.data = (field.grid.get_data() || []).slice();
		return field.df.data;
	};
	const paid_editors = [];
	const make_paid_editor = (opts) => {
		const field = web_form.fields_dict[opts.fieldname];
		if (!field) return null;
		const rows = () => table_rows(field);
		const box = document.createElement("div");
		box.className = "iyp-links iyp-faqs iyp-paid-box";
		field.$wrapper.addClass("iyp-links-grid-hidden").after(box);
		const dirty = () => web_form.make_form_dirty && web_form.make_form_dirty();
		const editor = { opts, rows, render: () => {}, paid: false };

		const draw_locked = () => {
			const kept = rows().length;
			box.innerHTML = `
				<div class="iyp-links-label">${opts.label} <span class="iyp-paid-tag">${__("Paid plan")}</span></div>
				<div class="iyp-paid-lock">
					<span class="iyp-paid-lock-icon" aria-hidden="true">🔒</span>
					<div>
						<b>${opts.locked_title}</b>
						<p>${__("Available on the paid plan (₹1,200 + GST for 10 years).")}</p>
						${kept ? `<p>${__("Your {0} saved items are kept and show on your page again once your plan is active.", [kept])}</p>` : ""}
						<a class="iyp-links-add" href="/#pricing" target="_blank" rel="noopener">${__("See plans")}</a>
					</div>
				</div>`;
		};

		const draw_open = () => {
			box.innerHTML = `
				<div class="iyp-links-label">${opts.label}</div>
				<p class="iyp-links-help">${opts.help}</p>
				<div class="iyp-faq-list"></div>
				<div class="iyp-links-actions"><button type="button" class="iyp-links-add">＋ ${opts.add_text}</button></div>`;
			const list = box.querySelector(".iyp-faq-list");
			editor.render = () => {
				rows().forEach((r, i) => (r.idx = i + 1));
				list.innerHTML = rows().length
					? rows()
							.map(
								(r, i) => `
					<div class="iyp-faq-row" data-i="${i}">
						<div class="iyp-faq-num">${i + 1}</div>
						<div class="iyp-faq-fields">${opts.inputs
							.map((inp) =>
								inp.type === "file"
									? `<div class="iyp-paid-file">
										${r[inp.key] ? `<a href="${esc_html(r[inp.key])}" target="_blank" rel="noopener">📎 ${esc_html(r[inp.key].split("/").pop())}</a>` : `<span>${__("No file yet")}</span>`}
										<button type="button" class="iyp-links-add iyp-paid-upload" data-key="${inp.key}">${r[inp.key] ? __("Change file") : inp.placeholder}</button>
									</div>`
									: inp.type === "textarea"
									? `<textarea data-key="${inp.key}" rows="3" placeholder="${inp.placeholder}" aria-label="${inp.placeholder}">${esc_html(r[inp.key])}</textarea>`
									: `<input data-key="${inp.key}" type="text" value="${esc_html(r[inp.key])}" placeholder="${inp.placeholder}" aria-label="${inp.placeholder}">`
							)
							.join("")}</div>
						<button type="button" class="iyp-link-del" title="${__("Remove")}" aria-label="${__("Remove")}">✕</button>
					</div>`
							)
							.join("")
					: `<div class="iyp-links-empty">${opts.empty_text}</div>`;
			};
			list.addEventListener("input", (e) => {
				const row_el = e.target.closest(".iyp-faq-row");
				const row = row_el && rows()[+row_el.dataset.i];
				if (!row || !e.target.dataset.key) return;
				row[e.target.dataset.key] = e.target.value;
				dirty();
			});
			list.addEventListener("click", (e) => {
				const row_el = e.target.closest(".iyp-faq-row");
				if (!row_el) return;
				const i = +row_el.dataset.i;
				const row = rows()[i];
				const upload = e.target.closest(".iyp-paid-upload");
				if (upload) {
					if (!frappe.ui.FileUploader) return frappe.msgprint(__("File upload is not available here. Please try again."));
					new frappe.ui.FileUploader({
						allow_multiple: false,
						restrictions: { allowed_file_types: [".jpg", ".jpeg", ".png", ".webp", ".pdf"] },
						on_success: (file) => {
							row[upload.dataset.key] = file.file_url;
							editor.render();
							dirty();
						},
					});
					return;
				}
				if (!e.target.closest(".iyp-link-del")) return;
				const remove = () => {
					rows().splice(i, 1);
					editor.render();
					dirty();
				};
				const title = (row && row[opts.inputs[0].key]) || "";
				if (!title.trim()) return remove();
				frappe.confirm(__("Do you really want to delete this?") + `<br><b>${esc_html(title.trim())}</b>`, remove);
			});
			box.querySelector(".iyp-faq-list + .iyp-links-actions .iyp-links-add").addEventListener("click", () => {
				const blank = { idx: rows().length + 1, __islocal: true };
				opts.inputs.forEach((inp) => (blank[inp.key] = ""));
				rows().push(blank);
				editor.render();
				dirty();
				const last = list.querySelector(".iyp-faq-row:last-child input, .iyp-faq-row:last-child textarea");
				if (last) last.focus();
			});
			editor.render();
		};

		editor.open = (paid) => {
			editor.paid = paid;
			paid ? draw_open() : draw_locked();
		};
		draw_locked();
		paid_editors.push(editor);
		return editor;
	};
	make_paid_editor({
		fieldname: "testimonials",
		label: __("Testimonials"),
		locked_title: __("Show what your customers say about you"),
		help: __("Real words from your customers, with their name. Shown on your page and read by Google and AI search."),
		add_text: __("Add testimonial"),
		empty_text: __("No testimonials yet. Click “Add testimonial” to add one."),
		required: ["customer_name", "testimonial"],
		inputs: [
			{ key: "customer_name", placeholder: __("Customer name, e.g. Rahul Sharma") },
			{ key: "customer_company", placeholder: __("Designation / company, e.g. Purchase Head, Tata Motors") },
			{ key: "testimonial", type: "textarea", placeholder: __("What they said about your work") },
		],
	});
	make_paid_editor({
		fieldname: "certificates",
		label: __("Certificates"),
		locked_title: __("Show your certificates and awards"),
		help: __("ISO, licences, awards. Upload a photo or PDF; visitors can open it on your page."),
		add_text: __("Add certificate"),
		empty_text: __("No certificates yet. Click “Add certificate” to add one."),
		required: ["certificate_name"],
		inputs: [
			{ key: "certificate_name", placeholder: __("Certificate name, e.g. ISO 9001:2015") },
			{ key: "issued_by", placeholder: __("Issued by, e.g. TÜV SÜD") },
			{ key: "year", placeholder: __("Year, e.g. 2024") },
			{ key: "certificate_file", type: "file", placeholder: __("Upload photo or PDF") },
		],
	});
	if (paid_editors.length && web_form.doc && web_form.doc.name && !web_form.is_new) {
		frappe
			.call({ method: "its_your_profile.api.get_plan", args: { name: web_form.doc.name }, quiet: true })
			.then(({ message }) => {
				const open = !!(message && (message.paid || message.staff));
				paid_editors.forEach((ed) => ed.open(open));
			})
			.catch(() => {});
	}

	// Add links to the Profile Links table, skipping platforms (and URLs) it already has
	const add_links = (links) => {
		const field = web_form.fields_dict.profile_links;
		if (!field || !links.length) return 0;
		const rows = link_rows();
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
		render_links();
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
	on_field("website_url", (field, url) => read_links(url));

	// CHANGE NOTE 2026-11-17: no LinkedIn link yet when Save is clicked? First look for it on the
	// company's own website (homepage + contact page), add what is found, then save as usual. Only if
	// the website has none (or can't be opened) does the "LinkedIn is required" message below appear.
	let linkedin_looked_up = false;
	const save_form = web_form.save.bind(web_form);
	web_form.save = () => {
		const has_linkedin = link_rows().some((r) => r.platform === "LinkedIn" && (r.url || "").trim());
		const site = (web_form.get_value("website_url") || "").trim();
		if (has_linkedin || !site || linkedin_looked_up) return save_form();
		linkedin_looked_up = true;
		frappe
			.call({
				method: "its_your_profile.api.read_website_links",
				args: { url: site, quiet: 1 },
				freeze: true,
				freeze_message: __("Looking for your LinkedIn page on your website..."),
			})
			.then(({ message }) => {
				const added = add_links((message && message.links) || []);
				if (added) {
					frappe.show_alert({ message: __("Added {0} links from your website.", [added]), indicator: "green" });
				}
			})
			.catch(() => {})
			.finally(() => save_form());
		return false;
	};

	// CHANGE NOTE 2026-11-07: LinkedIn is compulsory. Save is blocked until the Profile Links table
	// has a LinkedIn row with a link (usually filled in automatically from the card, the website or
	// a web search).
	web_form.validate = () => {
		// 2026-11-17: empty link lines (no link typed) are dropped instead of failing with
		// "Row #2: Value missing for Link"
		const rows = link_rows();
		for (let i = rows.length - 1; i >= 0; i--) {
			if (!(rows[i].url || "").trim()) rows.splice(i, 1);
		}
		render_links();

		// FAQs: drop empty ones; a question without an answer (or the other way round) is pointed out
		const faqs = faq_rows();
		for (let i = faqs.length - 1; i >= 0; i--) {
			faqs[i].question = (faqs[i].question || "").trim();
			faqs[i].answer = (faqs[i].answer || "").trim();
			if (!faqs[i].question && !faqs[i].answer) faqs.splice(i, 1);
		}
		render_faqs();
		const half = faqs.find((r) => !r.question || !r.answer);
		if (half) {
			frappe.msgprint({
				title: __("Finish the question"),
				indicator: "orange",
				message: half.question
					? __("Please type the answer for “{0}”, or remove it with ✕.", [frappe.utils.escape_html(half.question)])
					: __("Please type the question for the answer “{0}”, or remove it with ✕.", [frappe.utils.escape_html(half.answer)]),
			});
			return false;
		}

		// 2026-11-26: Testimonials / Certificates: drop empty rows, point out half-filled ones
		for (const ed of paid_editors) {
			if (!ed.paid) continue;
			const list = ed.rows();
			for (let i = list.length - 1; i >= 0; i--) {
				ed.opts.inputs.forEach((inp) => (list[i][inp.key] = (list[i][inp.key] || "").trim()));
				if (ed.opts.inputs.every((inp) => !list[i][inp.key])) list.splice(i, 1);
			}
			ed.render();
			const half = list.find((r) => ed.opts.required.some((key) => !r[key]));
			if (half) {
				frappe.msgprint({
					title: __("Finish the {0}", [ed.opts.label]),
					indicator: "orange",
					message: __("Please fill in: {0}. Or remove it with ✕.", [
						ed.opts.inputs.filter((inp) => ed.opts.required.includes(inp.key) && !half[inp.key]).map((inp) => inp.placeholder.split(",")[0]).join(", "),
					]),
				});
				return false;
			}
		}

		const no_platform = rows.find((r) => !r.platform);
		if (no_platform) {
			frappe.msgprint({
				title: __("Choose a platform"),
				indicator: "orange",
				message: __("Please choose the platform (LinkedIn, Facebook, ...) for {0}", [frappe.utils.escape_html(no_platform.url)]),
			});
			return false;
		}
		const other = rows.find((r) => r.platform === "Other" && !(r.label || "").trim());
		if (other) {
			frappe.msgprint({
				title: __("Name the link"),
				indicator: "orange",
				message: __("Please type a name for the “Other” link {0} (for example: Instagram, YouTube).", [frappe.utils.escape_html(other.url)]),
			});
			return false;
		}

		const linkedin = rows.find((r) => r.platform === "LinkedIn" && (r.url || "").trim());
		if (linkedin) return true;
		frappe.msgprint({
			title: __("LinkedIn is required"),
			indicator: "orange",
			message: __(
				"We could not find a LinkedIn page on your website. Please add it under <b>Links</b>: click <b>Add link</b>, choose <b>LinkedIn</b> and paste the link (for example https://www.linkedin.com/company/your-company)."
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

		// 2026-11-26: ask first and only say "Reading..." while a scan really runs; a stuck old
		// status comes back as "Stale" (api.get_scan_status) and is dropped without a message.
		// Never poll for more than 3 minutes.
		const check = () =>
			frappe
				.call({ method: "its_your_profile.api.get_scan_status", args: { name: doc.name }, quiet: true })
				.then(({ message: status }) => status);
		check().then((status) => {
			if (!["Pending", "Processing"].includes(status)) return;
			frappe.show_alert({ message: __("Reading your visiting card..."), indicator: "blue" });
			let tries = 0;
			const timer = setInterval(() => {
				if (++tries > (3 * 60 * 1000) / POLL_MS) return clearInterval(timer);
				check().then((now) => {
					if (now === "Completed") {
						clearInterval(timer);
						window.location.reload();
					} else if (now === "Failed") {
						clearInterval(timer);
						frappe.msgprint(__("We couldn't read the card. Please fill in the details manually."));
					} else if (now === "Stale") {
						clearInterval(timer);
					}
				});
			}, POLL_MS);
		});
	};

	// 2026-11-23: show the logo we already have (uploaded, from the card or the website) as a
	// picture, not only as a file name, and update it when a new one is uploaded or removed
	const show_logo = () => {
		const field = web_form.fields_dict.company_logo;
		if (!field) return;
		const wrap = field.$wrapper.get(0);
		const url = web_form.get_value("company_logo") || (web_form.doc && web_form.doc.company_logo) || "";
		let box = wrap.querySelector(".iyp-logo-preview");
		if (!/^(\/files\/|\/private\/files\/|https?:\/\/)/.test(url)) {
			if (box) box.remove();
			return;
		}
		if (!box) {
			box = document.createElement("div");
			box.className = "iyp-logo-preview";
			box.innerHTML = `<img alt=""><span>${__("Your current logo")}</span>`;
			box.querySelector("img").addEventListener("error", () => box.remove());
			(wrap.querySelector(".control-input-wrapper") || wrap).prepend(box);
		}
		const img = box.querySelector("img");
		if (img.getAttribute("src") !== url) img.setAttribute("src", url);
	};
	on_field("company_logo", () => setTimeout(show_logo, 50));

	// The form may finish loading before this script runs, so check now as well as on after_load
	web_form.after_load = () => {
		watch_scan();
		show_logo();
	};
	watch_scan();
	show_logo();
	setTimeout(show_logo, 800);
});
