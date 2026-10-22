"""AI helpers for card reading and website summaries.

Uses OpenAI when `openai_api_key` is set in site_config.json, otherwise Gemini (`gemini_api_key`).
Any OpenAI-compatible service works too: set `openai_base_url` and `openai_model` alongside the key.
"""

import base64
import json
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


class WebsiteInsights(BaseModel):
	ai_summary: str = Field(description="Exactly three plain-text sentences describing what the business does")
	business_nature: Literal["Service", "Manufacturing", "Hybrid/Trading"]
	linkedin_url: str | None = None
	facebook_url: str | None = None
	established_year: int | None = None


CARD_PROMPT = """You are reading a business visiting card.
Extract the details printed on the card. Use null for anything that is not clearly printed.
Do not guess or invent values."""

WEBSITE_PROMPT = """Below is text scraped from a company's website.
1. Write a factual three-sentence summary of what the business does, who it serves and where.
2. Classify it as Service, Manufacturing, or Hybrid/Trading.
3. Return the LinkedIn and Facebook page URLs if they appear in the text, otherwise null.
4. Return the year the company was established if stated, otherwise null.

Website text:
{text}"""


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


def analyse_website(text: str) -> WebsiteInsights:
	if _use_openai():
		return _openai_generate(WEBSITE_PROMPT.format(text=text), WebsiteInsights)
	return _generate(WEBSITE_PROMPT.format(text=text), WebsiteInsights)
