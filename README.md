# EMPIRE-OS

A persistent intelligence and governed execution system that converts activity into structured memory, detects drift, enforces authority, and produces verifiable action receipts.

## Phase 21 governance runtime

Empire OS now implements the canonical command loop:

`AUTHORIZE → APPROVE → EXECUTE → VERIFY → RECONCILE → RESOLVE → SEAL`

The runtime includes deterministic role and action policy, founder approval gates, registered executors, independent evidence verification, financial reconciliation checks, idempotency, full state history, and a tamper-evident receipt chain.

### Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8787
```

Open `/docs` for the API and `/v1/governance/health` for governance status.

### Test

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

See [`docs/PHASE_21_GOVERNANCE_LOOP.md`](docs/PHASE_21_GOVERNANCE_LOOP.md) for the policy, state machine, endpoints, and proof request.

## Canon

- **WE EVOLVE. NEVER DELETE.**
- Founder has final authority.
- No execution without verification.
- No revenue without a receipt.
- Unknown and destructive capabilities stay blocked until explicitly governed.
