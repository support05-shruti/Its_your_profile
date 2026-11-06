# Changelog

## 2026-11-05 — Monthly WhatsApp report, pre-filled WhatsApp text, first-source memory

- **Summary:**
  - New `its_your_profile/monthly_report.py`: on the 1st of each month at 10:00, adds up last month's
    `Profile Visit` rows per business (AI crawler reads, visitors from AI apps, page views, WhatsApp
    taps, calls, contact saves) and sends each business one WhatsApp template message through the
    WhatsApp Cloud API. Off by default.
  - `Its Your Profile Settings`: new "Monthly WhatsApp Report" section (on/off, Phone Number ID,
    access token, template name and language, Graph API version).
  - `hooks.py`: `scheduler_events` cron entry for the report.
  - Business profile page: WhatsApp buttons open with "Hi, I found you on itsyourprofile.com"
    pre-filled; the visit/tap script remembers the visitor's first source for the browser tab, so
    later taps and reloads are still credited to e.g. ChatGPT.
- **Reason:** Owners get a monthly summary of what the page did for them, and know in the chat itself
  where a WhatsApp lead came from. Built on the existing `tracking.py` / `Profile Visit` log rather
  than a second "Profile Event" log, so there is one set of numbers.
- **Files or modules affected:** `its_your_profile/monthly_report.py` (new), `its_your_profile/hooks.py`,
  `its_your_profile/its_your_profile/doctype/its_your_profile_settings/its_your_profile_settings.json`,
  `its_your_profile/its_your_profile/doctype/business_profile/templates/business_profile.html`.
- **Testing:** Local only (no bench access from the editing machine): Python compiled; settings JSON
  parsed; the template's new Jinja and script parsed. Not run: `bench migrate`, the scheduler job,
  a real WhatsApp send, the profile page in a browser.
- **Pending items:** Submit and get Meta approval for the `monthly_profile_report` Utility template
  (9 body variables, see the Template Name field help); fill in the settings and tick the switch.
  The unused `Profile Event` doctype (created 2026-11-05, not committed) can be deleted. Add a line
  about anonymous visit analytics to the privacy policy (check India's DPDP Act).

## 2026-11-05 — Dark theme toggle on the home page

- **Summary:** Added a light/dark theme toggle button (moon/sun) to the home page header (`/`). The page
  starts in the visitor's saved choice, or their system setting if they have not chosen; the choice is
  remembered in the browser. Dark palette added; the visiting card, phone and AI chat-bubble
  illustrations stay light on purpose.
- **Reason:** Requested dark theme option for the public web page.
- **Files or modules affected:** `its_your_profile/www/home.html`, `its_your_profile/www/home.css`,
  `its_your_profile/www/home.js`.
- **Testing:** `node --check` on `home.js` and the new inline head script passed; CSS braces balanced.
  Template rendered locally with Jinja2 (stub context, without Frappe's base template or website CSS)
  and screenshotted in headless Edge in light and dark at desktop width: both looked correct.
  Not tested: on the real site with Frappe's styles, the toggle click in a real browser, true phone
  widths (headless Edge would not render below ~500px), and other pages.
- **Pending items:** Only the home page has the theme; `/directory`, `/notifications` and business
  profile pages are unchanged. Run `bench clear-cache` (or `bench --site <site> clear-website-cache`)
  after applying, then check `/` in a browser.
