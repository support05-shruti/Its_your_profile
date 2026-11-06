// Home page motion: reveal sections as they scroll in, parallax circles, frosted header,
// scroll progress bar and the business count counting up. CSS does the animating.
(function () {
	var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
	var nav = document.querySelector(".iyp-nav");
	var bar = document.querySelector(".iyp-progress");
	var circles = document.querySelectorAll("[data-parallax]");
	var targets = document.querySelectorAll(".iyp-reveal, .iyp-stagger");
	window.__iypMotion = true;

	// Each child of a stagger group gets its index, which CSS turns into a delay
	document.querySelectorAll(".iyp-stagger").forEach(function (group) {
		Array.prototype.forEach.call(group.children, function (child, i) {
			child.style.setProperty("--i", i);
		});
	});

	function countUp(scope) {
		scope.querySelectorAll("[data-count]").forEach(function (el) {
			var end = +el.dataset.count, start = performance.now();
			if (reduce || !end) return;
			(function step(now) {
				var p = Math.min((now - start) / 1200, 1);
				el.textContent = Math.round(end * (1 - Math.pow(1 - p, 3))).toLocaleString();
				if (p < 1) requestAnimationFrame(step);
			})(start);
		});
	}

	function show(el) {
		el.classList.add("in");
		countUp(el);
		// Once the entrance is over, hover effects should react at once, without the stagger delay
		if (el.classList.contains("iyp-stagger")) {
			setTimeout(function () { el.classList.add("done"); }, 600 + el.children.length * 90);
		}
	}

	if (reduce || !("IntersectionObserver" in window)) {
		targets.forEach(show);
	} else {
		var io = new IntersectionObserver(function (entries) {
			entries.forEach(function (e) {
				if (!e.isIntersecting) return;
				show(e.target);
				io.unobserve(e.target);
			});
		}, { threshold: 0.15, rootMargin: "0px 0px -40px 0px" });
		targets.forEach(function (el) { io.observe(el); });
	}

	var ticking = false;
	function onScroll() {
		var y = window.scrollY;
		var max = document.documentElement.scrollHeight - window.innerHeight;
		if (nav) nav.classList.toggle("scrolled", y > 8);
		if (bar) bar.style.transform = "scaleX(" + (max > 0 ? Math.min(y / max, 1) : 0) + ")";
		if (!reduce) {
			circles.forEach(function (c) {
				c.style.transform = "translate3d(0," + (y * c.dataset.parallax).toFixed(1) + "px,0)";
			});
		}
		ticking = false;
	}
	window.addEventListener("scroll", function () {
		if (!ticking) {
			ticking = true;
			requestAnimationFrame(onScroll);
		}
	}, { passive: true });
	onScroll();

	// CHANGE NOTE
	// Date: 2026-11-05
	// Change: Dark theme toggle button in the header.
	// Reason: Let visitors switch between light and dark. The inline script in home.html sets the
	// starting theme; this wires the button, saves an explicit choice, and keeps following the
	// system setting until the visitor picks one.
	var root = document.documentElement;
	var toggle = document.querySelector(".iyp-theme");
	var systemDark = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

	function applyTheme(theme) {
		root.setAttribute("data-iyp-theme", theme);
		if (toggle) toggle.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
	}
	function savedTheme() {
		try { return localStorage.getItem("iyp-theme"); } catch (e) { return null; }
	}

	applyTheme(root.getAttribute("data-iyp-theme") === "dark" ? "dark" : "light");
	if (toggle) {
		toggle.addEventListener("click", function () {
			var next = root.getAttribute("data-iyp-theme") === "dark" ? "light" : "dark";
			applyTheme(next);
			// Storage can be blocked (private mode); the toggle still works for this visit
			try { localStorage.setItem("iyp-theme", next); } catch (e) { /* ignore */ }
		});
	}
	if (systemDark && systemDark.addEventListener) {
		systemDark.addEventListener("change", function (e) {
			if (!savedTheme()) applyTheme(e.matches ? "dark" : "light");
		});
	}
})();
