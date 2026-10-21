import frappe
from frappe import _

ALLOWED_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")


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
