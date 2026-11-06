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
		var FIELD_ORDER = ["company_name", "contact_person", "designation", "phone", "email", "website_url", "address_line", "city", "state", "pincode"];
		var ALWAYS_SHOW = ["company_name", "contact_person", "phone", "email"];
		var INPUT_HINTS = {
			phone: { type: "tel", inputmode: "tel", autocomplete: "tel" },
			email: { type: "email", inputmode: "email", autocomplete: "email" },
			website_url: { type: "url", inputmode: "url", autocomplete: "url" },
			pincode: { type: "text", inputmode: "numeric", autocomplete: "postal-code" },
			contact_person: { type: "text", autocomplete: "name" },
			company_name: { type: "text", autocomplete: "organization" }
		};
		var scanState = { dataUrl: null, fileUrl: null, read: null };

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
		function uploadPhoto(dataUrl) {
			if (scanState.fileUrl) return Promise.resolve(scanState.fileUrl); // already uploaded (Try again)
			return fetch(dataUrl).then(function (r) { return r.blob(); }).then(function (blob) {
				var form = new FormData();
				form.append("file", blob, "visiting-card-" + Date.now() + ".jpg");
				form.append("is_private", "1");
				return fetch("/api/method/upload_file", {
					method: "POST", credentials: "same-origin",
					headers: { "X-Frappe-CSRF-Token": csrfToken(), Accept: "application/json" },
					body: form
				});
			}).then(function (r) {
				return r.json().catch(function () { return {}; }).then(function (data) {
					if (!r.ok || !data.message || !data.message.file_url) throw new Error(errorText(data, "The photo could not be uploaded. Please try again."));
					scanState.fileUrl = data.message.file_url;
					return scanState.fileUrl;
				});
			});
		}

		function setScan(state) {
			scan.setAttribute("data-state", state);
			scan.querySelectorAll("[data-show]").forEach(function (el) { el.hidden = el.getAttribute("data-show") !== state; });
		}
		function showScan(dataUrl) {
			if (!scan) { sendToForm(dataUrl); return; } // older page without the scan panel
			scanState = { dataUrl: dataUrl, fileUrl: null, read: null };
			scanImg.src = dataUrl;
			if (drop) drop.hidden = true;
			say("");
			scan.hidden = false;
			setScan("preview");
			scan.scrollIntoView({ behavior: "smooth", block: "center" });
		}
		function resetScan() {
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
				var input = document.createElement("input");
				var hint = INPUT_HINTS[fieldname] || { type: "text" };
				Object.keys(hint).forEach(function (k) { input.setAttribute(k, hint[k]); });
				input.name = fieldname;
				input.value = value;
				wrap.appendChild(span);
				wrap.appendChild(input);
				scanFields.appendChild(wrap);
			});
		}
		function scanNow() {
			setScan("scanning");
			uploadPhoto(scanState.dataUrl).then(function (fileUrl) {
				return call("its_your_profile.api.read_visiting_card", { file_url: fileUrl });
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
			scanFields.querySelectorAll("input").forEach(function (input) { values[input.name] = input.value.trim(); });
			if (!values.company_name) {
				var box = scanFields.querySelector("input[name=company_name]");
				if (box) { box.focus(); box.classList.add("need"); }
				return;
			}
			setScan("saving");
			call("its_your_profile.api.create_profile_from_card", {
				file_url: scanState.fileUrl,
				values: JSON.stringify(values),
				links: JSON.stringify((scanState.read && scanState.read._links) || [])
			}).then(function (made) {
				scan.querySelector("[data-done-name]").textContent = made.company_name || "";
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
					if (scanState.read && b.hasAttribute("data-scan-retry")) createPage(); else scanNow();
				});
			});
			scan.querySelectorAll("[data-scan-change]").forEach(function (b) { b.addEventListener("click", resetScan); });
			scan.querySelector("[data-scan-create]").addEventListener("click", createPage);
			scanFields.addEventListener("input", function (e) { e.target.classList.remove("need"); });
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

		var editor = upload.querySelector(".iyp-editor:not(.iyp-ask)");
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
				sendToForm(dataUrl); // no cropper available: carry on with the photo as it is
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
					if (btn.classList.contains("iyp-btn-ghost") && fileInput) fileInput.click();
				});
			});
			editor.addEventListener("cancel", function () { closeEditor(); }); // Esc key
			editor.querySelector("[data-editor-done]").addEventListener("click", function () {
				if (!cropper) return;
				var canvas = cropper.getCroppedCanvas({ maxWidth: MAX_SIDE, maxHeight: MAX_SIDE, fillColor: "#fff", imageSmoothingQuality: "high" });
				var dataUrl = canvas ? canvas.toDataURL("image/jpeg", 0.85) : original;
				closeEditor();
				showScan(dataUrl); // scan right here on the home page (2026-11-06)
			});
		}

		function useFile(file) {
			if (!file) return;
			if (!/^image\//.test(file.type)) {
				say("Please choose a photo (JPG or PNG) of your visiting card.", true);
				return;
			}
			say("Opening your photo...");
			shrink(file).then(function (dataUrl) {
				if (editor && editor.showModal) openEditor(dataUrl);
				else showScan(dataUrl);
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
					var site = (webForm.querySelector("input[name=website_url]") || {}).value || "";
					askToLogIn(createUrl + (site ? "?website_url=" + encodeURIComponent(site.trim()) : ""));
				});
			}
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
