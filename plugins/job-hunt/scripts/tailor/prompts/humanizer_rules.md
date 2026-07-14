# Humanizer Rules — write like a real engineer, not an LLM

The single biggest reason a CV gets binned as "AI slop" is its *register*: the
vocabulary, the rhythm, the suspiciously even polish. A skeptical hiring manager
spots it in seconds. This file exists to kill that tell at generation time. Obey
every rule below. The ban-list is also scanned in code after generation — any
banned token that slips through is flagged for human review, so do not use them.

---

## 1. BANNED PHRASES (hard ban — never output any of these)

These tokens are the machine-scannable ban-list. The pipeline greps the tailored
text (summary + bullets + highlights) for each one. Do **not** emit any of them,
in any casing or inflection:

- `leverage`
- `delve`
- `tapestry`
- `moreover`
- `furthermore`
- `robust`
- `seamless`
- `in today's fast-paced`
- `testament`
- `underscore`
- `navigate the landscape`

Also avoid the wider family these belong to — they read identically machine-made:
*spearheaded, utilise/utilize, facilitate, synergy, holistic, cutting-edge,
state-of-the-art, game-changer, best-in-class, plethora, myriad, embark,
unlock, elevate, harness, streamline, deep dive, at the forefront, passionate
about, results-driven, dynamic, ecosystem (as filler), realm, landscape (as
filler), it is worth noting, plays a crucial/pivotal/vital role, a wide range
of, drive impact, value-add.*

When you reach for one of these, stop and name the actual thing instead.

| Banned (LLM register) | Write instead (plain verb / concrete fact) |
| --- | --- |
| "Leveraged vector stores to..." | "Used vector stores to..." / "Built retrieval over a vector store that..." |
| "Spearheaded a robust, seamless pipeline" | "Built a RAG pipeline that hit 95%+ retrieval accuracy" |
| "Delved into multimodal data" | "Fused wearable, EEG, and self-report signals" |
| "A testament to my passion for AI" | (delete — show it in the work, do not assert it) |
| "Streamlined operations to drive impact" | "Cut release cycle time ~20% with Dockerised CI/CD" |

---

## 2. NO TRIADIC LISTS (the rule of three is an AI fingerprint)

LLMs compulsively group things in threes: "scalable, reliable, and efficient",
"design, build, and deploy", "automation, observability, and decision
intelligence". A page full of triads screams machine-written.

- Do not default every list to exactly three items. Vary list length — two, four,
  five — driven by the real content, not by cadence.
- Never use a triad of vague adjectives.

> **Before:** "Designed scalable, reliable, and maintainable AI systems."
> **After:** "Designed agentic AI systems with planning and memory that cut
> task-handling time ~35%."

(The summary in the master CV does use one domain triad — "healthcare, finance,
and operations" — that one is fine because it names real, concrete domains. The
ban is on *vague adjective* triads and on making three the default everywhere.)

---

## 3. NO VAGUE OR INFLATED METRICS — use only the real ones

Every number must come from the master CV. Do not round up, do not invent a
percentage to make a bullet "punchier", do not add a metric to a bullet that has
none in the master.

- Keep real metrics exactly as written (95%+, ~40%, +30%, -50%, +35%, -20%,
  MAE<0.35, R² up to 0.80, >95%, +20%).
- Never produce a suspiciously round, unsourced figure ("boosted productivity by
  10x", "improved accuracy by 300%"). These are the clearest fabrication tell.
- If a real bullet has no number, leave it without one — a concrete description
  beats a fake metric.

> **Before:** "Dramatically improved model performance by orders of magnitude."
> **After:** "Reached 95%+ accuracy on domain-specific knowledge retrieval."

---

## 4. VARY SENTENCE RHYTHM — uniform length is the dead giveaway

AI text marches in same-length sentences with the same shape. Humans don't. Mix
short and long. Let some bullets be five words and others be a full clause.

> **Before (uniform, machine-like):**
> "Developed scalable machine learning pipelines for production environments.
> Implemented robust monitoring solutions for deployed model systems.
> Designed comprehensive evaluation frameworks for model performance metrics."
>
> **After (varied, human):**
> "Built and shipped LLM pipelines end to end — prompt design through production
> inference. Added guardrails that cut bad outputs in half. Evaluation was
> continuous, not a one-off."

Avoid starting every bullet the same way ("Developed... Developed... Designed...
Designed..."). Open with the strongest real verb for that bullet.

---

## 5. PLAIN, STRONG VERBS

Use the verb a working engineer would use in standup: built, shipped, designed,
trained, deployed, fixed, cut, measured, integrated, containerised, validated,
tuned. Avoid corporate abstractions (facilitated, orchestrated-as-filler,
optimised-everything, drove, enabled, empowered) unless they are literally
accurate.

> **Before:** "Facilitated the orchestration of synergistic agent workflows."
> **After:** "Built multi-agent orchestration with task decomposition and
> inter-agent coordination."

---

## 6. CONCRETE SPECIFICS, NOT GENERIC FILLER

Name the system, the data, the tool, the outcome. Generic competence claims
("strong problem-solving skills", "passionate about innovation") are filler and
should be cut entirely. The master CV is full of specifics — use them.

> **Before:** "Experienced in working with various AI technologies and tools."
> **After:** "Worked across RAG, multi-agent orchestration, and MCP-based tool
> integration; stack was Python, PyTorch, Docker, AWS."

---

## 7. NO EM-DASH OVERUSE

The em-dash (—) is overused by LLMs as an all-purpose connector. At most **one**
em-dash per section, and only where a comma or full stop genuinely won't do.
Prefer commas, full stops, or a restructured sentence. Do not chain clauses with
multiple em-dashes in one sentence.

> **Before:** "Built a pipeline — fast, reliable — that scaled — and it worked."
> **After:** "Built a fast, reliable pipeline that scaled in production."

---

## 8. BRITISH / DUTCH-MARKET SPELLING (be consistent)

This CV targets the Netherlands / EU market. Use British spelling throughout and
never mix conventions on the same page:

- optimise, optimisation (not optimize/optimization)
- specialise, specialised
- containerise, containerised
- behaviour, modelling, programme, analyse, organise, licence (noun)

Keep proper nouns and library names as their real names (TensorFlow, PyTorch,
scikit-learn, Docker) — do not "Britishise" those.

---

## 9. NO PREAMBLE, NO META-COMMENTARY

Do not write "Here is the tailored summary" or explain your choices inside the CV
content. The CV fields contain only CV content. (Reasoning about the tailoring
belongs nowhere in the output JSON.)

---

## Quick self-check before you finalise each field

1. Did I use any banned word from §1? → remove it.
2. Are three-quarters of my bullets the same length/shape? → vary them.
3. Is every number in the master CV verbatim? → no invented metrics.
4. More than one em-dash in a section? → cut to one or zero.
5. Any vague adjective triad ("scalable, reliable, efficient")? → replace with a
   concrete claim.
6. Consistent British spelling? → fix any US spellings.
7. Would this line survive a hiring manager asking "prove it" in interview? → if
   not, it is either fabricated or fluff; cut or ground it.
