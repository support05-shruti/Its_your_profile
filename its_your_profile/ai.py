"""AI helpers for card reading and website summaries.

Uses OpenAI when `openai_api_key` is set in site_config.json, otherwise Gemini (`gemini_api_key`).
Any OpenAI-compatible service works too: set `openai_base_url` and `openai_model` alongside the key.
"""

import base64
import json
import re
import time
from typing import Literal

import frappe
import requests
from pydantic import BaseModel, Field

# gemini-2.5-flash (named in the SOP) is retired for new API users; the alias tracks the current Flash model
DEFAULT_MODEL = "gemini-flash-latest"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


class CardDetails(BaseModel):
	company_name: str | None = Field(None, description="Company or business name")
	contact_person: str | None = Field(None, description="Full name of the person on the card")
	designation: str | None = Field(None, description="Job title of the person")
	phone: str | None = Field(None, description="Primary phone number, with country code if printed")
	email: str | None = None
	website: str | None = None
	address_line: str | None = Field(None, description="Street address, without city, state or pincode")
	city: str | None = None
	state: str | None = None
	pincode: str | None = None
	name_color: str | None = Field(
		None, description="Hex colour of the company name text as printed on the card, e.g. #E8711A"
	)
	brand_color: str | None = Field(
		None,
		description="Hex colour of the main logo or accent colour on the card, e.g. #1F5F8B. "
		"Not white or the plain background colour.",
	)
	social_links: list[str] = Field(
		default_factory=list,
		description="Social media and online profile addresses printed on the card, as full URLs",
	)
	logo_box: list[float] = Field(
		default_factory=list,
		description="Box around the complete company logo (symbol, styled name and tagline) as "
		"[ymin, xmin, ymax, xmax], each 0-1000 of the image "
		"height or width. Empty if the card has no logo.",
	)


class WebsiteInsights(BaseModel):
	ai_summary: str | None = Field(
		None, description="Exactly three plain-text third-person sentences describing what the business does"
	)
	services: list[str] = Field(
		default_factory=list, description="Main products and services, each a short noun phrase"
	)
	business_nature: Literal["Service", "Manufacturing", "Hybrid/Trading"] | None = None
	linkedin_url: str | None = None
	facebook_url: str | None = None
	established_year: int | None = None


class FAQItem(BaseModel):
	question: str
	answer: str


class FAQs(BaseModel):
	faqs: list[FAQItem] = Field(default_factory=list, description="4 to 6 questions with their answers")


class LinkedInMatch(BaseModel):
	person_url: str | None = None
	company_url: str | None = None


CARD_PROMPT = """You are reading a business visiting card.
Extract the details printed on the card. Use null for anything that is not clearly printed.
Do not guess or invent values.
Also give the colours as hex codes: the colour of the company name text, and the main brand or
logo colour. Use null for a colour if the card is black and white.
List in social_links every social media or online profile address printed on the card (LinkedIn,
Facebook, Instagram, YouTube, X/Twitter, WhatsApp, IndiaMART, Justdial...) as a full URL, e.g.
"instagram.com/acmetools" → "https://instagram.com/acmetools". A bare handle like "@acmetools"
counts only when the platform's icon or name is printed right next to it. Do not include the
company website or email here. Use an empty list if there are none.
Give logo_box: a box around the complete company logo, as it would be cut out of the card to use
as the company's logo. Include everything that is designed as part of the logo: the symbol or
emblem, the company name written in the logo's style beside or under it, and a tagline printed
as part of it. Leave out the person's name, contact details and address. Make sure the whole
logo is inside the box. Use an empty list if there is no logo."""

# The summary is written for AI search engines, which quote clear factual definitions over marketing copy
WEBSITE_PROMPT = """Below is text scraped from the website of {company}.
1. Write a factual three-sentence summary of what the business does, who it serves and where.
   Write in the third person as plain statements that start with the company name, e.g.
   "Acme Tools is a manufacturer of hand tools based in Rajkot, Gujarat." No marketing language,
   superlatives, slogans, "we"/"our" or calls to action.
   If the text does not make clear what the business does, use null. Never write about the text
   itself or say that information is missing.
2. Classify it as Service, Manufacturing, or Hybrid/Trading (null if unclear).
3. Return the LinkedIn and Facebook page URLs if they appear in the text, otherwise null.
4. Return the year the company was established if stated, otherwise null.
5. List the main products and services it clearly offers (at most 10), each a short noun phrase
   such as "GST filing" or "HDPE pipes". Use an empty list if unclear.

Website text:
{text}"""

# FAQ answers become FAQPage data that Google and AI assistants quote word for word, so they may
# only restate the facts given: an invented price or claim would be repeated as true
FAQ_PROMPT = """Below are the facts about a business listed on It's Your Profile, a business directory.
Write 4 to 6 questions a potential customer would ask an AI assistant about this business, each
with a short answer (one or two sentences).
- Use ONLY the facts below. Never add prices, years, awards, clients, timings or claims that are
  not in them. Skip a question rather than guess its answer.
- Name the business in each question, e.g. "What services does Acme Tools offer?", and answer in
  the third person, starting with the business name where it reads naturally.
- Cover what it does, where it is based or serves, its main products or services, and how to
  contact it (say "by phone, WhatsApp or email through its It's Your Profile page", without
  writing out the number or address).
- Plain factual statements only: no marketing language, superlatives, "we"/"our" or calls to action.

Facts:
{facts}"""

RESEARCH_PROMPT = """Search Google for this business and find out what it does:
Company: {company}
Website: {website}
City: {city}

Reply with only a JSON object with these keys:
- ai_summary: a factual three-sentence summary of what the business does, who it serves and where,
  in the third person as plain statements that start with the company name. No marketing language,
  superlatives or "we"/"our".
  null if you cannot find this business. Never mention your search or that information is missing.
- services: a list of the main products and services it clearly offers (at most 10), each a short
  noun phrase. An empty list if unclear.
- business_nature: "Service", "Manufacturing" or "Hybrid/Trading", or null
- linkedin_url, facebook_url: the company's own pages if found, otherwise null
- established_year: the year it was established as a number, otherwise null"""

LINKEDIN_PROMPT = """Search Google for the LinkedIn pages of this business contact:
Name: {person}
Job title: {designation}
Company: {company}
City: {city}
Website: {website}

1. person_url: this person's own LinkedIn profile (linkedin.com/in/...). Only give it if a search
   result shows a profile with the same name AND the same company, website or city. Otherwise null.
2. company_url: the company's LinkedIn page (linkedin.com/company/...), only if the name clearly
   matches. Otherwise null.
Copy URLs exactly from the search results; never build or guess one.
Reply with only a JSON object: {{"person_url": "..." or null, "company_url": "..." or null}}"""


def _setting(fieldname):
	"""Read from Its Your Profile Settings (set in the desk), falling back to site_config.json."""
	value = None
	try:
		settings = frappe.get_cached_doc("Its Your Profile Settings")
		if settings.meta.get_field(fieldname).fieldtype == "Password":
			value = settings.get_password(fieldname, raise_exception=False)
		else:
			value = settings.get(fieldname)
	except Exception:
		pass  # settings doctype not migrated yet
	return (value or frappe.conf.get(fieldname) or "").strip()


def _client():
	from google import genai
	from google.genai import types

	api_key = _setting("gemini_api_key")
	if not api_key:
		frappe.throw("Set the Gemini API Key in Its Your Profile Settings")
	# Gemini often answers 503 "high demand"; retry with backoff instead of failing the scan
	return genai.Client(
		api_key=api_key,
		http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=5)),
	)


def _generate(contents, schema):
	from google.genai import types

	# Keep the client in a variable: once garbage-collected it closes its HTTP connection,
	# and a bare _client().models... call loses it mid-request ("client has been closed")
	client = _client()
	try:
		response = client.models.generate_content(
			model=_setting("gemini_model") or DEFAULT_MODEL,
			contents=contents,
			config=types.GenerateContentConfig(
				response_mime_type="application/json",
				response_schema=schema,
				temperature=0,
			),
		)
	finally:
		client.close()
	return response.parsed or schema.model_validate_json(response.text)


def _openai_generate(prompt, schema, image=None, mime_type=None):
	api_key = _setting("openai_api_key")
	if not api_key:
		frappe.throw("Set the OpenAI API Key in Its Your Profile Settings")
	base_url = (_setting("openai_base_url") or DEFAULT_OPENAI_BASE_URL).rstrip("/")

	content = [
		{
			"type": "text",
			"text": f"{prompt}\n\nReply with only a JSON object matching this JSON Schema:\n"
			+ json.dumps(schema.model_json_schema()),
		}
	]
	if image:
		data_url = f"data:{mime_type};base64,{base64.b64encode(image).decode()}"
		content.append({"type": "image_url", "image_url": {"url": data_url}})

	body = {
		"model": _setting("openai_model") or DEFAULT_OPENAI_MODEL,
		"messages": [{"role": "user", "content": content}],
		"response_format": {"type": "json_object"},
	}

	# Retry rate limits and server overloads with backoff, like the Gemini client does
	for attempt in range(5):
		response = requests.post(
			f"{base_url}/chat/completions",
			headers={"Authorization": f"Bearer {api_key}"},
			json=body,
			timeout=180,
		)
		if response.status_code not in (429, 500, 502, 503, 504) or attempt == 4:
			break
		time.sleep(2**attempt)

	if not response.ok:
		raise Exception(f"AI request failed ({response.status_code}): {response.text[:500]}")
	return schema.model_validate_json(response.json()["choices"][0]["message"]["content"])


def _use_openai():
	try:
		provider = frappe.db.get_single_value("Its Your Profile Settings", "ai_provider")
	except Exception:
		provider = None  # settings doctype not migrated yet
	if provider:
		return provider == "OpenAI"
	return bool(_setting("openai_api_key"))


def extract_card_details(image: bytes, mime_type: str) -> CardDetails:
	if _use_openai():
		return _openai_generate(CARD_PROMPT, CardDetails, image=image, mime_type=mime_type)

	from google.genai import types

	return _generate([types.Part.from_bytes(data=image, mime_type=mime_type), CARD_PROMPT], CardDetails)


def analyse_website(text: str, company: str | None = None) -> WebsiteInsights:
	prompt = WEBSITE_PROMPT.format(text=text, company=company or "a company")
	if _use_openai():
		return _openai_generate(prompt, WebsiteInsights)
	return _generate(prompt, WebsiteInsights)


def write_faqs(facts: str) -> FAQs:
	prompt = FAQ_PROMPT.format(facts=facts)
	if _use_openai():
		return _openai_generate(prompt, FAQs)
	return _generate(prompt, FAQs)


def research_company(company=None, website=None, city=None) -> WebsiteInsights:
	"""For websites that give no usable text (built in the browser with JavaScript): ask Gemini with Google Search."""
	prompt = RESEARCH_PROMPT.format(company=company or "-", website=website or "-", city=city or "-")
	found = re.search(r"\{.*\}", _search(prompt), re.S)
	return WebsiteInsights.model_validate_json(found.group()) if found else WebsiteInsights()


def find_linkedin(person, designation=None, company=None, city=None, website=None) -> LinkedInMatch:
	prompt = LINKEDIN_PROMPT.format(
		person=person, designation=designation or "-", company=company or "-", city=city or "-", website=website or "-"
	)
	found = re.search(r"\{.*\}", _search(prompt), re.S)
	return LinkedInMatch.model_validate_json(found.group()) if found else LinkedInMatch()


def _search(prompt) -> str:
	"""Always Gemini, whatever the provider setting: it is the one with Google Search built in."""
	from google.genai import types

	client = _client()
	try:
		# No response_schema: older Gemini models refuse it together with the search tool
		response = client.models.generate_content(
			model=_setting("gemini_model") or DEFAULT_MODEL,
			contents=prompt,
			config=types.GenerateContentConfig(
				tools=[types.Tool(google_search=types.GoogleSearch())],
				temperature=0,
			),
		)
	finally:
		client.close()
	return response.text or ""
