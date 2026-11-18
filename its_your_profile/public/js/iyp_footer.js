// CHANGE NOTE 2026-11-07: small fixes for Frappe's standard pages, loaded on every website page
// through hooks.py web_include_js: our logo on the login page, and the sign-up button on Android.
// The "Developed by SoftWorld Solutions Pvt. Ltd." credit is no longer added here: it appears only
// once, in the home page footer (www/home.html). (Earlier this file was iyp_credit.js and drew a
// floating credit badge on every page.)
(function () {
	if (window.__iypCredit) return;
	window.__iypCredit = true;

	function add() {
		fixLogo();
		fixSignupButton();
		guardSignup();
		addThemeSwitch();
		countPageView();
	}

	// 2026-11-18: robots were signing up with made-up names and other people's emails, sending them
	// "Welcome" emails. The server (signup_guard.py) only accepts a sign-up that carries "iyp_human",
	// which is added here once a person has typed or tapped on the page.
	function guardSignup() {
		if (!document.querySelector(".form-signup")) return;
		var human = false;
		["keydown", "pointerdown", "touchstart"].forEach(function (type) {
			document.addEventListener(type, function () { human = true; }, { passive: true, capture: true });
		});
		var tries = 0;
		(function wrap() {
			var login = window.login;
			if (!login || typeof login.call !== "function") {
				if (++tries < 50) setTimeout(wrap, 100);
				return;
			}
			if (login.call.__iyp) return;
			var call = login.call;
			login.call = function (args) {
				if (args && args.cmd === "frappe.core.doctype.user.user.sign_up" && human) args.iyp_human = "iyp-1";
				return call.apply(this, arguments);
			};
			login.call.__iyp = true;
		})();
	}

	// 2026-11-16: count views of the site's own pages (home, terms, directory...) for the staff
	// dashboard, with where the visitor first came from in this tab. Business pages count themselves.
	function countPageView() {
		var path = location.pathname;
		if (/^\/(business\/|app\b|login|update-password|api\/)/.test(path)) return;
		var from = null;
		try { from = JSON.parse(sessionStorage.getItem("iyp_site_from") || "null"); } catch (e) { from = null; }
		if (!from) {
			from = { referrer: document.referrer || "", utm: new URLSearchParams(location.search).get("utm_source") || "" };
			try { sessionStorage.setItem("iyp_site_from", JSON.stringify(from)); } catch (e) { /* storage blocked */ }
		}
		var headers = { "Content-Type": "application/x-www-form-urlencoded" };
		if (window.frappe && frappe.csrf_token) headers["X-Frappe-CSRF-Token"] = frappe.csrf_token;
		fetch("/api/method/its_your_profile.tracking.track_page", {
			method: "POST", headers: headers, keepalive: true, credentials: "same-origin",
			body: new URLSearchParams({ path: path, referrer: from.referrer, utm: from.utm })
		}).catch(function () {});
	}

	// 2026-11-16: light / dark switch on the sign-in / sign-up and set-password pages, which are
	// Frappe's own pages and had no switch (the other pages have their own). Same saved choice
	// ("iyp-theme") as the rest of the site.
	function addThemeSwitch() {
		var path = location.pathname.replace(/\/+$/, "");
		if (path !== "/login" && path !== "/update-password") return;
		if (document.querySelector(".iyp-theme-fab")) return;
		var root = document.documentElement;
		var btn = document.createElement("button");
		btn.type = "button";
		btn.className = "iyp-theme-fab";
		btn.setAttribute("aria-label", "Switch light / dark");
		btn.title = "Switch light / dark";
		btn.innerHTML =
			'<svg class="iyp-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/></svg>' +
			'<svg class="iyp-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
		function sync() {
			btn.setAttribute("aria-pressed", root.getAttribute("data-iyp-theme") === "dark" ? "true" : "false");
		}
		btn.addEventListener("click", function () {
			var next = root.getAttribute("data-iyp-theme") === "dark" ? "light" : "dark";
			root.setAttribute("data-iyp-theme", next);
			try { localStorage.setItem("iyp-theme", next); } catch (e) { /* storage blocked */ }
			sync();
		});
		sync();
		document.body.appendChild(btn);
	}


	function fixLogo() {
		// Login page: our logo in place of Frappe's (iyp_site.css does it too; this covers browsers
		// that ignore CSS image replacement)
		document.querySelectorAll("img.app-logo").forEach(function (img) {
			img.src = "/assets/its_your_profile/images/iyp-logo.png";
			img.alt = "It's Your Profile";
		});
	}

	// CHANGE NOTE 2026-11-07: Frappe enables "Create Account" only on the boxes' "input" event.
	// Android autofill (Chrome, Gboard) fills the name/email without that event, so the button
	// stayed disabled on phones. Check on every kind of change, and a few times a second while
	// the sign-up form is open (autofill can fire no event at all).
	function fixSignupButton() {
		var form = document.querySelector(".form-signup");
		if (!form) return;
		var name = document.getElementById("signup_fullname");
		var email = document.getElementById("signup_email");
		var button = form.querySelector(".btn-signup, button[type=submit]");
		if (!name || !email || !button) return;
		function check() {
			var ready = !!(name.value.trim() && email.value.trim());
			if (button.disabled === ready) button.disabled = !ready;
		}
		["input", "change", "keyup", "blur", "paste", "focus"].forEach(function (type) {
			name.addEventListener(type, function () { setTimeout(check, 0); });
			email.addEventListener(type, function () { setTimeout(check, 0); });
		});
		setInterval(function () {
			if (form.offsetParent !== null) check(); // only while the sign-up form is showing
		}, 400);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", add);
	else add();
})();
