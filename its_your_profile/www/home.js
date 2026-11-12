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

	// CHANGE NOTE 2026-11-06: phone/tablet menu. The ☰ button opens the header links as a panel;
	// tapping a link, tapping outside or pressing Esc closes it.
	var menuBtn = document.querySelector(".iyp-menu-btn");
	var menu = document.getElementById("iyp-menu");
	if (menuBtn && menu) {
		var setMenu = function (open) {
			menu.classList.toggle("open", open);
			menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
		};
		menuBtn.addEventListener("click", function (e) {
			e.stopPropagation();
			setMenu(!menu.classList.contains("open"));
		});
		menu.addEventListener("click", function (e) {
			if (e.target.closest("a")) setMenu(false);
		});
		document.addEventListener("click", function (e) {
			if (menu.classList.contains("open") && !menu.contains(e.target)) setMenu(false);
		});
		document.addEventListener("keydown", function (e) {
			if (e.key === "Escape" && menu.classList.contains("open")) { setMenu(false); menuBtn.focus(); }
		});
	}

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

	// CHANGE NOTE
	// Date: 2026-11-06
	// Change: Upload card in the hero: tabs, drag & drop and file picker for the visiting card.
	// Reason: Start straight from the home page. The form needs a login, so the photo cannot be
	// uploaded here; it is shrunk and kept in this tab (sessionStorage), and the form's script
	// (my_business.js) uploads and reads it once the visitor arrives there, after login if needed.
	var upload = document.querySelector(".iyp-upload");
	if (upload) {
		var PENDING_KEY = "iyp-pending-card";
		var MAX_SIDE = 1600; // same size the form uses: plenty for the AI to read
		var createUrl = upload.getAttribute("data-create-url") || "/my-business/new";
		var tabs = upload.querySelectorAll('[role="tab"]');
		var drop = upload.querySelector(".iyp-drop");
		var fileInput = upload.querySelector("#iyp-card-file");
		var note = upload.querySelector(".iyp-drop-note");
		var noteText = note ? note.textContent : "";

		function selectTab(tab) {
			// Website results sit outside both panes; leaving them (2026-11-07) starts the tab fresh
			if (typeof scanState !== "undefined" && scanState.mode === "web") resetWeb();
			tabs.forEach(function (t) {
				var on = t === tab;
				t.setAttribute("aria-selected", on ? "true" : "false");
				t.tabIndex = on ? 0 : -1;
				document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
			});
		}
		tabs.forEach(function (tab, i) {
			tab.addEventListener("click", function () { selectTab(tab); });
			tab.addEventListener("keydown", function (e) {
				if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
				var next = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
				selectTab(next);
				next.focus();
			});
		});

		function say(text, isError) {
			if (!note) return;
			note.textContent = text;
			note.classList.toggle("err", !!isError);
		}

		// Shrink to a JPEG small enough to keep in sessionStorage (a few hundred KB)
		function shrink(file) {
			return new Promise(function (resolve, reject) {
				var img = new Image();
				img.onload = function () {
					var scale = Math.min(1, MAX_SIDE / Math.max(img.width, img.height));
					var canvas = document.createElement("canvas");
					canvas.width = Math.round(img.width * scale);
					canvas.height = Math.round(img.height * scale);
					canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
					URL.revokeObjectURL(img.src);
					resolve(canvas.toDataURL("image/jpeg", 0.85));
				};
				img.onerror = function () { URL.revokeObjectURL(img.src); reject(); };
				img.src = URL.createObjectURL(file);
			});
		}

		function sendToForm(dataUrl) {
			try {
				sessionStorage.setItem(PENDING_KEY, dataUrl);
			} catch (e) {
				/* Storage blocked or full: the visitor can still attach the card on the form */
			}
			window.location.href = createUrl;
		}

		// CHANGE NOTE 2026-11-06: scan on the home page. After the crop, the card shows with a
		// "Scan now" button; the photo is uploaded, read by the AI (api.read_visiting_card), the
		// details are shown to check, and "Create my page" saves it (api.create_profile_from_card).
		// No redirect. Needs a logged-in visitor (the upload and the AI read are per account).
		var scan = upload.querySelector(".iyp-scan");
		var scanImg = scan && scan.querySelector(".iyp-scan-photo img");
		var scanFields = scan && scan.querySelector(".iyp-scan-fields");
		var scanLabels = {};
		try { scanLabels = JSON.parse(scan.getAttribute("data-labels") || "{}"); } catch (e) { /* defaults below */ }
		// 2026-11-07: segment (industry) and business nature (a dropdown) after the company name
		var FIELD_ORDER = ["company_name", "segment", "business_nature", "contact_person", "designation", "phone", "email", "website_url", "address_line", "city", "state", "pincode"];
		var ALWAYS_SHOW = ["company_name", "segment", "business_nature", "contact_person", "phone", "email"];
		var NATURES = ["Service", "Manufacturing", "Hybrid/Trading"];
		var CHOOSE = "Choose...";
		try { NATURES = JSON.parse(scan.getAttribute("data-natures")) || NATURES; } catch (e) { /* default above */ }
		try { CHOOSE = JSON.parse(scan.getAttribute("data-choose")) || CHOOSE; } catch (e) { /* default above */ }
		var INPUT_HINTS = {
			phone: { type: "tel", inputmode: "tel", autocomplete: "tel" },
			email: { type: "email", inputmode: "email", autocomplete: "email" },
			website_url: { type: "url", inputmode: "url", autocomplete: "url" },
			pincode: { type: "text", inputmode: "numeric", autocomplete: "postal-code" },
			contact_person: { type: "text", autocomplete: "name" },
			company_name: { type: "text", autocomplete: "organization" }
		};
		var scanState = { front: null, back: null, read: null, mode: "card" };
		var editSide = "front"; // which side the crop window is editing

		function csrfToken() {
			return (window.frappe && frappe.csrf_token) || "";
		}
		// Frappe's error text: _server_messages (a JSON list of JSON objects) or the exception line
		function errorText(data, fallback) {
			try {
				if (data && data._server_messages) {
					var msgs = JSON.parse(data._server_messages).map(function (m) {
						try { return JSON.parse(m).message; } catch (e) { return m; }
					});
					var div = document.createElement("div");
					div.innerHTML = msgs.join(" ");
					if (div.textContent.trim()) return div.textContent.trim();
				}
				if (data && data.exception) return String(data.exception).split(":").slice(1).join(":").trim() || fallback;
			} catch (e) { /* fall through */ }
			return fallback;
		}
		function call(method, params) {
			return fetch("/api/method/" + method, {
				method: "POST",
				credentials: "same-origin",
				headers: { "Content-Type": "application/x-www-form-urlencoded", "X-Frappe-CSRF-Token": csrfToken(), Accept: "application/json" },
				body: new URLSearchParams(params)
			}).then(function (r) {
				return r.json().catch(function () { return {}; }).then(function (data) {
					if (!r.ok) throw new Error(errorText(data, "Something went wrong. Please try again."));
					return data.message;
				});
			});
		}
		// side: "front" or "back" (2026-11-07); each photo is uploaded once, even after Try again
		function uploadPhoto(side) {
			var s = scanState[side];
			if (s.fileUrl) return Promise.resolve(s.fileUrl);
			return fetch(s.dataUrl).then(function (r) { return r.blob(); }).then(function (blob) {
				var form = new FormData();
				form.append("file", blob, "visiting-card-" + side + "-" + Date.now() + ".jpg");
				form.append("is_private", "1");
				return fetch("/api/method/upload_file", {
					method: "POST", credentials: "same-origin",
					headers: { "X-Frappe-CSRF-Token": csrfToken(), Accept: "application/json" },
					body: form
				});
			}).then(function (r) {
				return r.json().catch(function () { return {}; }).then(function (data) {
					if (!r.ok || !data.message || !data.message.file_url) throw new Error(errorText(data, "The photo could not be uploaded. Please try again."));
					s.fileUrl = data.message.file_url;
					return s.fileUrl;
				});
			});
		}

		function setScan(state) {
			scan.setAttribute("data-state", state);
			scan.querySelectorAll("[data-show]").forEach(function (el) { el.hidden = el.getAttribute("data-show") !== state; });
			// Phones (2026-11-07): bring each new step into view, so nothing happens off-screen
			if (!scan.hidden && state !== "preview" && window.matchMedia("(max-width: 720px)").matches) {
				var target = state === "result" ? scan.querySelector('[data-show="result"]') : scan;
				requestAnimationFrame(function () {
					target.scrollIntoView({ behavior: "smooth", block: state === "result" ? "start" : "center" });
				});
			}
		}
		// Open the scan panel (first photo), keeping whatever side is already there (2026-11-07)
		// CHANGE NOTE 2026-11-07: the same panel serves the "Website link" tab. In website mode it sits
		// after the website form (not inside it, so Enter in a details box can't resubmit the site),
		// hides the photo parts, and shows website wording (.t-web) instead of card wording (.t-card).
		var cardPane = document.getElementById("iyp-pane-card");
		function setMode(mode) {
			scanState.mode = mode;
			if (!scan) return;
			scan.setAttribute("data-mode", mode);
			if (mode === "web") {
				if (webForm && scan.previousElementSibling !== webForm) webForm.parentNode.insertBefore(scan, webForm.nextSibling);
			} else if (cardPane && scan.parentNode !== cardPane) {
				cardPane.insertBefore(scan, cardPane.querySelector(".iyp-drop-note"));
			}
		}
		function resetWeb() {
			scanState = { front: null, back: null, read: null, mode: "card" };
			if (scan) scan.hidden = true;
			setMode("card");
			if (webForm) webForm.hidden = false;
		}
		function readWebsite(url) {
			if (!scan) { window.location.href = createUrl + "?website_url=" + encodeURIComponent(url); return; }
			scanState = { front: null, back: null, read: null, mode: "web", web: { url: url, map: null } };
			setMode("web");
			if (webForm) webForm.hidden = true;
			scan.hidden = false;
			setScan("scanning");
			call("its_your_profile.api.read_website", { url: url }).then(function (read) {
				scanState.read = read || {};
				scanState.web.map = scanState.read.map_url || null;
				renderFields(scanState.read);
				setScan("result");
			}).catch(function (err) {
				scan.querySelector("[data-error]").textContent = err.message;
				setScan("error");
			});
		}

		function openPanel() {
			setMode("card");
			var wasHidden = scan.hidden;
			if (drop) drop.hidden = true;
			say("");
			scan.hidden = false;
			setScan("preview");
			renderSides();
			if (wasHidden) scan.scrollIntoView({ behavior: "smooth", block: "center" });
		}
		function showScan(dataUrl) {
			if (!scan) { sendToForm(dataUrl); return; } // older page without the scan panel
			scanState.front = { dataUrl: dataUrl, fileUrl: null };
			scanState.read = null;
			openPanel();
		}
		// Front photo or "add the front" buttons; Scan now only once there is a front side
		function renderSides() {
			var hasFront = !!scanState.front;
			scanImg.hidden = !hasFront;
			if (hasFront) scanImg.src = scanState.front.dataUrl;
			scan.querySelector(".iyp-side-tag").hidden = !hasFront;
			scan.querySelector(".iyp-front-empty").hidden = hasFront;
			scan.querySelectorAll("[data-ready]").forEach(function (el) { el.hidden = !hasFront; });
			scan.querySelectorAll("[data-need-front]").forEach(function (el) { el.hidden = hasFront; });
			var go = scan.querySelector("[data-scan-now]");
			go.disabled = !hasFront;
			renderBack();
		}
		function resetScan() {
			if (scanState.mode === "web") { resetWeb(); return; } // "Try another website"
			scanState = { front: null, back: null, read: null, mode: "card" };
			scan.hidden = true;
			if (drop) drop.hidden = false;
			say(noteText);
			if (fileInput) fileInput.click();
		}
		function renderFields(values) {
			scanFields.innerHTML = "";
			FIELD_ORDER.forEach(function (fieldname) {
				var value = values[fieldname] || "";
				if (!value && ALWAYS_SHOW.indexOf(fieldname) === -1) return;
				var wrap = document.createElement("label");
				wrap.className = "iyp-scan-field" + (fieldname === "address_line" ? " wide" : "");
				var span = document.createElement("span");
				span.textContent = scanLabels[fieldname] || fieldname.replace(/_/g, " ");
				var input;
				if (fieldname === "business_nature") {
					// A dropdown with the profile's own choices (2026-11-07)
					input = document.createElement("select");
					[""].concat(NATURES).forEach(function (n) {
						var opt = document.createElement("option");
						opt.value = n;
						opt.textContent = n || CHOOSE;
						input.appendChild(opt);
					});
				} else {
					input = document.createElement("input");
					var hint = INPUT_HINTS[fieldname] || { type: "text" };
					Object.keys(hint).forEach(function (k) { input.setAttribute(k, hint[k]); });
				}
				input.name = fieldname;
				input.value = value;
				wrap.appendChild(span);
				wrap.appendChild(input);
				scanFields.appendChild(wrap);
			});
		}
		// Optional back side (2026-11-07): camera or gallery, cropped like the front
		function renderBack() {
			if (!scan) return;
			var hasBack = !!scanState.back;
			scan.querySelector(".iyp-back-empty").hidden = hasBack;
			var done = scan.querySelector(".iyp-back-done");
			done.hidden = !hasBack;
			if (hasBack) done.querySelector("img").src = scanState.back.dataUrl;
		}
		function setBack(dataUrl) {
			if (!scan) { sendToForm(dataUrl); return; }
			scanState.back = { dataUrl: dataUrl, fileUrl: null };
			scanState.read = null; // read again, now with both sides
			openPanel(); // may be the first photo: then the panel asks for the front
		}
		// Front first; the back only fills what the front left empty, and adds its links
		function mergeSides(front, back) {
			Object.keys(back || {}).forEach(function (key) {
				if (key !== "_links" && back[key] && !front[key]) front[key] = back[key];
			});
			var seen = {};
			front._links = (front._links || []).concat((back && back._links) || []).filter(function (l) {
				var k = (l.url || "").replace(/\/+$/, "").toLowerCase();
				if (!k || seen[k]) return false;
				seen[k] = true;
				return true;
			});
			return front;
		}
		function readSide(side) {
			return uploadPhoto(side).then(function (fileUrl) {
				return call("its_your_profile.api.read_visiting_card", { file_url: fileUrl });
			});
		}
		function scanNow() {
			setScan("scanning");
			readSide("front").then(function (front) {
				front = front || {};
				if (!scanState.back) return front;
				// An unreadable back side doesn't stop the page: the front's details are kept
				return readSide("back").then(function (back) { return mergeSides(front, back); }, function () { return front; });
			}).then(function (read) {
				scanState.read = read || {};
				renderFields(scanState.read);
				setScan("result");
				var first = scanFields.querySelector("input");
				if (first && window.matchMedia("(pointer: fine)").matches) first.focus();
			}).catch(function (err) {
				scan.querySelector("[data-error]").textContent = err.message;
				setScan("error");
			});
		}
		function createPage() {
			var values = {};
			scanFields.querySelectorAll("input, select").forEach(function (input) { values[input.name] = input.value.trim(); });
			if (!values.company_name) {
				var box = scanFields.querySelector("input[name=company_name]");
				if (box) { box.focus(); box.classList.add("need"); }
				return;
			}
			setScan("saving");
			var params = {
				values: JSON.stringify(values),
				links: JSON.stringify((scanState.read && scanState.read._links) || [])
			};
			if (scanState.mode === "web") {
				params.map_url = (scanState.web && scanState.web.map) || "";
			} else {
				params.file_url = scanState.front.fileUrl;
				params.back_file_url = (scanState.back && scanState.back.fileUrl) || "";
			}
			call("its_your_profile.api.create_profile_from_card", params).then(function (made) {
				// 2026-11-12: a page for this company already existed, so it was updated, not copied
				scan.querySelector("[data-done-name]").textContent = made.already_existed
					? (made.company_name || "") + " · You already had this page, so we updated it instead of making a copy."
					: made.company_name || "";
				var view = scan.querySelector("[data-done-view]");
				if (made.page_url) { view.href = made.page_url; view.hidden = false; } else { view.hidden = true; }
				scan.querySelector("[data-done-edit]").href = made.edit_url;
				setScan("done");
			}).catch(function (err) {
				scan.querySelector("[data-error]").textContent = err.message;
				setScan("error");
			});
		}
		if (scan) {
			scan.querySelectorAll("[data-scan-now], [data-scan-retry]").forEach(function (b) {
				b.addEventListener("click", function () {
					// A failed save (card already read) retries the save; otherwise read again
					if (scanState.read && b.hasAttribute("data-scan-retry")) createPage();
					else if (scanState.mode === "web" && scanState.web) readWebsite(scanState.web.url);
					else scanNow();
				});
			});
			scan.querySelectorAll("[data-scan-change]").forEach(function (b) { b.addEventListener("click", resetScan); });
			scan.querySelector("[data-scan-create]").addEventListener("click", createPage);
			scanFields.addEventListener("input", function (e) { e.target.classList.remove("need"); });
			scan.querySelector("[data-back-camera]").addEventListener("click", function () { pickPhoto("back", true); });
			scan.querySelector("[data-back-upload]").addEventListener("click", function () { pickPhoto("back", false); });
			scan.querySelector("[data-back-remove]").addEventListener("click", function () {
				scanState.back = null;
				scanState.read = null;
				if (!scanState.front) { // nothing left: back to the upload area
					scan.hidden = true;
					if (drop) drop.hidden = false;
					say(noteText);
					return;
				}
				renderSides();
			});
			// Started with the back side: these add the front (2026-11-07)
			scan.querySelector("[data-front-camera]").addEventListener("click", function () { pickPhoto("front", true); });
			scan.querySelector("[data-front-upload]").addEventListener("click", function () { pickPhoto("front", false); });
		}

		// Open the phone camera (capture) or the gallery for one side of the card (2026-11-07)
		function pickPhoto(side, camera) {
			var input = document.createElement("input");
			input.type = "file";
			input.accept = "image/*";
			if (camera) input.setAttribute("capture", "environment"); // the back camera
			input.style.display = "none";
			document.body.appendChild(input);
			input.addEventListener("change", function () {
				var file = input.files && input.files[0];
				input.remove();
				if (file) useFile(file, side);
			});
			input.click();
		}
		var frontCamera = upload.querySelector("[data-camera=front]");
		if (frontCamera) {
			frontCamera.addEventListener("click", function (e) {
				e.preventDefault();
				e.stopPropagation(); // don't also open the gallery picker of the drop area
				if (upload.getAttribute("data-logged-in") !== "1") { askToLogIn(); return; }
				pickPhoto("front", true);
			});
		}

		// CHANGE NOTE 2026-11-06: crop & rotate window. Cropper.js (MIT, same tool Frappe's forms use)
		// loads from cdnjs only when a photo is chosen. If it can't load, the photo goes on uncropped.
		var CROPPER_JS = "https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.js";
		var CROPPER_CSS = "https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.css";
		var cropperReady = null;
		function loadCropper() {
			if (window.Cropper) return Promise.resolve();
			if (cropperReady) return cropperReady;
			cropperReady = new Promise(function (resolve, reject) {
				var css = document.createElement("link");
				css.rel = "stylesheet";
				css.href = CROPPER_CSS;
				document.head.appendChild(css);
				var js = document.createElement("script");
				js.src = CROPPER_JS;
				js.onload = function () { resolve(); };
				js.onerror = function () { cropperReady = null; reject(); };
				document.head.appendChild(js);
			});
			return cropperReady;
		}

		var editor = upload.querySelector(".iyp-editor:not(.iyp-ask):not(.iyp-side)");
		var editorImg = editor && editor.querySelector(".iyp-editor-stage img");
		var cropper = null;
		var original = null; // the photo as chosen, for Reset

		function startCropper(src) {
			if (cropper) cropper.destroy();
			editorImg.src = src;
			cropper = new window.Cropper(editorImg, {
				viewMode: 1, autoCropArea: 0.92, background: false, responsive: true,
				dragMode: "move", toggleDragModeOnDblclick: false
			});
		}

		// Turn the photo itself and start again from it, so the crop box always fits the new shape
		function rotate(degrees) {
			if (!cropper) return;
			var src = editorImg;
			var canvas = document.createElement("canvas");
			canvas.width = src.naturalHeight;
			canvas.height = src.naturalWidth;
			var ctx = canvas.getContext("2d");
			ctx.translate(canvas.width / 2, canvas.height / 2);
			ctx.rotate((degrees * Math.PI) / 180);
			ctx.drawImage(src, -src.naturalWidth / 2, -src.naturalHeight / 2);
			startCropper(canvas.toDataURL("image/jpeg", 0.92));
		}

		function closeEditor() {
			if (cropper) { cropper.destroy(); cropper = null; }
			if (editor.open) editor.close();
		}

		function openEditor(dataUrl) {
			original = dataUrl;
			loadCropper().then(function () {
				say(noteText);
				editor.showModal();
				startCropper(dataUrl);
			}, function () {
				// No crop tool (slow or blocked internet): carry on with the photo as it is, on this
				// page; never send it to the old form (2026-11-07)
				if (editSide === "back") setBack(dataUrl); else showScan(dataUrl);
			});
		}

		if (editor) {
			editor.querySelectorAll("[data-rotate]").forEach(function (btn) {
				btn.addEventListener("click", function () { rotate(+btn.getAttribute("data-rotate")); });
			});
			editor.querySelector("[data-reset]").addEventListener("click", function () {
				if (original) startCropper(original);
			});
			editor.querySelectorAll("[data-editor-cancel]").forEach(function (btn) {
				btn.addEventListener("click", function () {
					closeEditor();
					if (!btn.classList.contains("iyp-btn-ghost")) return;
					if (editSide === "back") pickPhoto("back", false);
					else if (fileInput) fileInput.click();
				});
			});
			editor.addEventListener("cancel", function () { closeEditor(); }); // Esc key
			editor.querySelector("[data-editor-done]").addEventListener("click", function () {
				if (!cropper) return;
				var canvas = cropper.getCroppedCanvas({ maxWidth: MAX_SIDE, maxHeight: MAX_SIDE, fillColor: "#fff", imageSmoothingQuality: "high" });
				var dataUrl = canvas ? canvas.toDataURL("image/jpeg", 0.85) : original;
				closeEditor();
				// scan right here on the home page (2026-11-06); a back photo joins the front (2026-11-07)
				if (editSide === "back") setBack(dataUrl); else showScan(dataUrl);
			});
		}

		// CHANGE NOTE 2026-11-07: "Which side of the card is this?" for every photo picked, taken or
		// dropped, unless the button already said the side (e.g. "Take back photo").
		var sideDlg = upload.querySelector(".iyp-side");
		var sideAnswer = null;
		function askSide(dataUrl) {
			if (!sideDlg || !sideDlg.showModal) return Promise.resolve(scanState.front ? "back" : "front");
			sideDlg.querySelector(".iyp-side-preview img").src = dataUrl;
			// Suggest the side that is still missing
			var suggest = scanState.front && !scanState.back ? "back" : "front";
			sideDlg.querySelectorAll("[data-side]").forEach(function (b) {
				b.classList.toggle("suggest", b.getAttribute("data-side") === suggest);
			});
			return new Promise(function (resolve) {
				sideAnswer = resolve;
				sideDlg.showModal();
			});
		}
		function answerSide(side) {
			if (sideDlg.open) sideDlg.close();
			if (sideAnswer) { var done = sideAnswer; sideAnswer = null; done(side); }
		}
		if (sideDlg) {
			sideDlg.querySelectorAll("[data-side]").forEach(function (b) {
				b.addEventListener("click", function () { answerSide(b.getAttribute("data-side")); });
			});
			sideDlg.querySelector("[data-side-cancel]").addEventListener("click", function () { answerSide(null); });
			sideDlg.addEventListener("cancel", function (e) { e.preventDefault(); answerSide(null); }); // Esc key
		}

		function useFile(file, side) {
			if (!file) return;
			if (!/^image\//.test(file.type)) {
				say("Please choose a photo (JPG or PNG) of your visiting card.", true);
				return;
			}
			say("Opening your photo...");
			shrink(file).then(function (dataUrl) {
				return (side ? Promise.resolve(side) : askSide(dataUrl)).then(function (chosen) {
					if (!chosen) { say(scan && !scan.hidden ? "" : noteText); return; } // cancelled
					editSide = chosen === "back" ? "back" : "front";
					if (editor && editor.showModal) openEditor(dataUrl);
					else if (editSide === "back") setBack(dataUrl);
					else showScan(dataUrl);
				});
			}, function () {
				say("This photo could not be opened. Please try a JPG or PNG photo.", true);
			});
		}

		// CHANGE NOTE 2026-11-06: visitors who are not logged in are asked to log in before uploading
		// (click, drop or website link). After login they land on the form, which has the upload.
		var loggedIn = upload.getAttribute("data-logged-in") === "1";
		var ask = upload.querySelector(".iyp-ask");
		var askLogin = ask && ask.querySelector("[data-ask-login]");
		var webForm = upload.querySelector(".iyp-web");
		// Back to the home page after login/sign-up, where the card is scanned (a website link goes to the form)
		var askSignup = ask && ask.querySelector("[data-ask-signup]");
		function askToLogIn(target) {
			var back = encodeURIComponent(target || "/");
			if (!ask || !ask.showModal) { window.location.href = "/login?redirect-to=" + back; return; }
			if (askLogin) askLogin.href = "/login?redirect-to=" + back;
			if (askSignup) askSignup.href = "/login?redirect-to=" + back + "#signup";
			ask.showModal();
		}
		if (ask) {
			ask.querySelector("[data-ask-close]").addEventListener("click", function () { ask.close(); });
			ask.addEventListener("click", function (e) { if (e.target === ask) ask.close(); }); // click outside
		}
		if (!loggedIn) {
			if (drop) {
				drop.addEventListener("click", function (e) { e.preventDefault(); askToLogIn(); });
				drop.addEventListener("keydown", function (e) {
					if (e.key === "Enter" || e.key === " ") { e.preventDefault(); askToLogIn(); }
				});
			}
			if (webForm) {
				webForm.addEventListener("submit", function (e) {
					e.preventDefault();
					askToLogIn(); // back to the home page after login, where the website is read
				});
			}
		} else if (webForm) {
			// Logged in (2026-11-07): read the website right here, no redirect to the form
			webForm.addEventListener("submit", function (e) {
				e.preventDefault();
				var site = ((webForm.querySelector("input[name=website_url]") || {}).value || "").trim();
				if (site) readWebsite(site);
			});
		}

		if (fileInput) {
			fileInput.addEventListener("change", function () {
				useFile(fileInput.files && fileInput.files[0]);
				fileInput.value = "";
			});
		}
		if (drop) {
			["dragenter", "dragover"].forEach(function (type) {
				drop.addEventListener(type, function (e) {
					e.preventDefault();
					drop.classList.add("over");
				});
			});
			["dragleave", "dragend"].forEach(function (type) {
				drop.addEventListener(type, function () { drop.classList.remove("over"); });
			});
			drop.addEventListener("drop", function (e) {
				e.preventDefault();
				drop.classList.remove("over");
				if (!loggedIn) { askToLogIn(); return; }
				useFile(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]);
			});
		}
	}
})();
