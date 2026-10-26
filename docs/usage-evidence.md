# Usage and client evidence labels

This is the contribution contract for client labels and any future opt-in usage reporting. It does not claim that a reporting service, installation bridge or community-rating backend is already implemented. Check the deployed source before describing a feature as available.

## Report the event that was actually observed

| Event or display | Evidence needed | What it does not establish |
| --- | --- | --- |
| Queued | A preserved pending request with its selected source versions | Network transfer started |
| Transferring | An active response stream | A file was saved or installed |
| Bytes received | Measured bytes from that response; a known total for a percentage | Installation, reading or a task outcome |
| Browser download requested | The client handed the completed payload to the browser's download action | Disk-save completion; the user may cancel it |
| Installed locally | Explicit local helper/CLI inventory or user-selected folder inspection, with the observed source/hash | The agent discovered or read it |
| Read observed | A successful retained tool output that matches the selected full skill body | Internal influence on the model |
| Pair completed | Both intended arm records and artifact grades, linked to the sealed protocol | Either condition is generally better |
| Outcome | Versioned task/check result for the exact source/model/run | General quality, usefulness or user preference |
| Human preference | Saved blind choice and its scope; reveal only afterward | A verified identity, broad consensus or a rating for other versions |

Browser code cannot silently scan installed skills on a local filesystem. A chosen file, folder, ZIP or report exposes only what the person selected. A local helper requires an explicit supported connection and read scope; the public site must not imply that it has inspected the rest of the machine. A self-reported installation must be labeled self-reported.

Progress must describe received bytes for the active transfer. When total length is unknown, show an indeterminate state and a byte count rather than a fake percentage. Preserve queued requests or explicitly cancel them. A new request must not silently turn an older transfer into a completed one. Show the source name, state and retryable error; a retry uses the pinned source and is a new transfer attempt. Do not convert server failure, a canceled stream or a browser save prompt into a completed installation.

## Minimal opt-in reporting

The default contribution must work without external analytics. Do not add paid analytics infrastructure for these labels. Local state or an explicit user-controlled export can provide evidence without sending it to a server.

If usage reporting is added, make it off by default with a visible purpose, recipient, retention rule and revoke control. Consent to download is not consent to report installation, skill reads, task outcomes or ratings. Revoke stops future events and clears the local reporting queue. A local-only control must not imply that it deleted records already sent elsewhere.

Use only the fields needed for the stated count: event type, public catalog ID, exact public skill hash, application version and a coarse time when necessary. Keep event identifiers short-lived and local unless a reviewed deduplication design requires otherwise. Do not use stable machine fingerprints, local paths, account identifiers, private skill hashes, prompts, code, task text, generated artifacts or review reasons. Ordinary hosting HTTP metadata is separate from product event reporting; do not claim the whole network retains nothing.

Name the denominator and source of a displayed total: transfer attempts, received payloads, user-reported installs, observed local installs, observed reads, completed pairs or human ratings. They cannot all be called usage. Unknown is distinct from zero. Unrated entries have no community rating; repository stars remain labeled repository popularity. A local preference or unverified import cannot silently become a public star score.
