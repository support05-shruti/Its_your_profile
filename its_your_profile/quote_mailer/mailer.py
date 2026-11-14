"""Quote Mailer: emails one NEW Indian business quote every 2 minutes.

Each run asks the app's AI (OpenAI or Gemini, same keys as ai.py) to write a fresh, original quote
in the style of the indian-quotes-api project (github.com/Aniket-508/indian-quotes-api).
The AI writes its own quotes and the email says so; it is never asked to put words in a real
person's mouth, because AI tends to invent "famous quotes" nobody said.

No repeats: every sent quote is saved in sites/<site>/private/quote_mailer_sent.json, and a new
quote that matches an old one is thrown away and written again.
If the AI is down, it falls back to the 107 real quotes in quotes.json, each used only once.

The email layout copies the /random page (components/randomquote.tsx) with inline styles,
because email apps ignore CSS classes.

Off by default, so a deploy to the live site sends nothing. Switch on per site with:
	bench --site site1.local set-config quote_mailer_enabled 1
"""

import json
import os
import random
import re
from functools import lru_cache

import frappe
from frappe.utils import escape_html
from pydantic import BaseModel, Field

from its_your_profile import ai

RECIPIENT = "support05@softworld.co.in"
QUOTES_FILE = os.path.join(os.path.dirname(__file__), "quotes.json")
AI_TRIES = 3  # attempts to get a quote that was never sent before
RECENT_IN_PROMPT = 40  # last N quotes shown to the AI so it steers away from them

# A different theme each time keeps the AI from writing the same kind of quote again and again
TOPICS = [
	"starting up with very little money", "jugaad and frugal innovation", "hiring the first team",
	"selling to the first customers", "failure and starting again", "patience and long-term thinking",
	"family business and the next generation", "building for Bharat and small towns",
	"customer trust", "leadership", "taking risks", "discipline and daily habits",
	"competition", "raising money", "building a brand", "working with a co-founder",
	"learning from mistakes", "serving customers in India", "growing a small shop into a company",
	"saying no", "speed versus quality", "humility after success", "manufacturing in India",
	"women entrepreneurs", "first-generation founders", "pricing and profit", "ethics in business",
	"technology for everyone", "resilience in tough times", "dreaming big from a small place",
]

logger = frappe.logger("its_your_profile", allow_site=True)

# Tailwind colours used by the /random page
INDIGO_600 = "#4f46e5"
INDIGO_100 = "#e0e7ff"
INDIGO_800 = "#3730a3"
GRAY_900 = "#111827"
GRAY_600 = "#4b5563"


class NewQuote(BaseModel):
	quote: str = Field(description="One original quote, 8 to 30 words, no quotation marks")
	tags: list[str] = Field(description="1 to 3 short lowercase theme tags, e.g. 'hiring', 'sales'")


# ---------------------------------------------------------------- memory of sent quotes


def _sent_file() -> str:
	return frappe.get_site_path("private", "quote_mailer_sent.json")


def _load_sent() -> list[str]:
	try:
		with open(_sent_file(), encoding="utf-8") as f:
			return json.load(f)
	except (FileNotFoundError, ValueError):
		return []


def _save_sent(sent: list[str]):
	os.makedirs(os.path.dirname(_sent_file()), exist_ok=True)
	with open(_sent_file(), "w", encoding="utf-8") as f:
		json.dump(sent, f, ensure_ascii=False, indent=0)


def _key(text: str) -> str:
	"""'Hire slowly, fire fast!' and 'hire slowly fire fast' count as the same quote."""
	return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


# ---------------------------------------------------------------- getting a quote


def _ask_ai(topic: str, recent: list[str]) -> NewQuote:
	avoid = "\n".join(f"- {q}" for q in recent[-RECENT_IN_PROMPT:]) or "- (none yet)"
	prompt = (
		"Write ONE new, original, short motivational quote for Indian entrepreneurs and business owners.\n"
		f"Theme: {topic}.\n"
		"Style: simple English, practical, memorable, rooted in Indian business life; "
		"like quotes by Indian founders such as Kunal Shah or Sachin Bansal, but your own words.\n"
		"Do not copy or paraphrase any existing famous quote. Do not mention any real person.\n"
		f"It must be clearly different from these quotes already sent:\n{avoid}"
	)
	if ai._use_openai():
		return ai._openai_generate(prompt, NewQuote)
	return ai._generate(prompt, NewQuote)


def _ai_quote(sent_keys: set[str], sent: list[str]) -> dict | None:
	for _ in range(AI_TRIES):
		try:
			new = _ask_ai(random.choice(TOPICS), sent)
		except Exception:
			logger.exception("Quote Mailer: AI quote failed")
			return None
		text = new.quote.strip().strip('"“”').strip()
		if text and _key(text) not in sent_keys:
			return {"quote": text, "author": "", "company": "", "tags": new.tags[:3], "ai": True}
	return None


@lru_cache(maxsize=1)
def load_quotes() -> list[dict]:
	with open(QUOTES_FILE, encoding="utf-8") as f:
		return json.load(f)


def _backup_quote(sent_keys: set[str]) -> dict | None:
	"""A real quote from quotes.json that was never sent; None once all 107 are used."""
	unused = [q for q in load_quotes() if _key(q["quote"]) not in sent_keys]
	return random.choice(unused) if unused else None


def get_new_quote() -> dict | None:
	sent = _load_sent()
	sent_keys = {_key(q) for q in sent}
	return _ai_quote(sent_keys, sent) or _backup_quote(sent_keys)


# ---------------------------------------------------------------- email


def render_quote(q: dict) -> str:
	badges = "".join(
		f'<span style="display:inline-block;margin:0 0 6px 6px;padding:2px 10px;border-radius:9999px;'
		f'background:{INDIGO_100};color:{INDIGO_800};font-size:12px;font-weight:600;">'
		f"{escape_html(tag)}</span>"
		for tag in q.get("tags", [])
	)
	if q.get("ai"):
		byline = f'<p style="margin:0;font-size:17px;font-weight:500;color:{INDIGO_600};">Fresh quote</p>'
		byline += f'<p style="margin:2px 0 0;color:{GRAY_600};font-size:15px;">written by AI for It&#39;s Your Profile</p>'
	else:
		byline = f'<p style="margin:0;font-size:17px;font-weight:500;color:{INDIGO_600};">{escape_html(q["author"])}</p>'
		if q.get("company"):
			byline += (
				f'<p style="margin:2px 0 0;color:{GRAY_600};font-size:15px;">at '
				f'<span style="color:{GRAY_900};">{escape_html(q["company"])}</span></p>'
			)

	return f"""
<div style="background:#ffffff;padding:32px 16px;font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;">
 <div style="max-width:640px;margin:0 auto;">
  <div style="text-align:center;margin-bottom:32px;">
   <h1 style="margin:0 0 12px;font-size:30px;font-weight:700;color:{GRAY_900};">Words of Wisdom</h1>
   <p style="margin:0;font-size:17px;color:{GRAY_600};">Get inspired with wisdom for India&#39;s entrepreneurs</p>
  </div>

  <!-- Gradient glow around the card, like the page's indigo → purple → pink blur -->
  <div style="padding:4px;border-radius:14px;
    background:#d9c9f7;background-image:linear-gradient(90deg,#c7c4f8,#e3c4f9,#f8c4de);">
   <div style="background:#ffffff;border-radius:12px;padding:32px;">
    <div style="font-family:Georgia,serif;font-size:56px;line-height:40px;height:36px;color:{INDIGO_600};margin-bottom:20px;">&ldquo;</div>
    <blockquote style="margin:0 0 24px;font-size:22px;line-height:1.6;color:{GRAY_900};">
     &quot;{escape_html(q["quote"])}&quot;
    </blockquote>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
     <td style="vertical-align:top;">{byline}</td>
     <td style="vertical-align:top;text-align:right;">{badges}</td>
    </tr></table>
   </div>
  </div>
 </div>
</div>
"""


def send_random_quote():
	"""Scheduler job (cron */2 in hooks.py). Also callable from the console for a test send."""
	if not frappe.conf.get("quote_mailer_enabled"):
		return

	q = get_new_quote()
	if not q:
		logger.error("Quote Mailer: AI unavailable and all backup quotes already sent; nothing sent")
		return

	frappe.sendmail(
		recipients=[RECIPIENT],
		subject="Words of Wisdom: " + ("a fresh one for you" if q.get("ai") else q["author"]),
		message=render_quote(q),
		# Send right away: the email queue is only flushed every few minutes, too slow for */2
		now=True,
	)

	sent = _load_sent()
	sent.append(q["quote"])
	_save_sent(sent)
