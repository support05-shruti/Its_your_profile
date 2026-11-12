"""Public home page at /: what It's Your Profile does, with a start bar that leads to /create."""

import frappe

from its_your_profile.www.directory import is_backend_user

# Where "Create my page" goes: the existing sign-up form until the no-login /create page is built
CREATE_URL = "/my-business/new"

AUDIENCES = (
	("Chartered Accountants", "blue"),
	("Interior Designers", "peach"),
	("Doctors & Clinics", "mint"),
	("Manufacturers", "lilac"),
	("Traders & Distributors", "lemon"),
	("BNI Members", "blue"),
	("Lawyers", "rose"),
	("Consultants", "mint"),
	("Shops & Showrooms", "peach"),
	("Freelancers", "lilac"),
)


# FAQ on the home page (2026-11-07). Answers are always shown open (not hidden behind a click) and
# the same text goes into FAQPage structured data, so AI assistants and Google read it directly.
FAQS = (
	(
		"What is It's Your Profile?",
		"It's Your Profile turns your visiting card into a business page on the web. The page shows your company, "
		"services, contact details, address, LinkedIn and map, with Call and WhatsApp buttons, in a format that AI "
		"assistants such as ChatGPT, Gemini and Claude can read and recommend.",
	),
	(
		"How does it help my business get found by AI assistants?",
		"More and more customers ask ChatGPT, Gemini, Claude or Perplexity who to call. These assistants can only "
		"recommend businesses they can find and understand. Your page gives them your business name, what you do, "
		"where you are and how to contact you, in clear text and structured data they read easily.",
	),
	(
		"How do I create my page?",
		"Sign up free, then scan your visiting card with your phone camera or upload a photo of it. Our AI reads the "
		"card and fills in your details. You can also paste your website link. Check the details, save, and your page "
		"is ready in about a minute.",
	),
	(
		"Is it really free?",
		"Yes. Every feature is free for your first 6 months. You don't need a credit card or any payment details. "
		"We will tell you about plans well before the free period ends, and nothing is charged unless you choose a plan.",
	),
	(
		"Do I need my own website?",
		"No. Your It's Your Profile page works as your business page even if you have no website. If you do have one, "
		"add the link and we read it to add a short summary of your business, your services and your social links.",
	),
	(
		"Why is a LinkedIn link on every page?",
		"LinkedIn helps customers and AI assistants confirm that your business is real. If your card has no LinkedIn "
		"link, we look for it on your company website and then search the web. You can always add or change it yourself.",
	),
	(
		"Can I edit my page later?",
		"Yes. Log in and open My information to change any detail, such as your phone number, services, address or "
		"links. Your page updates as soon as you save.",
	),
	(
		"Can I see who visits my page?",
		"Yes. Your dashboard shows how many people viewed your page, who tapped Call or WhatsApp, where visitors came "
		"from, and when AI assistants and search engines read your page.",
	),
	(
		"Who is It's Your Profile for?",
		"Any business in India with a visiting card: chartered accountants, doctors and clinics, lawyers, consultants, "
		"interior designers, manufacturers, traders and distributors, shops and showrooms, freelancers and BNI members.",
	),
	(
		"Who made It's Your Profile?",
		"It's Your Profile is developed by SoftWorld Solutions Pvt. Ltd., a software company in India (softworld.co.in).",
	),
)


def user_badge(user):
	"""The logged-in owner's logo for the header (2026-11-07): their latest business logo, else their
	profile photo, else their initials. None for visitors."""
	if user == "Guest":
		return None
	biz = frappe.db.get_value(
		"Business Profile", {"owner": user}, ["company_name", "company_logo"], as_dict=True, order_by="creation desc"
	) or frappe._dict()
	person = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True) or frappe._dict()
	logo = next((u for u in (biz.company_logo, person.user_image) if (u or "").startswith(("/files/", "/private/files/"))), None)
	name = biz.company_name or person.full_name or user
	words = [w for w in name.split() if w[:1].isalnum()][:2]
	return frappe._dict(logo=logo, name=name, initials="".join(w[0] for w in words).upper() or "?")


def get_context(context):
	faqs = [{"q": frappe._(q), "a": frappe._(a)} for q, a in FAQS]
	context.faqs = faqs
	context.faq_schema = {
		"@context": "https://schema.org",
		"@type": "FAQPage",
		"mainEntity": [
			{"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faqs
		],
	}
	context.update(
		{
			"title": "It's Your Profile · Get found by AI",
			"description": "Turn your visiting card into a business page that ChatGPT, Gemini and Claude can find and recommend. Free, ready in a minute.",
			"audiences": AUDIENCES,
			"create_url": CREATE_URL,
			"logged_in": frappe.session.user != "Guest",
			"me": user_badge(frappe.session.user),
			# Preview image and address for shares and search engines (2026-11-12)
			"share_image": frappe.utils.get_url("/assets/its_your_profile/images/iyp-logo.png"),
			"home_url": frappe.utils.get_url("/"),
			"total": frappe.db.count("Business Profile", {"published": 1, "route": ("is", "set")}),
			# The directory is backend-only (2026-11-06): its links show only to staff
			"is_backend_user": is_backend_user(),
		}
	)
