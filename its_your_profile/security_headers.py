"""Security headers on every response (2026-11-12), from a site audit.

The web server in front of Frappe (nginx, set up by bench and by Frappe Cloud) already sends
X-Content-Type-Options, Referrer-Policy, X-Frame-Options and Strict-Transport-Security. Sending them
here too made every response carry them twice (with two different Referrer-Policy values), so this
hook only adds what nginx does not send:

- Content-Security-Policy, the safe part only: no embedding of our pages in other sites (clickjacking),
  no plugins, no <base> tricks. A full policy (which scripts may run) would break Frappe's inline
  scripts and the font / QR libraries, so it is not set here.
"""

CSP = "frame-ancestors 'self'; object-src 'none'; base-uri 'self'"


def add_security_headers(response=None, request=None):
	"""after_request hook."""
	if response is None:
		return
	if "Content-Security-Policy" not in response.headers:
		response.headers["Content-Security-Policy"] = CSP
