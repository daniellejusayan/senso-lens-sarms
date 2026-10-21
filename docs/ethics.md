# Ethics and data-handling note (Steps 1–2, 21 Oct 2026)

Course 1305394, project "Keeping Code Faithful to Its Architecture" (sarms). Mirrors Part 10 of
the proposal; this is the operational version the team follows.

## What we collect

- Public open-source repositories, used under their licences (criterion 7 admits only
  OSI-approved MIT / Apache-2.0 / BSD subjects; the exploratory PostHog case is MIT with a
  separate `ee/` licence and is used for detection statistics only, never for code drafts).
- Commit metadata (sha, timestamps, message, files touched), import graphs, contract and ADR
  text, and — in Weeks 3–6 — pull-request and issue text as quarantined model input.

## Personal data

Commit author names and e-mail addresses are personal data. They never leave the clone:
`sarms.mining.first_parent` writes `author_hash` = SHA-256 of a team salt plus the lowercased
e-mail, truncated to 16 hex characters. The salt lives in `.salt` (git-ignored; `.salt.example`
is the committed placeholder) and is shared between members outside git. Without the salt the
hash cannot be reversed or matched across projects; with it, the same author gets the same
hash across our repositories, which is all the analysis needs. Names are not stored at all.
Commit messages and PR text may contain names; they are kept in `data/` (git-ignored) and
quoted in reports only with the name removed.

## Human study (post-hoc audit)

Participants (advisor, course staff, senior students, volunteer maintainers) are informed
that the corrections are research prototypes applied in a sandbox, give consent for
anonymised quotes, and are recorded by a code (A1…An). Ratings are stored in coded form in
`data/audit/` (git-ignored), summary statistics only in the paper. No compensation; sessions
of 30–40 minutes; a participant may stop at any time and their ratings are discarded.

## What the system may touch

This term the system commits only to replay working copies and to throwaway fault-injection
branches on our own clones (`sarms/fi-*`); it never pushes to a subject's repository. A Term 2
live pilot runs only on a repository whose maintainers agree in writing, on branches they
authorise, and never reverts a developer's push (rule 1). Repository authors are not
contacted without opting in.

## Retention

Clones and per-commit data (`data/raw`, `data/<repo>`) are deleted at the end of Term 2; the
pseudonymised dataset (ledger rows, labels) is released with the paper.
