"""Owner activation (2026-07-02): set Thyda's + Tyty's per-staff exceptions (F1).

Thyda (#34) — owner spec "payback from AL · all approved by Tyty (1) · never to Supervisors, escalate to Tyty":
    payback_to_al · escalate_to_id=28 (Tyty) · no_supervisor_posts (fail-safe belt) ·
    al_approver_id=28 · swap_approver_id=28 · leave_approver_id=28 (inert — special leave is declarative).
Tyty (#28) — preset vip_exempt (fully exempt / owner-family).

Idempotent + reversible. Dry-run by default; --apply to set; --revert to clear BOTH back to {}.
Independent before/after read. NOT test-scoped — this is live config (redirected to owner while
attendance_test_mode is on; effective for real once test mode is off).

Usage: TWBSHOP_ENV=prod PYTHONPATH=. python scripts/set_thyda_tyty_exceptions.py [--apply|--revert]
"""
import sys
sys.path.insert(0, r"C:\Users\Papa\twbshop")
from core import exceptions as ex

ORG = "twb"
TYTY, THYDA = 28, 34
THYDA_EXC = {
    "payback_to_al": True,
    "no_supervisor_posts": True,
    "escalate_to_id": TYTY,
    "al_approver_id": TYTY,
    "swap_approver_id": TYTY,
    "leave_approver_id": TYTY,
}


def show(tag):
    print(tag)
    print("  Thyda(34):", ex.get_exceptions(ORG, THYDA))
    print("  Tyty(28): ", ex.get_exceptions(ORG, TYTY))


def main(mode):
    show("BEFORE:")
    if mode == "apply":
        ex.set_exceptions(ORG, THYDA, THYDA_EXC)
        ex.set_exceptions(ORG, TYTY, ex.apply_preset("vip_exempt"))
        show("\nAFTER (independent re-read):")
    elif mode == "revert":
        ex.set_exceptions(ORG, THYDA, {})
        ex.set_exceptions(ORG, TYTY, {})
        show("\nAFTER REVERT (independent re-read):")
    else:
        print("\nDRY-RUN — would set:")
        print("  Thyda(34):", ex._clean_exceptions(THYDA_EXC))
        print("  Tyty(28): ", ex.apply_preset("vip_exempt"))
        print("Pass --apply to set, --revert to clear.")


if __name__ == "__main__":
    main("apply" if "--apply" in sys.argv else "revert" if "--revert" in sys.argv else "dry")
