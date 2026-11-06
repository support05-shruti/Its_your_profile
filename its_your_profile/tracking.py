"""Visitor and crawler counts for each Business Profile, behind the owner's reports.

- People are counted by the profile page's script (page view, Call, WhatsApp, Save Contact...),
  with the site they came from: ChatGPT, Perplexity, Google...  Crawlers don't run scripts,
  so they never inflate these numbers.
- AI and search crawlers are counted on the server from their User-Agent when they fetch a
  profile page or /llms.txt.
- The owner is told in the app, like LinkedIn's "who viewed your profile": a bell alert in Desk
  and the /notifications page. Taps on Call, WhatsApp... come at once; views and crawler visits
  are held back so a busy page doesn't flood them.
"""

import re
from urllib.parse import urlparse

import frappe
from frappe.rate_limiter import rate_limit

EVENTS = ("View", "Call", "WhatsApp", "Email", "Directions", "Website", "Save Contact", "Share", "Social Link")

# User-Agent fragment → crawler. Specific names come before Googlebot and bingbot,
# which also appear inside some of them.
CRAWLERS = (
	("OAI-SearchBot", "ChatGPT Search"),
	("ChatGPT-User", "ChatGPT"),
	("GPTBot", "OpenAI GPTBot"),
	("Perplexity-User", "Perplexity"),
	("PerplexityBot", "Perplexity"),
	("Claude-SearchBot", "Claude Search"),
	("Claude-User", "Claude"),
	("ClaudeBot", "Anthropic ClaudeBot"),
	("Google-CloudVertexBot", "Google Gemini"),
	("Applebot", "Apple"),
	("meta-externalagent", "Meta AI"),
	("Amazonbot", "Amazon"),
	("DuckAssistBot", "DuckDuckGo AI"),
	("MistralAI-User", "Mistral"),
	("Bytespider", "ByteDance"),
	("Googlebot", "Google"),
	("bingbot", "Bing / Copilot"),
)
SEARCH_CRAWLERS = {"Google", "Bing / Copilot"}

# Referrer domain → where a person came from
SOURCE_DOMAINS = (
	("chatgpt.com", "ChatGPT"),
	("openai.com", "ChatGPT"),
	("perplexity.ai", "Perplexity"),
	("gemini.google.com", "Gemini"),
	("claude.ai", "Claude"),
	("copilot.microsoft.com", "Copilot"),
	("grok.com", "Grok"),
	("deepseek.com", "DeepSeek"),
	("meta.ai", "Meta AI"),
	("bing.com", "Bing"),
	("duckduckgo.com", "DuckDuckGo"),
	("facebook.com", "Facebook"),
	("instagram.com", "Instagram"),
	("linkedin.com", "LinkedIn"),
	("lnkd.in", "LinkedIn"),
	("whatsapp.com", "WhatsApp"),
	("x.com", "X"),
	("twitter.com", "X"),
	("t.co", "X"),
	("youtube.com", "YouTube"),
)
GOOGLE = re.compile(r"(^|\.)google\.[a-z.]+$")
AI_SOURCES = {"ChatGPT", "Perplexity", "Gemini", "Claude", "Copilot", "Grok", "DeepSeek", "Meta AI"}

# Event → (icon, what the visitor did), for the owner's notifications
ALERTS = {
	"View": ("👀", "viewed your page"),
	"Call": ("📞", "tapped Call"),
	"WhatsApp": ("💬", "tapped WhatsApp"),
	"Email": ("✉️", "tapped Email"),
	"Directions": ("📍", "asked for directions"),
	"Website": ("🌐", "opened your website"),
	"Save Contact": ("📇", "saved your contact"),
	"Share": ("🔗", "shared your page"),
	"Social Link": ("🔗", "opened one of your social links"),
}
LEADS = ("Call", "WhatsApp", "Email", "Directions", "Save Contact")

# Seconds before the same kind of alert is sent again for a profile
VIEW_ALERT_GAP = 60 * 60
TAP_ALERT_GAP = 60
AI_CRAWL_ALERT_GAP = 24 * 60 * 60


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60)
def track(profile: str, event: str, referrer: str | None = None, utm: str | None = None):
	"""Called by the profile page's script for a page view or a button tap."""
	if event not in EVENTS or not counts_as_visitor():
		return
	if not frappe.db.exists("Business Profile", {"name": profile, "published": 1}):
		return
	source = source_of(referrer, utm)
	log(profile, event, visitor="Person", source=source, referrer=referrer)
	notify_visit(profile, event, source)


def log_crawler_visit(profile: str | None = None):
	"""Count an AI or search crawler fetching a profile page or /llms.txt. Never breaks the page."""
	try:
		crawler = crawler_name(frappe.get_request_header("User-Agent"))
		if not crawler:
			return
		log(
			profile,
			"Crawl",
			visitor="Search Crawler" if crawler in SEARCH_CRAWLERS else "AI Crawler",
			crawler=crawler,
			path=frappe.request.path if frappe.request else None,
		)
		if profile:
			notify_crawl(profile, crawler)
		# Pages are GET requests, which Frappe rolls back
		frappe.db.commit()
	except Exception:
		frappe.log_error("Profile Visit: could not log crawler visit")


def log(profile, event, visitor, source=None, crawler=None, referrer=None, path=None):
	frappe.get_doc(
		{
			"doctype": "Profile Visit",
			"business_profile": profile,
			"event": event,
			"visitor": visitor,
			"source": source,
			"crawler": crawler,
			"referrer": (referrer or "")[:500] or None,
			"path": path,
		}
	).insert(ignore_permissions=True)


def notify_visit(profile, event, source):
	"""'📞 Someone tapped Call · came from ChatGPT'. Views wait an hour, taps a minute, per source."""
	icon, action = ALERTS[event]
	gap = VIEW_ALERT_GAP if event == "View" else TAP_ALERT_GAP
	came_from = "" if source == "Direct" else f" · came from {source}"
	notify_owner(profile, f"{icon} Someone {action}{came_from}", f"{event}:{source}", gap)


def notify_crawl(profile, crawler):
	"""'🤖 ChatGPT read your page for the first time'. Search crawlers only on that first visit."""
	first = frappe.db.count("Profile Visit", {"business_profile": profile, "crawler": crawler}) == 1
	if crawler in SEARCH_CRAWLERS and not first:
		return
	when = " for the first time" if first else ""
	notify_owner(profile, f"🤖 {crawler} read your page{when}", f"Crawl:{crawler}", AI_CRAWL_ALERT_GAP)


def notify_owner(profile, message, kind, gap):
	"""Add a Notification Log for the profile's owner: the Desk bell and /notifications show it."""
	try:
		owner, company = frappe.db.get_value("Business Profile", profile, ["owner", "company_name"]) or (None, None)
		# Owners looking at their own page are not visitors
		if not owner or owner in ("Guest", frappe.session.user):
			return

		key = f"iyp_alert:{profile}:{kind}"
		if frappe.cache().get_value(key):
			return
		frappe.cache().set_value(key, 1, expires_in_sec=gap)

		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": owner,
				"type": "Alert",  # Alerts show in the bell without sending an email
				"document_type": "Business Profile",
				"document_name": profile,
				"subject": f"{message} · {frappe.utils.escape_html(company or profile)}",
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error("Profile Visit: could not notify the owner")


def counts_as_visitor() -> bool:
	"""Our own staff checking pages are not visitors; neither are bots that run scripts."""
	if crawler_name(frappe.get_request_header("User-Agent")):
		return False
	user = frappe.session.user
	return user == "Guest" or frappe.get_cached_value("User", user, "user_type") != "System User"


def crawler_name(user_agent: str | None) -> str | None:
	agent = (user_agent or "").lower()
	for fragment, name in CRAWLERS:
		if fragment.lower() in agent:
			return name


def source_of(referrer: str | None, utm: str | None = None) -> str:
	"""'https://chatgpt.com/' → 'ChatGPT'. ChatGPT also adds ?utm_source=chatgpt.com to its links."""
	utm = (utm or "").strip().lower()
	for domain, name in SOURCE_DOMAINS:
		if utm and (utm == domain or utm == name.lower()):
			return name

	host = (urlparse(referrer or "").hostname or "").lower()
	if not host:
		return "Direct"
	if host == "gemini.google.com":
		return "Gemini"
	for domain, name in SOURCE_DOMAINS:
		if host == domain or host.endswith("." + domain):
			return name
	if GOOGLE.search(host):
		return "Google"
	if host == (urlparse(frappe.utils.get_url()).hostname or "").lower():
		return "It's Your Profile"  # directory or home page
	return "Other website"
