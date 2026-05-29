"""Proof: Opus block 1 — Sonnet validates exact repr() bytes."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hire_bot.khmer_validator import validate_khmer

BLOCK_1 = "ការដោះស្រាយកំហុសដោយស្ងាត់ មិនមែនជាការដោះស្រាយត្រឹមត្រូវទេ។"

print(f"BLOCK_1 repr: {repr(BLOCK_1)}")
print(f"BLOCK_1 length: {len(BLOCK_1)} chars")
result = validate_khmer(BLOCK_1)
print(f"BLOCK_1 result: {result}")
assert result["passed"], f"BLOCK_1 FAILED: {result['violations']}"
print("BLOCK_1: PASSED")
