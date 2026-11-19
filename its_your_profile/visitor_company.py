"""2026-11-19: "Someone from Infosys, Pune viewed your page", like LinkedIn's "someone from Google
viewed your profile".

Each visitor's internet address (IP) is looked up on ipinfo.io in a background job. Big companies,
colleges and government offices own their addresses, so the lookup names the organisation. Mobile
and home internet only name the provider (Jio, Airtel...), and cloud servers are bots or VPNs:
those are left out, so only real organisations show.

Only the organisation's name and city are kept on the Profile Visit, never the IP itself and never
the person. Each IP's answer is cached for a week, so a busy page stays within ipinfo's free limit.
An optional `ipinfo_token` in site_config.json raises that limit.
"""

import ipaddress
import re

import frappe
import requests

CACHE_SECONDS = 7 * 24 * 60 * 60
COMPANY_ALERT_GAP = 24 * 60 * 60

# Internet providers and cloud/hosting companies: their name says nothing about the visitor
NOT_A_VISITOR_COMPANY = re.compile(
	r"jio|airtel|bharti|bsnl|mtnl|vodafone|idea cellular|\bvi\b|hathway|atria|act fibernet|excitel|"
	r"tata (communications|teleservices|play|sky)|vsnl|tikona|spectra|you broadband|alliance broadband|"
	r"gtpl|den networks|siti|asianet|railtel|sify|netplus|fiber|fibre|broadband|telecom|telelink|"
	r"\bisp\b|internet service|cable|wireless|mobile|cellular|"
	r"amazon|aws|google|microsoft|azure|digitalocean|cloudflare|akamai|fastly|ovh|hetzner|linode|"
	r"vultr|oracle cloud|alibaba|tencent|contabo|leaseweb|hosting|datacenter|data center|"
	r"\bvpn\b|proxy|m247|zscaler|private customer",
	re.IGNORECASE,
)
LEGAL_ENDINGS = re.compile(
	r"[\s,.]+(private limited|pvt\.? ltd\.?|pvt|limited|ltd\.?|llp|inc\.?|llc|corporation|corp\.?|co\.?)$",
	re.IGNORECASE,
)


def request_ip() -> str | None:
	"""The visitor's public IP (Frappe reads X-Forwarded-For behind nginx / Frappe Cloud)."""
	ip = (getattr(frappe.local, "request_ip", None) or "").split(",")[0].strip()
	try:
		address = ipaddress.ip_address(ip)
	except ValueError:
		return None
	# Office LAN / localhost visits (like our test server) have no owner to look up
	return ip if address.is_global else None


def queue_lookup(visit_name: str):
	"""Called right after a Profile Visit is saved. Never slows down or breaks the visit."""
	try:
		ip = request_ip()
		if ip:
			frappe.enqueue(
				"its_your_profile.visitor_company.fill_company",
				queue="short",
				visit_name=visit_name,
				ip=ip,
				enqueue_after_commit=True,
			)
	except Exception:
		frappe.log_error("Visitor company: could not queue the lookup")


def fill_company(visit_name: str, ip: str):
	"""Background job: write the organisation's name and city on the visit, and tell the owner."""
	found = company_for_ip(ip)
	if not found or not frappe.db.exists("Profile Visit", visit_name):
		return
	frappe.db.set_value(
		"Profile Visit",
		visit_name,
		{"visitor_company": found["company"], "visitor_city": found["city"]},
		update_modified=False,
	)
	visit = frappe.db.get_value("Profile Visit", visit_name, ["business_profile", "event"], as_dict=True)
	if visit and visit.business_profile and visit.event == "View":
		from its_your_profile.tracking import notify_owner

		# The names come from an outside service, and the bell shows the subject as HTML
		org = frappe.utils.escape_html(found["company"] + (f", {found['city']}" if found["city"] else ""))
		notify_owner(
			visit.business_profile,
			f"🏢 Someone from {org} viewed your page",
			f"Company:{found['company']}",
			COMPANY_ALERT_GAP,
		)
	frappe.db.commit()


def company_for_ip(ip: str) -> dict | None:
	"""{'company': 'Infosys', 'city': 'Pune'}, or None for providers, clouds and failed lookups."""
	key = f"iyp_ip_company:{ip}"
	cached = frappe.cache.get_value(key)
	if cached is not None:
		return cached or None

	try:
		token = frappe.conf.get("ipinfo_token")
		response = requests.get(
			f"https://ipinfo.io/{ip}/json",
			params={"token": token} if token else None,
			timeout=5,
		)
		if response.status_code == 429:
			return None  # over the free limit for today: try again on the next visit
		data = response.json() if response.ok else {}
	except Exception:
		return None

	found = clean_company(data)
	frappe.cache.set_value(key, found or {}, expires_in_sec=CACHE_SECONDS)
	return found


def clean_company(data: dict) -> dict | None:
	"""'AS4758 National Informatics Centre' → 'National Informatics Centre'; providers → None."""
	org = re.sub(r"^AS\d+\s+", "", (data.get("org") or "").strip())
	if not org or data.get("bogon") or data.get("anycast") or NOT_A_VISITOR_COMPANY.search(org):
		return None
	if NOT_A_VISITOR_COMPANY.search(data.get("hostname") or ""):
		return None
	company = LEGAL_ENDINGS.sub("", org).strip(" ,.-")
	if len(company) < 2:
		return None
	return {"company": company[:140], "city": (data.get("city") or "").strip()[:80]}
