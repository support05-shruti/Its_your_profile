"""IndexNow (2026-11-23): tell Bing (and Yandex, Seznam, Naver) about our pages the moment they
are published or changed, instead of waiting for their robots to find them. ChatGPT Search and
Microsoft Copilot answer from Bing, so this is how they learn about a new business page.
Google does not use IndexNow; for Google we have Search Console and sitemap.xml.

The key below is public by design: Bing fetches https://<site>/<KEY>.txt (served by llms_txt.py)
to check that the page list really comes from this website.
"""

import ipaddress
from urllib.parse import urlparse

import frappe
import requests
from frappe.utils import get_url

KEY = "f6da6bbf57b2ce3d2ddb62a6baf9232a"
ENDPOINT = "https://api.indexnow.org/indexnow"
# The address people and search engines use. Background jobs on Frappe Cloud may only know the
# site's internal name, so page addresses are always rebuilt on this one.
SITE = "https://itsyourprofile.com"
# The same page is sent again at most once in this many seconds (background saves come in bursts)
RESEND_GAP = 30 * 60


def is_public_site() -> bool:
	"""False on the test server (site1.local at 192.168.x.x, localhost): only the live site sends."""
	if (frappe.local.site or "").endswith((".local", ".localhost")) or frappe.local.site == "localhost":
		return False
	host = (urlparse(get_url()).hostname or "").lower()
	if not host or host == "localhost" or host.endswith((".local", ".localhost")):
		return False
	try:
		ipaddress.ip_address(host)
		return False  # a bare IP address
	except ValueError:
		return True


def on_live_site(url: str) -> str:
	"""'https://<any host>/business/x' → 'https://itsyourprofile.com/business/x'."""
	path = urlparse(url).path or "/"
	return SITE + (path if path.startswith("/") else "/" + path)


def submit(urls: list[str]):
	"""Send up to 10,000 of our page addresses to IndexNow. Never raises."""
	if not urls or not is_public_site():
		return
	urls = list(dict.fromkeys(on_live_site(u) for u in urls))[:10000]
	try:
		response = requests.post(
			ENDPOINT,
			json={"host": urlparse(SITE).hostname, "key": KEY, "keyLocation": f"{SITE}/{KEY}.txt", "urlList": urls},
			headers={"Content-Type": "application/json; charset=utf-8"},
			timeout=20,
		)
		# 200 OK and 202 Accepted are both success
		if response.status_code not in (200, 202):
			frappe.log_error(
				title="IndexNow refused our pages",
				message=f"HTTP {response.status_code}: {response.text[:500]}\n\n" + "\n".join(urls[:50]),
			)
	except Exception:
		frappe.log_error(title="IndexNow could not be reached")


def queue_profile(doc, method=None):
	"""Business Profile on_update: a published page was created or changed, tell Bing in the background."""
	if not (doc.get("published") and doc.get("route")) or not is_public_site():
		return
	url = get_url(doc.route)
	cache_key = f"iyp:indexnow:{doc.name}"
	if frappe.cache.get_value(cache_key):
		return
	frappe.cache.set_value(cache_key, 1, expires_in_sec=RESEND_GAP)
	frappe.enqueue(
		"its_your_profile.indexnow.submit",
		urls=[url, get_url("/directory")],
		queue="short",
		enqueue_after_commit=True,
	)


def submit_all():
	"""after_migrate (every deploy): send every public page once, so Bing always has the full list."""
	if not is_public_site():
		return
	# Sent straight away (one request, 20 s at most): background workers may be restarting during a deploy
	try:
		from its_your_profile.llms_txt import sitemap_links

		submit([link["loc"] for link in sitemap_links()])
	except Exception:
		frappe.log_error(title="IndexNow: could not send the page list")
