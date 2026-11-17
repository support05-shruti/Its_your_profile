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

	var CLOSED = "iyp_onetap_closed", KNOWN = "iyp_onetap_known";
	function store(key, value) {
		try {
			if (value === undefined) return sessionStorage.getItem(key);
			sessionStorage.setItem(key, value);
		} catch (e) { /* storage blocked */ }
		return null;
	}
	// Closed the pop-up earlier in this tab: no pop-up again, but the page's own button still works
	var popupClosed = !!store(CLOSED);
	var buttons = document.querySelectorAll("[data-iyp-gsi-button]");
	if (popupClosed && !buttons.length) return;

	// Where the visitor first came from in this tab (Google, WhatsApp, ChatGPT...)
	var firstVisit = null;
	try { firstVisit = JSON.parse(store("iyp_onetap_from") || "null"); } catch (e) { firstVisit = null; }
	if (!firstVisit) {
		firstVisit = { referrer: document.referrer || "", utm: new URLSearchParams(location.search).get("utm_source") || "" };
		store("iyp_onetap_from", JSON.stringify(firstVisit));
	}

	function announce(person) {
		// The "Continue with Google" buttons become "Shared as …"
		buttons.forEach(function (box) {
			var wrap = box.closest("[data-iyp-gsi-wrap]") || box;
			wrap.classList.add("is-known");
			wrap.hidden = false;
			var done = wrap.querySelector("[data-iyp-gsi-done]");
			if (done) done.textContent = (done.getAttribute("data-text") || "").replace("{0}", person.name || person.email || "");
		});
		var event;
		try { event = new CustomEvent("iyp:known", { detail: person }); } catch (e) { return; }
		document.dispatchEvent(event);
	}

	// Already shared their name earlier in this tab: fill forms, no box again
	var known = null;
	try { known = JSON.parse(store(KNOWN) || "null"); } catch (e) { known = null; }

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
			store(KNOWN, JSON.stringify(person));
			announce(person);
		}).catch(function () {});
	}

	function start() {
		if (!window.google || !google.accounts || !google.accounts.id) return;
		google.accounts.id.initialize({
			client_id: clientId,
			callback: function (response) { send(response.credential); },
			auto_select: true,          // people who said yes before are recognised on each page without a tap
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
					size: "large", text: "continue_with", shape: "pill", logo_alignment: "left",
					width: Math.min(360, Math.max(220, box.clientWidth || 300))
				});
				var wrap = box.closest("[data-iyp-gsi-wrap]");
				if (wrap) wrap.hidden = false;
			} catch (e) { /* button could not be drawn */ }
		});
		if (popupClosed) return;
		google.accounts.id.prompt(function (n) {
			if (n && n.isSkippedMoment && n.isSkippedMoment()) store(CLOSED, "1");
		});
	}

	function load() {
		var script = document.createElement("script");
		script.src = "https://accounts.google.com/gsi/client";
		script.async = true;
		script.onload = start;
		document.head.appendChild(script);
	}

	if (known) announce(known);
	// Let the visitor see the page first
	setTimeout(load, known ? 0 : 2500);
})();
