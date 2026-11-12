# SkillWire voting design comparison, 31 October

Local design exploration only. No production code, API, account, schema, deployment or remote branch changed.

Run from this checkout:

    python3 -m http.server 18951 --bind 127.0.0.1 --directory design-previews/voting

Open http://127.0.0.1:18951/ and use the three-way picker.

- A: one toggleable star per skill, per anonymous browser.
- B: one toggleable up/down preference per skill, per anonymous browser.
- C: one recommendation total per UTC day; choosing another moves it, and tapping again removes it. Sorted by local recommendation count with catalog-order ties.

All count state starts empty and persists in localStorage only. No login and no network writes. These are working UI alternatives, not proof of deployed voting or anti-abuse protection. Clearing browser storage bypasses local identity. Production would need the approved server-side identity and rate limits; no such integration is included here.

Real skill names, source links and descriptions come from the public skillwire.net/catalog.json response captured on 31 October (timestamp in data.json). Descriptions are source claims, not independently verified. The four existing live daily votes are acknowledged separately, never relabelled as stars or up/down votes. Counts shown in screenshots were created by the local browser QA interaction.

The job: a stranger can read a skill's purpose and source, and express one clear preference without an account. Keep the existing LimeWire application language: blue title bar, beveled controls, yellow sidebar sections, zebra file rows and lime selected state. Divergence is in the preference model and list composition, not three palette changes.

Recommendation: A is the simplest familiar interaction and preserves a clean file list. B offers negative feedback but makes an unevaluated skill look judged. C best preserves the earlier one-total-vote-per-day constraint, at the cost of asking users to choose only one skill.
