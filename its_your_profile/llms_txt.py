"""Plain-text files for search and AI crawlers, built from the published Business Profiles.

- /llms.txt: a short Markdown index of every business (llmstxt.org)
- /llms-full.txt: every business's full details in one Markdown file, ready for an LLM context window
- /robots.txt: the Website Settings rules, plus an explicit welcome for AI search crawlers
- /business/<name>.md: one profile as Markdown. The profile's own address gives the same Markdown
  to a client whose Accept header asks for text/markdown first; browsers and Google get the page.

Registered through the `page_renderer` hook so the responses are plain text, not themed web pages.
"""

import frappe
from frappe.utils import get_url
from frappe.website.page_renderers.base_renderer import BaseRenderer
from frappe.www.robots import get_context as get_website_robots

# Retrieval bots of ChatGPT, Perplexity, Claude, Gemini and Apple Intelligence
AI_CRAWLERS = (
	"GPTBot",
	"OAI-SearchBot",
	"ChatGPT-User",
	"PerplexityBot",
	"ClaudeBot",
	"Claude-SearchBot",
	"Claude-User",
	"Google-Extended",
	"Applebot-Extended",
)
# The desk, API and private files are of no use to a crawler
PRIVATE_PATHS = ("/app/", "/api/", "/private/")

PROFILE_FIELDS = [
	"name",
	"company_name",
	"route",
	"ai_summary",
	"about_business",
	"services",
	"business_nature",
	"employee_range",
	"established_year",
	"contact_person",
	"designation",
	"contact_linkedin_url",
	"phone",
	"email",
	"website_url",
	"address_line",
	"city",
	"state",
	"pincode",
	"google_maps_url",
]


class CrawlerTextPage(BaseRenderer):
	def can_render(self):
		self.profile = None if self.path in BUILDERS else markdown_profile(self.path)
		return self.path in BUILDERS or bool(self.profile)

	def render(self):
		from its_your_profile.tracking import log_crawler_visit

		if self.profile:
			log_crawler_visit(self.profile)
			doc = frappe.get_doc("Business Profile", self.profile)
			return self.build_response(
				doc.as_markdown(),
				headers={
					"Content-Type": "text/markdown; charset=utf-8",
					"Cache-Control": "public, max-age=3600",
					"Vary": "Accept",
					# The HTML page is the one to cite
					"Link": f'<{get_url(doc.route)}>; rel="canonical"',
				},
			)

		# Every crawler fetches robots.txt; only the llms files say an AI read the directory
		if self.path != "robots.txt":
			log_crawler_visit()
		return self.build_response(BUILDERS[self.path](), headers={"Cache-Control": "public, max-age=3600"})


def markdown_profile(path):
	"""Name of the published profile asked for as Markdown, else None. Runs for every page
	request, so anything that can't be a profile is turned away before the database."""
	if path.endswith(".md"):
		route = path[:-3]
	elif wants_markdown():
		route = path
	else:
		return None
	if not route.startswith("business/"):
		return None
	return frappe.db.get_value("Business Profile", {"route": route, "published": 1}, "name")


def wants_markdown():
	accept = (frappe.get_request_header("Accept") or "").lower()
	first = accept.split(",")[0].strip()
	return first.startswith("text/markdown") or ("text/markdown" in accept and "text/html" not in accept)


def published_profiles(fields):
	"""Published profiles as Business Profile documents (not saved), so their summary methods work."""
	rows = frappe.get_all(
		"Business Profile",
		filters={"published": 1, "route": ("is", "set")},
		fields=fields,
		order_by="company_name asc",
	)
	return [frappe.get_doc({"doctype": "Business Profile", **row}) for row in rows]


def get_llms_txt() -> str:
	profiles = published_profiles(PROFILE_FIELDS)

	lines = [
		"# It's Your Profile",
		"",
		"> A directory of Indian businesses. Each profile page carries Schema.org JSON-LD for the business,"
		" its contact person and its services.",
		"",
		f"Browse and search the directory: {get_url('directory')}",
		f"Full details of every business in one file: {get_url('llms-full.txt')}",
		"Every profile is also available as Markdown: add .md to its address.",
		"",
		"## Businesses",
		"",
	]
	for p in profiles:
		meta = ", ".join(x for x in (p.business_nature, p.city, p.state) if x)
		detail = " - ".join(x for x in (meta, p.get_summary()) if x)
		lines.append(f"- [{p.company_name}]({get_url(p.route)})" + (f": {detail}" if detail else ""))

	return "\n".join(lines) + "\n"


def get_llms_full_txt() -> str:
	names = frappe.get_all(
		"Business Profile",
		filters={"published": 1, "route": ("is", "set")},
		pluck="name",
		order_by="company_name asc",
	)
	lines = [
		"# It's Your Profile: full directory",
		"",
		f"> Details of every published business in the It's Your Profile directory ({len(names)} businesses).",
		f"> The short index is at {get_url('llms.txt')}.",
		"",
	]
	# Same Markdown as each profile's .md page, one heading level down
	for name in names:
		lines += [frappe.get_doc("Business Profile", name).as_markdown(level=2), ""]

	return "\n".join(lines)


def get_robots_txt() -> str:
	rules = (get_website_robots(frappe._dict()).get("robots_txt") or "").strip() or "User-agent: *\nAllow: /"
	lines = [
		rules,
		"",
		"# AI search and answer engines are welcome to read every public profile",
		*(f"User-agent: {bot}" for bot in AI_CRAWLERS),
		"Allow: /",
		*(f"Disallow: {path}" for path in PRIVATE_PATHS),
		"",
	]
	if "sitemap:" not in rules.lower():
		lines.append(f"Sitemap: {get_url('sitemap.xml')}")
	lines.append(f"# Plain-text index for language models: {get_url('llms.txt')}")
	return "\n".join(lines) + "\n"


BUILDERS = {
	"llms.txt": get_llms_txt,
	"llms-full.txt": get_llms_full_txt,
	"robots.txt": get_robots_txt,
}
