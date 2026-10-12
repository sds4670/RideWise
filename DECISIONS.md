# DECISIONS

## 1. Three most important design decisions

**1. Trust lives in code; the LLM sits at the edge.**
Identity comes from the session, and the database connection itself is scoped: customer sessions get TEMP views filtered to their own `customer_id`, opened read-only. The LLM never supplies a customer ID (any it sends is discarded). Agents get operational views with PII masked in SQL. Reason: prompts can be jailbroken, a connection that does not contain other customers' rows cannot leak them. Layers on top (early refusal, SQL validator, output redaction) are defence in depth.

**2. Every rupee is computed in Python from config.**
Rental charge, late fee, battery fee, deposit, GST and refunds are pure functions in `src/rules/engine.py`, reading `policy_rules.yaml` where each constant cites its document and clause. The LLM chooses the tool and explains the result. Reason: hidden questions are calculations and LLM arithmetic is unreliable. Specific traps handled: the refund version is decided by `booked_at` converted to IST (cutoff 2026-06-30 18:30 UTC); the refund base counts only SUCCESS BOOKING payments; GOLD grace is 30 minutes and over that the full lateness is charged; exactly 10% battery is no fee. Tests reproduce all PDF examples and real bookings on both sides of the cutoff (`B-1163` v1, `B-1165` v2).

**3. Answers separate "policy says" from "recorded", and show their sources.**
Quote tools return the computed amount and the matching database rows as different fields. Example: `B-0004` was returned at 7% battery and the fee is recorded, but its damage claim `DMG0002` is OPEN and therefore not charged. The assistant must not present computed math as something that happened. Each answer carries tool calls, SQL and policy clauses in a "How I got this" panel. Reason: honest and verifiable answers.

## 2. Alternatives considered and rejected

- **Naive vector RAG over the policies.** Fixed-size vector chunks can split a table across rows, miss a version-scope clause or an annexure, and give a wrong refund; and the version choice depends on a date, not similarity. We kept the inline-prompt mode (`RAG_MODE=full`) and added a *structure-aware* RAG instead (see section 5), where clauses and tables are whole and the version is chosen by code.
- **Free LLM-written SQL only.** Unstable on joins and unsafe. Curated tools handle common questions; a validated `run_sql` covers unseen analytic ones.
- **Fixed query templates only.** Safe but breaks on unseen questions.
- **Security by prompt only.** Can be jailbroken.
- **LLM does the arithmetic.** Unreliable and not auditable.
- **One large prompt without tools.** No sources, harder to test and debug.
- **Building a login system.** Not required by the brief; role is chosen at session start.

## 3. Where the assistant currently fails or behaves poorly

- Policy text is in the prompt, so it will not scale to a large document set, and it adds tokens to every call.
- Adding a new tier or policy version is a config edit, but a new rule type needs code.
- `quote_refund` on a non-cancelled booking returns a labelled projection, which can confuse users.
- The early refusal guard is rule-based and can miss unusual wording. The scoped views still prevent exposure.
- Injection defence is layered (fencing, prompt rule, masking, redaction) but not a perfect filter.
- Response time depends on the hosted reasoning model and the number of tool steps (capped at 6).
- Ambiguous questions rely on the model asking a clarifying question.
- TODO: add concrete failures observed in the live question run (`outputs/results.md`).

## 4. What I would build next with one more week

- A graded evaluation suite of real questions with expected answers, run on every commit.
- Authentication and per-user rate limits.
- Clause-level hybrid retrieval with version metadata for larger document sets, with both refund versions always injected and the version chosen by code.
- Logging and monitoring of tool calls, refusals and latency.
- Response caching and prefix caching to cut latency and cost.
- An escalation flow to a human agent for disputes and low-confidence answers.
- Automated detection of mismatches between policy and recorded charges for the support team.

## 5. Policy retrieval (RAG) design

Added as `RAG_MODE=rag` (default); `RAG_MODE=full` restores the inline-prompt behaviour. The whole feature is behind the existing `search_policy` tool, so the rules engine, scoped DB views, guards and other tools are unchanged.

**Why structure-aware clause chunking, not fixed-size windows.** One chunk is one numbered clause, heading section, table or FAQ Q&A, with no overlap. Tables are never split by row and a clause keeps its worked example, because the questions here are about exact slabs and thresholds: a half-table or a clause separated from its example gives a wrong number. Each chunk begins with a context header (doc, version, effective date, applicability, clause) so it is self-contained when retrieved. The two scanned annexures (v2 refund schedule, tier grace) are images with no extractable text, so they come from the hand-transcribed `annexes.md` and are treated as authoritative for those pages. The inventory is written to `docs/CHUNKS.md` for review.

**Why code picks the version, never similarity.** Refund/cancellation/no-show queries always return both v1 (RW-POL-02) and v2 (RW-POL-03) plus each scope clause, so a retrieval miss can never drop a version. When a booking is in context, `engine.refund_version` (the same IST cutoff, 2026-06-30 18:30 UTC, used for actual quotes) labels the applicable version "APPLIES to this booking" and the other "SUPERSEDED, shown for reference". With no booking, both are labelled with their date condition and the model states both or asks. Late-fee/grace queries always include Annexure A; deposit queries include RW-POL-01 clause 5. This keeps the date-driven logic in one place and out of the similarity ranking.

**Why BM25 (with optional embeddings), not a mandatory embedding model.** The corpus is tiny, the vocabulary is shared between question and clause, and the brief forbids downloading local models or adding heavy dependencies. BM25 (`rank_bm25`) needs none of that and builds in well under a second. Embeddings are fused in via reciprocal rank fusion *only* if the endpoint exposes an embedding deployment (`LLM_EMBED_MODEL`); otherwise retrieval is BM25 plus metadata filtering. The index lives in `index/` (gitignored) and auto-rebuilds when a hash of the sources or the chunker version changes; it never writes to `data/` or `ridewise.db`.

**Measured.** Retrieval hit-rate is 21 of 22 policy questions (95%) with an expected clause in the top 4 (`tests/test_retrieval.py`). The one miss is "cancellation by RideWise": the forced v1/v2 refund-slab chunks crowd clause 2 out of the top 4 for that phrasing.

**Trade-offs.** BM25 can miss heavily paraphrased questions that share no words with the clause; embeddings would help but depend on an endpoint model. Structure-aware chunking is tuned to these five documents' numbering and would need adjusting for a differently formatted pack. Forcing both refund versions and family-specific chunks improves correctness but reduces slot space for other relevant clauses (the cause of the single hit-rate miss).
