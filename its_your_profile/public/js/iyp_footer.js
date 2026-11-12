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
