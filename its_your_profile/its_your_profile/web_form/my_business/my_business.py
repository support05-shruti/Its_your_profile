def get_context(context):
	# Frappe titles the blank form "New My Business Profile"; keep just the form's own title.
	# (Runs after Frappe sets that title, so this replaces it.) Changed 2026-11-06.
	if context.get("is_new"):
		context.title = context.web_form_doc.get("title") or context.title
