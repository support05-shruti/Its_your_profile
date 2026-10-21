"""Gemini helpers. Set the key with: bench --site <site> set-config gemini_api_key <key>"""

from typing import Literal

import frappe
from pydantic import BaseModel, Field

# gemini-2.5-flash (named in the SOP) is retired for new API users; the alias tracks the current Flash model
DEFAULT_MODEL = "gemini-flash-latest"


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


def _client():
	from google import genai
	from google.genai import types

	api_key = (frappe.conf.get("gemini_api_key") or "").strip()
	if not api_key:
		frappe.throw("gemini_api_key is not set in site_config.json")
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
			model=frappe.conf.get("gemini_model") or DEFAULT_MODEL,
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


def extract_card_details(image: bytes, mime_type: str) -> CardDetails:
	from google.genai import types

	return _generate([types.Part.from_bytes(data=image, mime_type=mime_type), CARD_PROMPT], CardDetails)


def analyse_website(text: str) -> WebsiteInsights:
	return _generate(WEBSITE_PROMPT.format(text=text), WebsiteInsights)
