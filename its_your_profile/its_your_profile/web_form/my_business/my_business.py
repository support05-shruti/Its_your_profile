from its_your_profile.portal import redirect


def get_context(context):
	# CHANGE NOTE 2026-11-07: new pages are made on the home page (scan the card or paste the
	# website, the details fill in right there), so the blank form is never shown: /my-business/new
	# goes to the upload card. Editing an existing page (/my-business/<name>/edit) still uses the form.
	# Temporary (302) redirect, so browsers don't remember it.
	if context.get("is_new"):
		redirect("/#start")
