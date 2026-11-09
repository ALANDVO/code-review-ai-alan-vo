# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

rust-rules-enhancement

## Roadmap

### rust-rules-enhancement — Add Rust-specific static analysis rules and evaluation samples

Status: done

Acceptance:
- Add SEC014 (unwrap panic risk), SEC015 (expect panic risk), BUG008 (println! debug output), MAINT004 (todo!/unimplemented!) rules for Rust
- Add 7 Rust evaluation samples covering the new rules
- All backend and frontend tests pass
- Evaluation run shows 100% pass rate for new Rust samples

Implementation: `backend/app/services/data/rules.json`, `backend/app/services/data/evaluation.json`

Tests: `backend/tests/test_main.py`, `frontend/src/test/client.test.ts`

### continue-implementation — Continue implementation and resolve known failures

Status: planned

Acceptance:
- Run checks, fix failures, and implement the next planned feature

---

Alan Vo · [alanvo.net](https://alanvo.net) · [X: @alanvoasi](https://x.com/alanvoasi)
