"""Refer & earn (2026-11-20).

Every business owner gets a referral code and link, e.g. itsyourprofile.com/?ref=SHRUTI7K
(Referral Code). Someone who opens the link keeps the code for 30 days (cookie set by
iyp_footer.js); it is also typed or pre-filled in the sign-up form. When they sign up, a Referral
row records who brought them ("Signed Up"). It counts for the referrer only once they make their
business page ("Page Created"), so fake sign-ups earn nothing.

12 businesses → 6 more months free, given once, automatically (REFERRALS_FOR_REWARD).
Everyone's free period is 6 months from sign-up (FREE_MONTHS); no payment is taken yet.
"""

import re
import secrets

import frappe
from frappe import _
from frappe.utils import add_months, escape_html, getdate, now_datetime, today

FREE_MONTHS = 6
REFERRALS_FOR_REWARD = 12
REWARD_MONTHS = 6
CODE_COOKIE = "iyp_ref"
CODE_EXTRA = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # no 0/O, 1/I/L mix-ups


def clean_code(code: str | None) -> str:
	return re.sub(r"[^A-Z0-9]", "", (code or "").upper())[:20]


def code_for(user: str, create: bool = True) -> str | None:
	"""The owner's referral code, made the first time it's needed: their first name + 2 characters."""
	code = frappe.db.get_value("Referral Code", {"user": user}, "name")
	if code or not create:
		return code
	first = frappe.db.get_value("User", user, "first_name") or user.split("@")[0]
	stem = re.sub(r"[^A-Z]", "", first.upper())[:6] or "IYP"
	for _try in range(20):
		code = stem + "".join(secrets.choice(CODE_EXTRA) for _i in range(2))
		if not frappe.db.exists("Referral Code", code):
			break
	frappe.get_doc({"doctype": "Referral Code", "code": code, "user": user}).insert(ignore_permissions=True)
	# Made while the dashboard (a GET request, which Frappe rolls back) is being shown
	frappe.db.commit()
	return code


def check_typed_code(doc, method=None):
	"""User before_insert: a referral code typed in the sign-up form must exist (a link's cookie
	that is wrong is just ignored in record_signup)."""
	from its_your_profile.signup_guard import is_signup_request

	if not is_signup_request():
		return
	code = clean_code((getattr(frappe.local, "form_dict", None) or {}).get("iyp_ref"))
	if code and not frappe.db.exists("Referral Code", code):
		frappe.throw(
			_("Referral code {0} was not found. Please check it, or leave the box empty.").format(code),
			title=_("Referral code"),
		)


def record_signup(doc, method=None):
	"""User after_insert: a sign-up that came with a referral code (form field or the link's cookie)."""
	try:
		from its_your_profile.signup_guard import is_signup_request

		if not is_signup_request():
			return  # users added by staff are nobody's referral
		form = getattr(frappe.local, "form_dict", None) or {}
		cookie = frappe.request.cookies.get(CODE_COOKIE) if getattr(frappe, "request", None) else None
		code = clean_code(form.get("iyp_ref") or cookie)
		if not code:
			return
		referrer = frappe.db.get_value("Referral Code", code, "user")
		if not referrer or referrer == doc.name or frappe.db.exists("Referral", {"new_user": doc.name}):
			return
		frappe.get_doc(
			{
				"doctype": "Referral",
				"referrer": referrer,
				"referral_code": code,
				"new_user": doc.name,
				"status": "Signed Up",
			}
		).insert(ignore_permissions=True)
	except Exception:
		# Never stop a sign-up because of the referral
		frappe.log_error("Referral: could not record the sign-up")


def count_page(doc, method=None):
	"""Business Profile after_insert: the referred person made their page, so it counts now."""
	try:
		referral = frappe.db.get_value(
			"Referral", {"new_user": doc.owner, "status": "Signed Up"}, ["name", "referral_code"], as_dict=True
		)
		if not referral:
			return
		frappe.db.set_value(
			"Referral",
			referral.name,
			{"status": "Page Created", "business_profile": doc.name, "counted_on": now_datetime()},
		)
		update_referrer(referral.referral_code)
	except Exception:
		frappe.log_error("Referral: could not count the new page")


def update_referrer(code: str):
	"""Count the referrer's businesses; at 12, give 6 more months free once and tell them."""
	joined = frappe.db.count("Referral", {"referral_code": code, "status": "Page Created"})
	card = frappe.get_doc("Referral Code", code)
	card.businesses_joined = joined
	earned = joined >= REFERRALS_FOR_REWARD and not card.reward_given
	if earned:
		card.reward_given = 1
		card.reward_given_on = today()
	card.save(ignore_permissions=True)
	if earned:
		tell_reward(card.user)


def tell_reward(user: str):
	until = frappe.utils.format_date(free_until(user))
	message = _("🎉 12 businesses joined with your link. You get 6 more months free, until {0}!").format(until)
	frappe.get_doc(
		{"doctype": "Notification Log", "for_user": user, "type": "Alert", "subject": escape_html(message)}
	).insert(ignore_permissions=True)
	try:
		frappe.sendmail(
			recipients=[user],
			subject=_("You've earned 6 months free on It's Your Profile"),
			message=f"<p>{escape_html(message)}</p><p>{_('Thank you for sharing It’s Your Profile.')}</p>",
		)
	except Exception:
		frappe.log_error("Referral: could not email the reward")


def free_until(user: str):
	"""Last day of the free period: 6 months from sign-up, +6 when the referral reward was given."""
	joined = frappe.db.get_value("User", user, "creation")
	months = FREE_MONTHS + (REWARD_MONTHS if frappe.db.get_value("Referral Code", {"user": user}, "reward_given") else 0)
	return add_months(getdate(joined), months)


def dashboard(user: str) -> dict:
	"""The owner's "Refer & earn" card on /notifications."""
	code = code_for(user)
	joined = frappe.db.count("Referral", {"referral_code": code, "status": "Page Created"})
	waiting = frappe.db.count("Referral", {"referral_code": code, "status": "Signed Up"})
	rewarded = bool(frappe.db.get_value("Referral Code", code, "reward_given"))
	shown = min(joined, REFERRALS_FOR_REWARD)
	link = frappe.utils.get_url(f"/?ref={code}")
	return frappe._dict(
		code=code,
		link=link,
		joined=joined,
		waiting=waiting,
		goal=REFERRALS_FOR_REWARD,
		left=max(REFERRALS_FOR_REWARD - joined, 0),
		percent=round(shown * 100 / REFERRALS_FOR_REWARD),
		rewarded=rewarded,
		free_until=frappe.utils.format_date(free_until(user)),
		share_text=_(
			"I made my business page on It's Your Profile, so Google and AI assistants can find us. "
			"Make yours free for 6 months: {0}"
		).format(link),
	)


def staff_list(limit: int = 20) -> list:
	"""Top referrers for the staff dashboard."""
	rows = frappe.get_all(
		"Referral Code",
		filters={"businesses_joined": (">", 0)},
		fields=["code", "user", "businesses_joined", "reward_given"],
		order_by="businesses_joined desc",
		limit_page_length=limit,
	)
	for row in rows:
		row.full_name = frappe.utils.get_fullname(row.user)
	return rows
