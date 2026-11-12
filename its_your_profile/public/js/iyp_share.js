// CHANGE NOTE 2026-11-12: our own "Share" menu, used by the business pages and the dashboard.
// Before, Share opened the phone's share sheet (navigator.share) or, where that is missing (any
// http:// site, many desktop browsers), went straight to WhatsApp without asking. Now it always asks:
// WhatsApp, Facebook, LinkedIn, X, Telegram, Email, SMS, Copy link, and "More apps" (the phone's own
// share sheet) where the browser has one. A bottom sheet on phones, a small dialog on computers.
// Use: window.iypShare(title, url). Loaded on every website page through hooks.py web_include_js.
(function () {
	if (window.iypShare) return;

	var css =
		".iyp-sh-back{position:fixed;inset:0;z-index:2000;background:rgba(20,18,30,.45);display:flex;align-items:flex-end;justify-content:center;opacity:0;transition:opacity .18s ease}" +
		".iyp-sh-back.open{opacity:1}" +
		".iyp-sh{width:100%;max-width:440px;max-height:90vh;overflow:auto;background:#fff;color:#1F1D1A;border-radius:18px 18px 0 0;padding:10px 18px calc(18px + env(safe-area-inset-bottom,0px));" +
		"font:400 15px/1.4 'IBM Plex Sans',Sora,system-ui,-apple-system,'Segoe UI',sans-serif;transform:translateY(24px);transition:transform .2s ease;box-shadow:0 -8px 30px rgba(0,0,0,.15)}" +
		".iyp-sh-back.open .iyp-sh{transform:none}" +
		".iyp-sh-grip{width:40px;height:4px;border-radius:2px;background:#DDD8CE;margin:2px auto 12px}" +
		".iyp-sh-head{display:flex;align-items:flex-start;gap:12px;margin-bottom:14px}" +
		".iyp-sh-head b{display:block;font-size:16px;font-weight:600}" +
		".iyp-sh-head small{display:block;margin-top:2px;font-size:13px;color:#6B665E;overflow-wrap:anywhere}" +
		".iyp-sh-x{margin-left:auto;flex:none;width:36px;height:36px;border:0;border-radius:8px;background:#F3F1EC;color:#3A3733;font-size:20px;line-height:1;cursor:pointer}" +
		".iyp-sh-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px 6px}" +
		".iyp-sh-opt{display:flex;flex-direction:column;align-items:center;gap:6px;padding:4px 0;border:0;background:none;font:inherit;font-size:12.5px;color:#3A3733;text-decoration:none!important;cursor:pointer;-webkit-tap-highlight-color:transparent}" +
		".iyp-sh-opt i{width:48px;height:48px;border-radius:50%;display:grid;place-items:center;color:#fff}" +
		".iyp-sh-opt svg{width:22px;height:22px;fill:currentColor}" +
		".iyp-sh-opt:active i{transform:scale(.94)}" +
		".iyp-sh-link{display:flex;gap:8px;margin-top:18px}" +
		".iyp-sh-link input{flex:1;min-width:0;height:44px;padding:0 12px;border:1px solid #E4DFD5;border-radius:8px;font:inherit;font-size:14px;color:#3A3733;background:#FAF9F6}" +
		".iyp-sh-link button{flex:none;height:44px;padding:0 16px;border:0;border-radius:8px;background:#3B2E7E;color:#fff;font:inherit;font-weight:600;cursor:pointer}" +
		"@media (min-width:600px){.iyp-sh-back{align-items:center}.iyp-sh{border-radius:14px;padding:18px 22px 22px}.iyp-sh-grip{display:none}}" +
		"@media (prefers-reduced-motion:reduce){.iyp-sh-back,.iyp-sh{transition:none}}" +
		/* Dark mode (2026-11-12) */
		"[data-iyp-theme=dark] .iyp-sh{background:#1B1736;color:#F0EEFA;box-shadow:0 -8px 30px rgba(0,0,0,.5)}" +
		"[data-iyp-theme=dark] .iyp-sh-grip{background:#463E7A}" +
		"[data-iyp-theme=dark] .iyp-sh-head small,[data-iyp-theme=dark] .iyp-sh-opt{color:#C9C4E2}" +
		"[data-iyp-theme=dark] .iyp-sh-x{background:#2A2550;color:#E9E6F2}" +
		"[data-iyp-theme=dark] .iyp-sh-link input{background:#141029;border-color:#463E7A;color:#E9E6F2}" +
		"[data-iyp-theme=dark] .iyp-sh-link button{background:#AFA2F5;color:#100D22}" +
		"[data-iyp-theme=dark] .iyp-sh-back{background:rgba(0,0,0,.6)}";

	// Brand marks, simplified
	var ICONS = {
		whatsapp: '<path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm5.3 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.1-4.5-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.9s.7-2 1-2.3c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.9 2.1c.1.2.1.3 0 .5l-.3.5-.4.5c-.2.2-.3.3-.1.6.2.3.8 1.3 1.7 2.1 1.2 1 2.1 1.4 2.4 1.5.3.1.5.1.6-.1l.9-1.1c.2-.3.4-.2.7-.1l2 1c.3.1.5.2.5.3.1.2.1.7-.2 1.3z"/>',
		facebook: '<path d="M14 8h3V4h-3c-2.8 0-4 1.8-4 4.3V10H7v4h3v8h4v-8h3l1-4h-4V8.6c0-.4.3-.6.6-.6z"/>',
		linkedin: '<path d="M6.5 8.5h-3V20h3V8.5zM5 3.5A1.8 1.8 0 1 0 5 7a1.8 1.8 0 0 0 0-3.5zM20.5 13.4c0-3.2-1.7-5.1-4.3-5.1-1.5 0-2.5.8-3 1.6V8.5h-3V20h3v-6.2c0-1.5.7-2.6 2-2.6s1.9 1 1.9 2.6V20h3.4v-6.6z"/>',
		x: '<path d="M17.8 3h3.1l-6.8 7.8L22 21h-6.2l-4.9-6.4L5.3 21H2.2l7.3-8.3L2 3h6.4l4.4 5.8L17.8 3zm-1.1 16.2h1.7L7.4 4.7H5.6l11.1 14.5z"/>',
		telegram: '<path d="M21.5 4.3 18.4 19c-.2 1-.8 1.3-1.7.8l-4.6-3.4-2.2 2.1c-.2.2-.5.5-1 .5l.3-4.8 8.7-7.8c.4-.3-.1-.5-.6-.2L6.6 13 2 11.6c-1-.3-1-1 .2-1.5L20.2 3c.8-.3 1.6.2 1.3 1.3z"/>',
		mail: '<path d="M3 5h18a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zm9 7.2L4 7.4V17h16V7.4l-8 4.8zM5.2 7 12 11l6.8-4H5.2z"/>',
		sms: '<path d="M4 3h16a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2zm3 7a1.3 1.3 0 1 0 0 2.6A1.3 1.3 0 0 0 7 10zm5 0a1.3 1.3 0 1 0 0 2.6 1.3 1.3 0 0 0 0-2.6zm5 0a1.3 1.3 0 1 0 0 2.6 1.3 1.3 0 0 0 0-2.6z"/>',
		copy: '<path d="M8 3h11a2 2 0 0 1 2 2v11h-2V5H8V3zM4 7h11a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2zm0 2v11h11V9H4z"/>',
		more: '<path d="M5 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm7 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm7 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/>'
	};

	function el(html) {
		var d = document.createElement("div");
		d.innerHTML = html;
		return d.firstChild;
	}

	function esc(s) {
		return String(s).replace(/[&<>"']/g, function (c) {
			return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
		});
	}

	function copyText(text, done) {
		if (navigator.clipboard && window.isSecureContext) {
			navigator.clipboard.writeText(text).then(done, function () { legacyCopy(text, done); });
		} else {
			legacyCopy(text, done);
		}
	}

	// http:// pages have no clipboard API; a selected textarea + execCommand still works there
	function legacyCopy(text, done) {
		var t = document.createElement("textarea");
		t.value = text;
		t.setAttribute("readonly", "");
		t.style.cssText = "position:fixed;top:0;left:0;opacity:0";
		document.body.appendChild(t);
		t.select();
		t.setSelectionRange(0, text.length);
		var ok = false;
		try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
		document.body.removeChild(t);
		if (ok) done();
		else window.prompt("Copy this link:", text);
	}

	var styled = false;

	window.iypShare = function (title, url) {
		if (!styled) {
			var s = document.createElement("style");
			s.textContent = css;
			document.head.appendChild(s);
			styled = true;
		}
		title = title || document.title;
		var text = title + " - " + url;
		var u = encodeURIComponent(url), t = encodeURIComponent(title), tx = encodeURIComponent(text);
		var options = [
			["WhatsApp", "whatsapp", "#25D366", "https://wa.me/?text=" + tx],
			["Facebook", "facebook", "#1877F2", "https://www.facebook.com/sharer/sharer.php?u=" + u],
			["LinkedIn", "linkedin", "#0A66C2", "https://www.linkedin.com/sharing/share-offsite/?url=" + u],
			["X", "x", "#111111", "https://twitter.com/intent/tweet?text=" + t + "&url=" + u],
			["Telegram", "telegram", "#229ED9", "https://t.me/share/url?url=" + u + "&text=" + t],
			["Email", "mail", "#6B665E", "mailto:?subject=" + t + "&body=" + tx],
			["SMS", "sms", "#3B8E5A", "sms:?&body=" + tx]
		];

		var grid = options.map(function (o) {
			var external = o[3].indexOf("http") === 0;
			return '<a class="iyp-sh-opt" href="' + esc(o[3]) + '"' + (external ? ' target="_blank" rel="noopener"' : "") +
				'><i style="background:' + o[2] + '"><svg viewBox="0 0 24 24" aria-hidden="true">' + ICONS[o[1]] + "</svg></i>" + o[0] + "</a>";
		}).join("");
		if (navigator.share) {
			grid += '<button type="button" class="iyp-sh-opt" data-more><i style="background:#3B2E7E"><svg viewBox="0 0 24 24" aria-hidden="true">' +
				ICONS.more + "</svg></i>More apps</button>";
		}

		var back = el(
			'<div class="iyp-sh-back" role="presentation"><div class="iyp-sh" role="dialog" aria-modal="true" aria-label="Share">' +
			'<div class="iyp-sh-grip" aria-hidden="true"></div>' +
			'<div class="iyp-sh-head"><div><b>Share this page</b><small>' + esc(title) + "</small></div>" +
			'<button type="button" class="iyp-sh-x" aria-label="Close">&times;</button></div>' +
			'<div class="iyp-sh-grid">' + grid + "</div>" +
			'<div class="iyp-sh-link"><input type="text" readonly value="' + esc(url) + '" aria-label="Page link">' +
			'<button type="button" data-copy-link>Copy link</button></div>' +
			"</div></div>"
		);
		document.body.appendChild(back);
		var lastFocus = document.activeElement;
		requestAnimationFrame(function () { back.classList.add("open"); });

		function close() {
			back.classList.remove("open");
			document.removeEventListener("keydown", onKey);
			setTimeout(function () { back.remove(); }, 200);
			if (lastFocus && lastFocus.focus) lastFocus.focus();
		}
		function onKey(e) { if (e.key === "Escape") close(); }
		document.addEventListener("keydown", onKey);

		back.addEventListener("click", function (e) { if (e.target === back) close(); });
		back.querySelector(".iyp-sh-x").addEventListener("click", close);
		back.querySelectorAll("a.iyp-sh-opt").forEach(function (a) {
			a.addEventListener("click", function () { setTimeout(close, 150); });
		});
		var copyBtn = back.querySelector("[data-copy-link]");
		copyBtn.addEventListener("click", function () {
			copyText(url, function () {
				copyBtn.textContent = "Copied ✓";
				setTimeout(close, 900);
			});
		});
		var more = back.querySelector("[data-more]");
		if (more) {
			more.addEventListener("click", function () {
				close();
				navigator.share({ title: title, url: url }).catch(function () {});
			});
		}
		back.querySelector(".iyp-sh-x").focus();
	};
})();
