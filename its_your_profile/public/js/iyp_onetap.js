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
	// 2026-11-25: a "Sign in with Google" bar at the top of every page (user's request), also for
	// visitors Google's pop-up can't reach (not signed in to Google in this browser, incognito, pop-up
	// paused by Google). Shown on every page open; × hides it for this page view only.
	(function addTopBar() {
		var main = document.querySelector("main");
		if (!main || !main.parentNode || document.querySelector("[data-iyp-topsign]")) return;
		var css = document.createElement("style");
		css.textContent =
			".iyp-topsign{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:10px 16px;position:relative;" +
			"box-sizing:border-box;width:calc(100% - 32px);max-width:760px;margin:12px auto;padding:12px 44px 12px 16px;" +
			"border:1px solid #E4DEF7;border-radius:16px;background:#F7F4FF;color:#2A2247;font-size:.92rem;" +
			"box-shadow:0 4px 16px rgba(60,40,120,.08)}" +
			".iyp-topsign[hidden]{display:none}" +
			".iyp-topsign-text{margin:0;text-align:center}" +
			".iyp-topsign-btn{display:flex;justify-content:center;min-height:44px}" +
			".iyp-topsign-done{display:none;margin:0;font-weight:600;color:#0E7A45}" +
			".iyp-topsign.is-known .iyp-topsign-text,.iyp-topsign.is-known .iyp-topsign-btn{display:none}" +
			".iyp-topsign.is-known .iyp-topsign-done{display:block}" +
			".iyp-topsign-x{position:absolute;top:6px;right:8px;border:0;background:none;font-size:1.4rem;line-height:1;" +
			"color:#6B6485;cursor:pointer;padding:4px 6px}" +
			"[data-iyp-theme=dark] .iyp-topsign{background:#221D36;border-color:#3A3256;color:#ECE8FA}" +
			"[data-iyp-theme=dark] .iyp-topsign-done{color:#5FD39A}";
		document.head.appendChild(css);
		var bar = document.createElement("div");
		bar.className = "iyp-topsign";
		bar.hidden = true; // shown once Google's button is drawn
		bar.setAttribute("data-iyp-topsign", "");
		bar.setAttribute("data-iyp-gsi-wrap", "");
		bar.innerHTML =
			'<p class="iyp-topsign-text"><strong>👋 Welcome!</strong> Sign in with Google to continue</p>' +
			'<div class="iyp-topsign-btn" data-iyp-gsi-button data-iyp-gsi-text="signin_with"></div>' +
			'<p class="iyp-topsign-done" data-iyp-gsi-done data-text="✓ Signed in as {0}"></p>' +
			'<button type="button" class="iyp-topsign-x" aria-label="Close">×</button>';
		bar.querySelector(".iyp-topsign-x").addEventListener("click", function () { bar.remove(); });
		main.parentNode.insertBefore(bar, main);
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
		// The top bar shows "✓ Signed in as …" for a moment, then goes away
		var topBar = document.querySelector("[data-iyp-topsign]");
		if (person.fresh !== false && topBar) setTimeout(function () { topBar.remove(); }, 4000);
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
		// 2026-11-24: "Sign in as …" is asked every time any page of the website is opened,
		// also for people known on this device already (user's request)
		google.accounts.id.prompt();
	}

	function load() {
		var script = document.createElement("script");
		script.src = "https://accounts.google.com/gsi/client";
		script.async = true;
		script.onload = start;
		document.head.appendChild(script);
	}

	// Remembered from an earlier visit: fills forms only (fresh: false), it does not open the
	// business page's View more box; the visitor is asked again (2026-11-24)
	if (known) announce(Object.assign({}, known, { fresh: false }));
	// 2026-11-25: Google sign-in is offered right at the start of every page (user's request)
	setTimeout(load, 0);
})();
