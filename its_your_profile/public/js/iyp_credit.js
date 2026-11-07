// CHANGE NOTE 2026-11-06: "Developed by SoftWorld Solutions Pvt. Ltd." badge, fixed in the
// bottom-left corner of every website page so it stays in view while scrolling. Loaded on all
// pages through hooks.py web_include_js. Moves up on phones where a page has its own bottom bar.
(function () {
	if (window.__iypCredit) return;
	window.__iypCredit = true;

	var css =
		".iyp-credit-badge{position:fixed;left:16px;bottom:16px;z-index:1030;display:inline-flex;align-items:center;gap:6px;" +
		"padding:7px 14px;border-radius:999px;background:rgba(255,255,255,.92);border:1px solid #E4DFF3;margin-bottom:env(safe-area-inset-bottom,0px);" +
		"-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);box-shadow:0 10px 24px -12px rgba(59,46,126,.45);" +
		"font:500 12.5px/1.2 Sora,system-ui,-apple-system,sans-serif;color:#5A5578 !important;text-decoration:none !important;" +
		"transition:transform .2s ease,box-shadow .2s ease,bottom .25s ease;animation:iyp-credit-in .6s .6s cubic-bezier(.2,.8,.2,1) backwards}" +
		".iyp-credit-badge b{color:#3B2E7E;font-weight:700}" +
		".iyp-credit-badge:hover{transform:translateY(-2px);box-shadow:0 14px 28px -12px rgba(59,46,126,.6)}" +
		".iyp-credit-badge:hover b{color:#B55406}" +
		".iyp-credit-badge i{width:7px;height:7px;border-radius:50%;background:linear-gradient(135deg,#3B2E7E,#E87012);flex:none}" +
		"@keyframes iyp-credit-in{from{opacity:0;transform:translateY(12px)}}" +
		"[data-iyp-theme=dark] .iyp-credit-badge{background:rgba(27,23,54,.92);border-color:#332C5A;color:#A9A4C8 !important}" +
		"[data-iyp-theme=dark] .iyp-credit-badge b{color:#D3CBFF}" +
		"@media (max-width:767px){.iyp-credit-badge{left:0;right:0;width:max-content;margin:0 auto;bottom:10px;font-size:11.5px;padding:6px 12px;white-space:nowrap}" +
		".iyp-credit-raised .iyp-credit-badge{bottom:calc(96px + env(safe-area-inset-bottom,0px));margin-bottom:0}" +
		/* Business pages on phones: the credit sits inside the bottom dock instead (2026-11-07) */
		".iyp-credit-in-bar .iyp-credit-badge{display:none}}" +
		"@media (prefers-reduced-motion:reduce){.iyp-credit-badge{animation:none;transition:none}}";

	function add() {
		if (document.querySelector(".iyp-credit-badge")) return;
		var style = document.createElement("style");
		style.textContent = css;
		document.head.appendChild(style);

		var a = document.createElement("a");
		a.className = "iyp-credit-badge";
		a.href = "https://softworld.co.in";
		a.target = "_blank";
		a.rel = "noopener";
		a.innerHTML = "<i aria-hidden=\"true\"></i>Developed by <b>SoftWorld Solutions Pvt. Ltd.</b>";
		document.body.appendChild(a);

		// Login page: our logo in place of Frappe's (iyp_site.css does it too; this covers browsers
		// that ignore CSS image replacement)
		document.querySelectorAll("img.app-logo").forEach(function (img) {
			img.src = "/assets/its_your_profile/images/iyp-logo.png";
			img.alt = "It's Your Profile";
		});

		// Business pages (quick-action bar) and the profile form (sticky save bar) keep a bar at the
		// bottom on phones; lift the badge above it there
		if (document.querySelector(".iyp-bar, .web-form-footer")) {
			document.documentElement.classList.add("iyp-credit-raised");
		}
		// Business page quick-action bar (2026-11-07): put the credit inside it as a small line, so
		// on phones it never overlaps the Call/WhatsApp buttons (the dashboard's dock is left alone)
		var bar = document.querySelector(".iyp-bar:not(.iyp-dock)");
		if (bar && !bar.querySelector(".iyp-bar-credit")) {
			var line = document.createElement("a");
			line.className = "iyp-bar-credit";
			line.href = "https://softworld.co.in";
			line.target = "_blank";
			line.rel = "noopener";
			line.innerHTML = "Developed by <b>SoftWorld Solutions Pvt. Ltd.</b>";
			bar.appendChild(line);
			document.documentElement.classList.add("iyp-credit-in-bar");
		}

		fixSignupButton();
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
