# Extending Job Hunt

The plugin has two extension points that don't require touching any skill's
prompt wording: **work-authorisation schemes** and **platform selection**.
Both are driven by small, testable Python interfaces under
`plugins/job-hunt/scripts/`.

## Adding a new work-authorisation scheme

A scheme is a `WorkAuthProvider` — a class that annotates a list of company
names with a work-auth status and gates individual listings based on that
status. Three ship today: `none`, `eu-blue-card`, `nl-ind-hsm`.

### 1. The interface (`work_auth/base.py`)

```python
class WorkAuthProvider:
    scheme: str = "base"

    def annotate(self, companies: list[str]) -> dict[str, dict[str, Any]]:
        """Return {company: {"status": <STATUS>, ...}} for each input company."""
        raise NotImplementedError

    def gate(self, listing: dict[str, Any]) -> str:
        """Return KEEP / FLAG / DROP for one listing. Reads the status the
        caller attached at listing["work_auth"]["status"]."""
        raise NotImplementedError
```

`status` must be one of the canonical values in `work_auth.base.STATUSES`:
`"confirmed"`, `"possible"`, `"not_found"`, `"flag"`, `"n/a"`. `gate()` must
return one of `KEEP`, `FLAG`, `DROP` (the module-level constants — `"keep"`,
`"flag"`, `"drop"`).

Providers must be **pure and offline**: `annotate()`/`gate()` read only
local/cached data, never the network. If your scheme needs a live data
source (like `nl-ind-hsm`'s IND register), put that behind an injectable
`refresh()` method instead, so annotation itself stays offline-testable — see
`work_auth/nl_ind_hsm.py` for the pattern (its `refresh()` takes
`from_names`, `from_file`, or a `fetch` callable, all optional, so tests never
hit the network).

The simplest real example is `work_auth/none_provider.py`:

```python
class NoneProvider(WorkAuthProvider):
    scheme = "none"

    def annotate(self, companies):
        return {c: {"status": "n/a"} for c in dict.fromkeys(companies)}

    def gate(self, listing):
        return KEEP
```

And a flag-only example, `work_auth/eu_blue_card.py`, for schemes where no
authoritative register exists to confirm against — it flags every listing
for manual review instead of guessing.

### 2. Register the scheme

Two places have to agree on the scheme's name string, and they're
deliberately validated against each other:

- `engine/profile.py`: add your scheme string to the `SCHEMES: set[str]`
  constant. This is what `validate_profile()` checks `work_auth.scheme`
  against when `/job-setup` writes a profile.
- `work_auth/__init__.py`: add a branch to `get_provider()`:

```python
def get_provider(scheme: str, **kwargs: Any) -> WorkAuthProvider:
    if scheme not in SCHEMES:
        raise ValueError(f"unknown work_auth scheme {scheme!r}; allowed: {sorted(SCHEMES)}")
    if scheme == "none":
        return NoneProvider()
    if scheme == "eu-blue-card":
        return EuBlueCardProvider()
    if scheme == "nl-ind-hsm":
        from work_auth.nl_ind_hsm import NlIndHsmProvider
        return NlIndHsmProvider(**kwargs)
    # add your scheme here
    raise ValueError(f"scheme {scheme!r} has no registered provider")
```

`get_provider(scheme)` is the only way the rest of the engine (and the
`job-search` skill, via `search.search_cli`) obtains a provider — nothing
imports a concrete provider class directly except the registry itself.

### 3. Tell `/job-setup` about it

The `job-setup` skill (`plugins/job-hunt/skills/job-setup/SKILL.md`) lists the
allowed schemes in its own prose (step 2) so the guided setup conversation can
offer it to the user. Add your scheme name and a one-line description there.
No code change is required for the skill itself — it just needs to know what
to *say*; `write-profile` will reject an unlisted scheme string regardless,
because `validate_profile()` checks against `SCHEMES`.

### 4. Test it

Follow `tests/test_work_auth_providers.py` and `tests/test_nl_ind_hsm.py`:
import `work_auth` as `wa`, call `wa.get_provider("<your-scheme>")`, and
assert `annotate()`/`gate()` behave as documented — including that
`gate()` only ever returns `"keep"`, `"flag"`, or `"drop"`, and that an
unknown scheme still raises `ValueError`.

## How platform selection works

Platforms are plain string keys, not classes — there's no provider interface
to implement, because platform discovery is performed by Claude via MCP/
Playwright tools inside the `job-search` skill, not by Python.

### 1. The allowed set (`engine/profile.py`)

```python
PLATFORMS: set[str] = {
    "linkedin",
    "indeed",
    "naukri",
    "career_pages",
    "greenhouse_lever",
}
```

`validate_profile()` rejects any `profile.platforms` entry not in this set.
To add a platform, add its key here first.

### 2. Wire it into the two skills

- `plugins/job-hunt/skills/job-setup/SKILL.md` — add the key to the offered
  set in step 2 ("Platforms to search — offer the allowed set: ...").
- `plugins/job-hunt/skills/job-search/SKILL.md` — add a row to the "Discover"
  step's table describing which tool to use for that key and what to extract
  (title, company, location, a stable job id, URL). This is prose read by
  Claude at run time, not a Python dispatch table, so no code deploy is
  needed to change *how* a platform is queried — only to add or remove which
  keys are legal in a profile.

### 3. Runtime behaviour

`/job-search` iterates `profile.platforms` and, for each key, uses the
matching tool as documented in the skill. If the required MCP/Playwright tool
isn't available in the session, it skips that platform and says so
explicitly — it never fabricates or approximates results for a platform it
couldn't actually query. Every listing collected, regardless of platform, is
normalised through `search/listing.py`'s `normalize_listing()` into the same
canonical shape (`source, company, role, location, url, job_id, posted_date,
level`) before it reaches the deterministic annotate/filter/dedupe/rank
pipeline in `search/search_cli.py` — so a new platform only needs to produce
that shape; everything downstream is platform-agnostic already.
