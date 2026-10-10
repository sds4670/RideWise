# RideWise Assist

RideWise Assist is a conversational assistant for RideWise, a two-wheeler and EV
rental service in Bengaluru. It answers questions from customers and support
agents using a SQLite database (bookings, customers, vehicles) and a set of
policy documents (rental terms, cancellation and refund policy, late-return and
damage penalties, EV user guide). Built for the NeoStats AI Engineer Intern
Hackathon, 10 Oct 2026.

## Status

Only the items checked below exist today. Unchecked items are planned and are
not implemented.

- [x] Project scaffold (`.gitignore`, `.env.example`, data pack, this README)
- [ ] Database access layer and role scoping
- [ ] Rules engine (refunds, penalties)
- [ ] Agent loop
- [ ] Streamlit UI (`app.py`)
- [ ] Tests
- [ ] Adversarial / attack testing

## Quick start

Target setup time is under 10 minutes. Note: `requirements.txt` and `app.py`
arrive with later milestones (see Status); until then only the data and
environment steps apply.

Prerequisites: Python 3.10+ and Git.

```bash
git clone https://github.com/sds4670/RideWise.git
cd RideWise
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Data: the provided pack is not committed and must stay unmodified. Copy
`ridewise.db`, `data_dictionary.md` and the 5 policy PDFs into `data/`.

Environment: copy `.env.example` to `.env` and fill in the values.

- `LLM_BASE_URL` - base URL of the LLM endpoint.
- `LLM_API_KEY` - API key for that endpoint.
- `LLM_MODEL` - model name to call.

Credentials are provided by NeoStats. They live only in your local `.env`, which
is gitignored, and are never committed.

```bash
streamlit run app.py   # run the app
pytest                 # run tests
```

## How to use

In the sidebar, choose a role:

- Customer: enter a `customer_id` such as `CUST0001`. The assistant only sees
  that customer's data.
- Support Agent: broader access across customers, with PII masking.

The "New conversation" button resets the chat.

Example questions (Customer):
1. What is the status of my latest booking?
2. How much refund do I get if I cancel now?
3. What are the late-return charges?
4. Is my vehicle an EV, and how do I charge it?
5. What documents do I need to rent?
6. What is the penalty for a damaged vehicle?

Example questions (Support Agent):
1. Show the booking history for customer CUST0001.
2. Which bookings are overdue for return?
3. What refund applies to a booking made before the July 2026 cutoff?
4. Summarise the cancellation policy differences between v1 and v2.
5. What is the damage penalty schedule for EVs?
6. List vehicles currently on rent in Bengaluru.

## Architecture (planned)

```
          +-----------------------------+
 user --> |  Streamlit UI (app.py)      |
          +--------------+--------------+
                         |  session state (role, customer_id, history)
                         v
          +-----------------------------+
          |  Agent loop (agent.py)      |
          +--------------+--------------+
            |            |             |
            v            v             v
     +-----------+ +-----------+ +-------------+
     | DB tools  | | Rules     | | Policy text |
     | (db.py)   | | engine    | | (data/*.pdf)|
     +-----+-----+ +-----+-----+ +------+------+
           |             |              |
           v             v              v
     role-scoped   policy_rules.yaml  prompt context
     DB views
           ^
           |  SQL validator / guards (read-only)
```

- UI (`app.py`): role and `customer_id` selection, chat, conversation reset.
- Session: holds role, customer identity and message history per session.
- Agent loop (`agent.py`): orchestrates tool calls and composes answers.
- DB tools (`db.py`): read-only access through role-scoped views.
- Rules engine (`rules.py`, `policy_rules.yaml`): refund and penalty math.
- Policy text (`data/*.pdf`): full policy text supplied as prompt context.
- Guards: SQL validator and identity/scope checks enforced in code.

## Key design decisions

Rationale will be expanded in `DECISIONS.md` (not yet written).

- Identity and scope are enforced in code, not in prompts - prompts can be
  bypassed; code cannot.
- DB access is read-only through role-scoped views with a SQL validator -
  limits what any role can read and prevents writes.
- Money math runs in Python from `policy_rules.yaml` - deterministic and
  auditable, not left to the model.
- Refund policy version is chosen by `booked_at` in IST, cutoff
  2026-07-01 00:00 IST - the booking date decides which policy applies.
- Full policy text goes into the prompt instead of vector search - the corpus is
  small, so retrieval adds complexity without benefit.
- Free text from the DB is treated as untrusted - guards against injection via
  stored data.
- Answers cite their sources - users can verify where a number came from.

## Security and privacy

- No secrets in the repo. Credentials live only in local `.env` (gitignored);
  `sample_open_ai_wrapper.py` and the data pack are gitignored.
- Database access is read-only.
- PII is masked for the support-agent role.
- Prompt-injection attempts (including via stored DB text) are handled by code
  guards, not prompt instructions.
- Out-of-scope or unauthorised requests are refused rather than answered.

## Known limitations

To be completed after testing. Current true limitations:

- No application code or tests exist yet; only the scaffold is in place.
- Behaviour, accuracy and attack-resistance are unverified (to be completed
  after testing).

## Project structure

```
.
├── .env.example        # template for local .env (no real values)
├── .gitignore
├── README.md
├── data_dictionary.md  # schema description of ridewise.db
└── data/               # provided pack, not committed (copy in locally)
    ├── ridewise.db
    ├── data_dictionary.md
    └── *.pdf           # 5 policy documents + use case brief
```
