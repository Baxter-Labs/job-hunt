# Legal Disclaimer

Job Hunt is a job-application assistance tool. Before you rely on it, please
read this.

## Provided "as is"

Job Hunt is provided "as is", without warranty of any kind, express or
implied, including but not limited to warranties of merchantability, fitness
for a particular purpose, and non-infringement. You use it at your own risk.

## Not legal, career, or immigration advice

Nothing Job Hunt outputs — a ranked job list, a work-authorisation
annotation, a tailored CV, a cover letter, an ATS score — is legal, career,
or immigration/visa advice. In particular:

- A `nl-ind-hsm` annotation of **"confirmed"** means the company name matched
  an entry in a locally cached copy of the Dutch IND recognised-sponsor
  register at the time the cache was last refreshed. It is a best-effort
  **register-name match**, not a legal determination of sponsorship
  eligibility, and it can be wrong (stale cache, name variants, entity
  changes, the register itself changing). Always verify a company's current
  sponsor status and your own eligibility directly with the IND or a
  qualified immigration professional before making any decision based on it.
- The `eu-blue-card` scheme does not check against any authoritative
  employer register at all — it flags every listing for your own manual
  salary/threshold review, precisely because Job Hunt cannot make that
  determination for you.
- No output from Job Hunt should be treated as confirmation that a specific
  employer will sponsor you, that a specific role qualifies under a specific
  scheme, or that you are eligible to work in a given jurisdiction.

## No guarantee of job outcomes

Job Hunt does not guarantee interviews, offers, or any other outcome. A
higher ATS match score does not guarantee a response from an employer or an
applicant-tracking system, and a lower score does not mean you should not
apply. Job Hunt is a tool to help you prepare and organise applications, not
a promise of results.

## The fabrication check reduces risk — it does not remove your responsibility

`/job-tailor`'s fabrication check is a deterministic, code-level comparison
of the generated CV against your own `cv_master.json` (contact info, every
`(company, title, dates)` triple, every listed skill). It substantially
reduces the risk of a generated document containing a claim you didn't
actually make — but it is a mechanical check, not proofreading, and it
cannot catch every possible issue (subtle rephrasing that shifts meaning,
context lost in reordering, an error that was already present in your own
master CV, etc.). You are responsible for reading every tailored CV and
cover letter in full and confirming every claim in it is accurate before you
submit it anywhere.

## Platform Terms of Service are yours to follow

You are responsible for complying with the Terms of Service of every job
platform, applicant-tracking system, or company career site you interact
with through Job Hunt — including any restrictions on automated access,
scraping, or assisted form-filling. Job Hunt does not review or guarantee
compliance with any third-party platform's terms on your behalf.

## You are responsible for what you submit

You are responsible for everything submitted under your name through any
workflow Job Hunt assists with — the accuracy of your CV and cover letter,
the truthfulness of any answers you provide in application forms, and the
decision to apply at all. Job Hunt assists with preparation and drafting; it
does not review your application the way a human advisor would, and it does
not decide what you send.

## Assisted apply has hard limits, by design

`/job-apply` never bypasses a CAPTCHA, never logs in on your behalf, and
never accepts terms, consent, or cookie prompts for you — it stops and hands
control back to you at each of those points. It never asks for, stores, or
types your passwords, API keys, or any other credential. If a platform
requires you to solve a CAPTCHA, log in, or accept terms, that step is yours
to complete.

---

If any of this is unclear, or you're relying on Job Hunt for a
consequential decision (a visa application, a contract, a legal filing),
stop and consult a qualified professional instead.
