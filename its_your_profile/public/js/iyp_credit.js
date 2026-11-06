// CHANGE NOTE 2026-11-06: "Developed by SoftWorld Solutions Pvt. Ltd." badge, fixed in the
// bottom-left corner of every website page so it stays in view while scrolling. Loaded on all
// pages through hooks.py web_include_js. Moves up on phones where a page has its own bottom bar.
(function () {
	if (window.__iypCredit) return;
	window.__iypCredit = true;

	var css =
		".iyp-credit-badge{position:fixed;left:16px;bottom:16px;z-index:1030;display:inline-flex;align-items:center;gap:6px;" +
		"padding:7px 14px;border-radius:999px;background:rgba(255,255,255,.92);border:1px solid #E4DFF3;" +
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
		".iyp-credit-raised .iyp-credit-badge{bottom:92px}}" +
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

		// Business pages (quick-action bar) and the profile form (sticky save bar) keep a bar at the
		// bottom on phones; lift the badge above it there
		if (document.querySelector(".iyp-bar, .web-form-footer")) {
			document.documentElement.classList.add("iyp-credit-raised");
		}
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", add);
	else add();
})();
