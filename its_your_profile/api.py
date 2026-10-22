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

	mime_type = mimetypes.guess_type(file.file_name or file_url)[0] or "image/jpeg"
	details = ai.extract_card_details(file.get_content(), mime_type)
	frappe.cache.set_value(card_read_cache_key(file_url), 1, expires_in_sec=3600)

	return {
		fieldname: getattr(details, key).strip()
		for key, fieldname in CARD_FIELD_MAP.items()
		if getattr(details, key)
	}


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
