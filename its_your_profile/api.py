import mimetypes

import frappe
from frappe import _

ALLOWED_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")


def card_read_cache_key(file_url: str) -> str:
	return f"its_your_profile:card_read:{file_url}"


@frappe.whitelist(methods=["POST"])
def read_visiting_card(file_url: str):
	"""Read a just-attached card and return field values, so the form fills in before Save.

	Marks the file as read so saving the profile doesn't queue a second, background scan.
	"""
	from its_your_profile import ai
	from its_your_profile.tasks import CARD_FIELD_MAP

	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to read a visiting card"), frappe.PermissionError)

	file = frappe.get_doc("File", {"file_url": file_url})
	if not frappe.has_permission("File", "read", doc=file):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	from its_your_profile.its_your_profile.doctype.business_profile.business_profile import (
		card_colours,
		clean_phone,
	)

	mime_type = mimetypes.guess_type(file.file_name or file_url)[0] or "image/jpeg"
	details = ai.extract_card_details(file.get_content(), mime_type)
	colours = card_colours(details)

	values = {
		fieldname: getattr(details, key).strip()
		for key, fieldname in CARD_FIELD_MAP.items()
		if getattr(details, key) and getattr(details, key).strip()
	}
	if values.get("phone"):
		values["phone"] = clean_phone(values["phone"])  # shown clean in the form before Save

	if values.get("email") and not values.get("website_url"):
		from its_your_profile.tasks import website_from_email

		# No website on the card: try the company domain of the email (the form then reads its links)
		if website := website_from_email(values["email"]):
			values["website_url"] = website

	if not values:
		# Not remembered as read, so Save still queues the background scan as a second try
		frappe.throw(
			_("Could not read any details from this photo. Please take a clearer, straight photo of the card in good light, or type the details."),
			title=_("Card not readable"),
		)

	# Remembered for the Save that follows: marks the card as read (no background scan) and
	# carries its colours, which the user form has no boxes for
	frappe.cache.set_value(card_read_cache_key(file_url), {"colours": colours}, expires_in_sec=3600)

	return {**values, **colours}


@frappe.whitelist(methods=["POST"])
def read_website_links(url: str):
	"""Fetch a website (homepage + contact page) and return its profile links, so the form's
	Profile Links table fills in before Save. No AI involved, so it answers in seconds."""
	from bs4 import BeautifulSoup

	from its_your_profile.its_your_profile.doctype.business_profile.business_profile import clean_url
	from its_your_profile.tasks import fetch, find_contact_page, find_map_url, social_links

	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in"), frappe.PermissionError)

	url = clean_url(url, _("Website URL"))
	try:
		pages = [fetch(url)]
		if contact_url := find_contact_page(pages[0], url):
			try:
				pages.append(fetch(contact_url))
			except Exception:
				pass  # the homepage alone is still useful
	except Exception:
		frappe.throw(_("Could not open {0}. Please check the website address.").format(url))

	soups = [BeautifulSoup(html, "html.parser") for html in pages]
	return {
		"links": [
			{"platform": platform, "label": label, "url": link} for platform, label, link in social_links(soups)
		],
		"map_url": find_map_url(soups),
	}


@frappe.whitelist(methods=["POST"])
def send_welcome_email(name: str):
	"""Desk button: send (or resend) the welcome email for one business."""
	doc = frappe.get_doc("Business Profile", name)
	doc.check_permission("write")
	doc.send_welcome_email()
	return {"sent_to": doc.email}


@frappe.whitelist(methods=["POST"])
def rotate_visiting_card(name: str, fieldname: str, direction: str):
	"""Desk button: turn a card photo a quarter left or right. Saved as a new file, so the
	browser shows the new image at once instead of a cached copy of the old one."""
	import io

	from PIL import Image, ImageOps

	if fieldname not in ("visiting_card", "visiting_card_back"):
		frappe.throw(_("Not a visiting card field"))

	doc = frappe.get_doc("Business Profile", name)
	doc.check_permission("write")
	old_url = doc.get(fieldname)
	if not old_url:
		frappe.throw(_("No photo to rotate"))
	old_file = frappe.get_doc("File", {"file_url": old_url})

	# Apply the phone's EXIF orientation first, so we turn the photo as it looks on screen
	image = Image.open(io.BytesIO(old_file.get_content()))
	image_format = image.format if image.format in ("JPEG", "PNG", "WEBP") else "JPEG"
	image = ImageOps.exif_transpose(image).rotate(90 if direction == "left" else -90, expand=True)
	if image_format == "JPEG" and image.mode not in ("RGB", "L"):
		image = image.convert("RGB")
	buffer = io.BytesIO()
	image.save(buffer, format=image_format, quality=95)

	new_file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": old_file.file_name,
			"attached_to_doctype": "Business Profile",
			"attached_to_name": name,
			"attached_to_field": fieldname,
			"is_private": old_file.is_private,
			"content": buffer.getvalue(),
		}
	).insert(ignore_permissions=True)

	doc.db_set(fieldname, new_file.file_url)
	try:
		frappe.delete_doc("File", old_file.name, ignore_permissions=True)
	except Exception:
		pass  # an old photo left behind is harmless; the profile already points at the new one
	return {"file_url": new_file.file_url}


@frappe.whitelist(methods=["POST"])
def refresh_ai_summary(name: str):
	"""Desk button: read the website (or search Google) again and rewrite the AI Summary."""
	from its_your_profile.tasks import scrape_website

	frappe.get_doc("Business Profile", name).check_permission("write")
	scrape_website(name)
	return {"ai_summary": frappe.db.get_value("Business Profile", name, "ai_summary")}


@frappe.whitelist(methods=["POST"])
def upload_visiting_card():
	"""Create a Business Profile from an uploaded card photo (multipart field `file`).

	The scan itself runs in the background; poll `get_scan_status` with the returned name.
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to upload a visiting card"), frappe.PermissionError)

	upload = frappe.request.files.get("file")
	if not upload:
		frappe.throw(_("No file uploaded"))
	if upload.mimetype not in ALLOWED_IMAGE_TYPES:
		frappe.throw(_("Please upload a JPG, PNG, WEBP or HEIC image"))

	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": upload.filename,
			"content": upload.stream.read(),
			"is_private": 0,
		}
	).insert(ignore_permissions=True)

	# Inserting with the card set queues the scan (see BusinessProfile.on_update)
	profile = frappe.get_doc({"doctype": "Business Profile", "visiting_card": file.file_url})
	profile.insert(ignore_permissions=True)

	file.db_set(
		{
			"attached_to_doctype": "Business Profile",
			"attached_to_name": profile.name,
			"attached_to_field": "visiting_card",
		}
	)

	return {"name": profile.name, "card_scan_status": profile.card_scan_status}


@frappe.whitelist()
def get_scan_status(name: str):
	owner, status = frappe.db.get_value("Business Profile", name, ["owner", "card_scan_status"]) or (None, None)
	if not owner:
		frappe.throw(_("Business Profile not found"), frappe.DoesNotExistError)
	if owner != frappe.session.user and not frappe.has_permission("Business Profile", "read", name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return status
