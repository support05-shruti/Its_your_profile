/* Google One Tap on every page of It's Your Profile (2026-11-16).
 *
 * A website can't read the Google account a visitor is signed into. Google One Tap shows a small
 * Google box, "Continue as Shruti"; only if the visitor taps it does Google hand us a signed token
 * with their name and email. its_your_profile.one_tap.identify checks it with Google and saves the
 * person as a Site Visitor (staff see them on the dashboard). On a business page the business's
 * owner sees them too.
 *
 * Runs only when the page has <meta name="iyp-gsi-client"> (portal.one_tap_meta): One Tap switched
 * on in Settings, visitor not logged in, not the login page. Closing the box hides it for this tab.
 * Pages can listen for the "iyp:known" event (detail = {name, first_name, email}); the business
 * page fills its contact form with it.
 */
(function () {
	var meta = document.querySelector('meta[name="iyp-gsi-client"]');
	var clientId = meta && meta.getAttribute("content");
	if (!clientId) return;
	// A logged-in user (cached guest page) never gets the box
	if (/(^|;\s*)user_id=(?!Guest)/.test(document.cookie)) return;

	var KNOWN = "iyp_onetap_known";
	function store(key, value) {
		try {
			if (value === undefined) return sessionStorage.getItem(key);
			sessionStorage.setItem(key, value);
		} catch (e) { /* storage blocked */ }
		return null;
	}
	// 2026-11-23: the pop-up is asked on EVERY page visit until the visitor shares their name (Google
	// or the "View more" form). Closing it no longer hides it for the rest of the tab. Google itself
	// may still wait a while after someone closes it several times; that we can't change.
	// 2026-11-25: a pop-up at the start of every page (user's request): "Sign in with Google" for
	// 10 seconds; closing it (×) asks for the visitor's name and email instead. Also reaches visitors
	// Google's own pop-up can't (not signed in to Google in this browser, incognito, paused by Google).
	// Shown on every page open, also for returning visitors.
	var pop = (function () {
		if (!document.body) return null;
		var SHOW_SECONDS = 10;
		var css = document.createElement("style");
		css.textContent =
			".iyp-pop{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:flex-start;justify-content:center;" +
			"padding:72px 16px 16px;background:rgba(24,18,48,.35);box-sizing:border-box}" +
			".iyp-pop[hidden]{display:none}" +
			".iyp-pop-card{position:relative;box-sizing:border-box;width:100%;max-width:400px;padding:22px 20px 18px;border-radius:20px;" +
			"background:#fff;color:#2A2247;text-align:center;box-shadow:0 18px 50px rgba(30,20,80,.25);overflow:hidden;" +
			"font-family:inherit;animation:iypPopIn .25s ease}" +
			"@keyframes iypPopIn{from{opacity:0;transform:translateY(-12px)}to{opacity:1;transform:none}}" +
			".iyp-pop-card h3{margin:0 0 6px;font-size:1.15rem;font-weight:700;color:inherit}" +
			".iyp-pop-card p{margin:0 0 14px;font-size:.9rem;color:#5B5478}" +
			".iyp-pop-step[hidden]{display:none}" +
			".iyp-pop-btn{display:flex;justify-content:center;min-height:44px}" +
			".iyp-pop-x[hidden]{display:none}.iyp-pop-x{position:absolute;top:8px;right:10px;border:0;background:none;font-size:1.5rem;line-height:1;color:#6B6485;cursor:pointer;padding:4px 8px}" +
			".iyp-pop-time{position:absolute;left:0;bottom:0;height:4px;width:100%;background:#6C4BD8;transform-origin:left}" +
			".iyp-pop-form{display:grid;gap:10px;text-align:left}" +
			".iyp-pop-form label{font-size:.82rem;font-weight:600;color:#3A3256}" +
			".iyp-pop-form input{box-sizing:border-box;width:100%;margin-top:4px;padding:11px 12px;border:1px solid #D9D3EE;border-radius:12px;font-size:16px;background:#fff;color:#2A2247}" +
			".iyp-pop-form button{margin-top:4px;padding:12px;border:0;border-radius:999px;background:#3B2A86;color:#fff;font-size:.95rem;font-weight:700;cursor:pointer}" +
			".iyp-pop-form button[disabled]{opacity:.6;cursor:wait}" +
			".iyp-pop-card .iyp-pop-err{margin:0;color:#B42318;font-size:.84rem;font-weight:600}.iyp-pop-card .iyp-pop-err[hidden]{display:none}" +
			".iyp-pop-trap{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}" +
			".iyp-pop-done{margin:6px 0;font-weight:700;color:#0E7A45}" +
			"[data-iyp-theme=dark] .iyp-pop-card{background:#221D36;color:#ECE8FA}" +
			"[data-iyp-theme=dark] .iyp-pop-card p,[data-iyp-theme=dark] .iyp-pop-form label{color:#BDB5DA}" +
			"[data-iyp-theme=dark] .iyp-pop-form input{background:#1A162B;border-color:#3A3256;color:#ECE8FA}" +
			"[data-iyp-theme=dark] .iyp-pop-done{color:#5FD39A}";
		document.head.appendChild(css);

		var box = document.createElement("div");
		box.className = "iyp-pop";
		box.hidden = true;
		box.setAttribute("role", "dialog");
		box.setAttribute("aria-modal", "true");
		box.setAttribute("aria-label", "Sign in");
		box.innerHTML =
			'<div class="iyp-pop-card">' +
				'<button type="button" class="iyp-pop-x" aria-label="Close">×</button>' +
				'<div class="iyp-pop-step" data-step="google">' +
					'<h3>👋 Welcome to It’s Your Profile</h3>' +
					'<p>Sign in with Google to continue</p>' +
					'<div class="iyp-pop-btn" data-iyp-pop-gsi></div>' +
					'<div class="iyp-pop-time"></div>' +
				'</div>' +
				'<div class="iyp-pop-step" data-step="form" hidden>' +
					'<h3>Tell us who you are</h3>' +
					'<p>Please give your name and email ID</p>' +
					'<form class="iyp-pop-form" novalidate>' +
						'<label>Name *<input name="name" autocomplete="name" maxlength="80" required></label>' +
						'<label>Email ID *<input name="email" type="email" autocomplete="email" maxlength="120" required></label>' +
						'<input class="iyp-pop-trap" name="company_website" tabindex="-1" autocomplete="off" aria-hidden="true">' +
						'<p class="iyp-pop-err" hidden></p>' +
						'<button type="submit">Continue</button>' +
					'</form>' +
				'</div>' +
				'<div class="iyp-pop-step" data-step="done" hidden><p class="iyp-pop-done"></p></div>' +
			'</div>';
		document.body.appendChild(box);

		var steps = box.querySelectorAll(".iyp-pop-step");
		var form = box.querySelector("form");
		var err = box.querySelector(".iyp-pop-err");
		var line = box.querySelector(".iyp-pop-time");
		var xButton = box.querySelector(".iyp-pop-x");
		var timer = null, step = "";
		var root = document.documentElement, oldOverflow = root.style.overflow;
		// 2026-11-25: the details form is compulsory on business pages only (no × there); on the home
		// page, directory etc. it can be closed, so new businesses can still read and sign up
		var compulsory = !!document.querySelector("[data-iyp-profile]");
		function show(name) {
			step = name;
			for (var i = 0; i < steps.length; i++) steps[i].hidden = steps[i].getAttribute("data-step") !== name;
			xButton.hidden = name === "done" || (name === "form" && compulsory);
			box.hidden = false;
			root.style.overflow = "hidden"; // the page behind can't be scrolled or read
		}
		function close() { clearTimeout(timer); box.hidden = true; step = ""; root.style.overflow = oldOverflow; }
		function openForm() {
			clearTimeout(timer);
			show("form");
			setTimeout(function () {
				var first = form.elements.name.value ? form.elements.email : form.elements.name;
				try { first.focus(); } catch (e) { /* ignore */ }
			}, 50);
		}
		function open() {
			if (step) return;
			show("google");
			// The 10-second line shrinks; after 10 seconds without Google, the details form is asked
			// (compulsory, so waiting doesn't get anyone past it)
			line.style.transition = "none";
			line.style.transform = "scaleX(1)";
			void line.offsetWidth;
			line.style.transition = "transform " + SHOW_SECONDS + "s linear";
			line.style.transform = "scaleX(0)";
			timer = setTimeout(function () { if (step === "google") openForm(); }, SHOW_SECONDS * 1000);
		}
		// × on the Google step asks for the details; × on the details step (not on business pages) closes
		xButton.addEventListener("click", function () {
			if (step === "google") openForm();
			else if (!compulsory) close();
		});
		form.addEventListener("submit", function (ev) {
			ev.preventDefault();
			err.hidden = true;
			var name = form.elements.name.value.trim(), email = form.elements.email.value.trim();
			function fail(text, field) { err.textContent = text; err.hidden = false; if (field) field.focus(); }
			if (name.length < 2) return fail("Please enter your name.", form.elements.name);
			if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return fail("Please enter a valid email ID.", form.elements.email);
			var button = form.querySelector("button");
			button.disabled = true;
			var headers = { "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json" };
			if (window.frappe && frappe.csrf_token) headers["X-Frappe-CSRF-Token"] = frappe.csrf_token;
			fetch("/api/method/its_your_profile.one_tap.share_details", {
				method: "POST", credentials: "same-origin", headers: headers,
				body: new URLSearchParams({
					name: name, email: email, profile: profileId(), path: location.pathname,
					referrer: (firstVisit && firstVisit.referrer) || "", utm: (firstVisit && firstVisit.utm) || "",
					company_website: form.elements.company_website.value
				})
			}).then(function (r) {
				return r.json().catch(function () { return {}; }).then(function (data) { return { ok: r.ok, status: r.status, data: data }; });
			}).then(function (res) {
				button.disabled = false;
				if (!res.ok) {
					var text = "Could not save your details. Please try again.";
					if (res.status === 429) text = "Too many tries. Please wait a while and try again.";
					else {
						try {
							var m = JSON.parse(JSON.parse(res.data._server_messages || "[]")[0] || "{}").message;
							if (m) { var d = document.createElement("div"); d.innerHTML = m; text = d.textContent || text; }
						} catch (e) { /* keep the default text */ }
					}
					return fail(text);
				}
				var person = (res.data && res.data.message) || { name: name, first_name: name.split(" ")[0], email: email };
				keep(JSON.stringify(person));
				announce(person);
			}).catch(function () {
				button.disabled = false;
				fail("Could not save your details. Please check your internet and try again.");
			});
		});
		return {
			open: open,
			openForm: openForm,
			gsiBox: box.querySelector("[data-iyp-pop-gsi]"),
			prefill: function (person) {
				if (person.name && !form.elements.name.value) form.elements.name.value = person.name;
				if (person.email && !form.elements.email.value) form.elements.email.value = person.email;
			},
			done: function (person) {
				clearTimeout(timer);
				box.querySelector(".iyp-pop-done").textContent = "✓ Thank you, " + (person.first_name || person.name || person.email || "") + "!";
				show("done");
				setTimeout(close, 2000);
			}
		};
	})();
	var buttons = document.querySelectorAll("[data-iyp-gsi-button]");

	// Where the visitor first came from in this tab (Google, WhatsApp, ChatGPT...)
	var firstVisit = null;
	try { firstVisit = JSON.parse(store("iyp_onetap_from") || "null"); } catch (e) { firstVisit = null; }
	if (!firstVisit) {
		firstVisit = { referrer: document.referrer || "", utm: new URLSearchParams(location.search).get("utm_source") || "" };
		store("iyp_onetap_from", JSON.stringify(firstVisit));
	}

	function announce(person) {
		// The "Continue with Google" buttons become "Shared as …", only for a new answer: someone
		// remembered from an earlier visit still gets the button, as they are asked again (2026-11-24)
		if (person.fresh !== false) buttons.forEach(function (box) {
			var wrap = box.closest("[data-iyp-gsi-wrap]") || box;
			wrap.classList.add("is-known");
			wrap.hidden = false;
			var done = wrap.querySelector("[data-iyp-gsi-done]");
			if (done) done.textContent = (done.getAttribute("data-text") || "").replace("{0}", person.name || person.email || "");
		});
		// The start pop-up: a new answer says thank you and closes; someone remembered from an earlier
		// visit only gets their name and email filled in (they are still asked)
		if (pop) { if (person.fresh !== false) pop.done(person); else pop.prefill(person); }
		var event;
		try { event = new CustomEvent("iyp:known", { detail: person }); } catch (e) { return; }
		document.dispatchEvent(event);
	}

	// Already shared their name earlier on this device (2026-11-19: kept in localStorage, not only this
	// tab; the server remembers them too, see one_tap.remember_visitor): fill forms, no box again
	function keep(value) {
		try {
			if (value === undefined) return localStorage.getItem(KNOWN) || sessionStorage.getItem(KNOWN);
			localStorage.setItem(KNOWN, value);
		} catch (e) { store(KNOWN, value); }
		return null;
	}
	var known = null;
	try { known = JSON.parse(keep() || "null"); } catch (e) { known = null; }

	function profileId() {
		var page = document.querySelector("[data-iyp-profile]");
		return page ? page.getAttribute("data-iyp-profile") : "";
	}

	function send(credential) {
		return fetch("/api/method/its_your_profile.one_tap.identify", {
			method: "POST", credentials: "same-origin",
			headers: { "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json" },
			body: new URLSearchParams({
				credential: credential, path: location.pathname, profile: profileId(),
				referrer: firstVisit.referrer, utm: firstVisit.utm
			})
		}).then(function (r) { return r.ok ? r.json() : null; }).then(function (data) {
			var person = data && data.message;
			if (!person) return;
			keep(JSON.stringify(person));
			announce(person);
		}).catch(function () {});
	}

	function start() {
		if (!window.google || !google.accounts || !google.accounts.id) return;
		google.accounts.id.initialize({
			client_id: clientId,
			callback: function (response) { send(response.credential); },
			// 2026-11-24: no silent sign-in; the visitor is asked ("Sign in as …") on every visit
			auto_select: false,
			cancel_on_tap_outside: true,
			context: "use",
			itp_support: true,
			use_fedcm_for_prompt: true
		});
		// 2026-11-16: a visible "Continue with Google" button where the page asks for one, so a
		// visitor who closed the pop-up (or never saw it) can still share their name
		buttons.forEach(function (box) {
			if (box.childElementCount) return;
			try {
				google.accounts.id.renderButton(box, {
					type: "standard", theme: document.documentElement.getAttribute("data-iyp-theme") === "dark" ? "filled_black" : "outline",
					// 2026-11-23: a box can ask for its own words, e.g. "signup_with" on the View more gate
					size: "large", text: box.getAttribute("data-iyp-gsi-text") || "continue_with", shape: "pill", logo_alignment: "left",
					width: Math.min(360, Math.max(220, box.clientWidth || 300))
				});
				var wrap = box.closest("[data-iyp-gsi-wrap]");
				if (wrap) wrap.hidden = false;
			} catch (e) { /* button could not be drawn */ }
		});
		// 2026-11-25: the start pop-up replaces Google's own corner pop-up (two at once was confusing).
		// Its Google button shows "Sign in as <name>" when the visitor is signed in to Google.
		if (pop) {
			try {
				google.accounts.id.renderButton(pop.gsiBox, {
					type: "standard", theme: document.documentElement.getAttribute("data-iyp-theme") === "dark" ? "filled_black" : "outline",
					size: "large", text: "signin_with", shape: "pill", logo_alignment: "left", width: 300
				});
				pop.open();
			} catch (e) { pop.openForm(); }
		}
	}

	function load() {
		var script = document.createElement("script");
		script.src = "https://accounts.google.com/gsi/client";
		script.async = true;
		script.onload = function () {
			if (window.google && google.accounts && google.accounts.id) start();
			else if (pop) pop.openForm();
		};
		// Google could not be reached (blocked, offline): ask for the details straight away
		script.onerror = function () { if (pop) pop.openForm(); };
		document.head.appendChild(script);
	}

	// Remembered from an earlier visit: fills forms only (fresh: false), it does not open the
	// business page's View more box; the visitor is asked again (2026-11-24)
	if (known) announce(Object.assign({}, known, { fresh: false }));
	// 2026-11-25: Google sign-in is offered right at the start of every page (user's request)
	setTimeout(load, 0);
})();
