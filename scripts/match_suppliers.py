"""Map OCR'd receipt vendors -> supplier Telegram groups (the vendor<->group seed).

Reads the OCR catalogue (scripts/ocr_catalogue.py output) and classifies every
doc_type=='receipt' vendor into: matched-to-a-group / our-own-name (bill-to) /
known-but-no-group / unsure / blank / payment-slip. Pure Python, re-runnable, zero
API. The matched set is the draft seed for acc_vendors.tg_group_id (P0).

    python scripts/match_suppliers.py [catalogue.jsonl]
"""
import json
import sys
from collections import Counter, defaultdict

from ops_intelligence.price_list_fetcher import SUPPLIER_CHATS  # id -> label

LABEL_TO_ID = {label: cid for cid, label in SUPPLIER_CHATS.items()}

# Resolved vendor-substring -> supplier-group label (domain knowledge + the 7 I viewed).
CURATED = {
    "indoguna": "Indoguna", "indochina": "Indoguna", "indocouna": "Indoguna",  # OCR misreads
    "makro": "Makro",
    "dan meat": "Dan_Meat",
    "buonissimo": "Buonissimo",
    "thai huot": "ThaiHuot", "thaihuot": "ThaiHuot",
    "soma": "SOMA_Eggs",
    "betagro": "Betagro",
    "puratos": "Grand_Place_Chocolate", "grand-place": "Grand_Place_Chocolate",
    "grand place": "Grand_Place_Chocolate",
    "melbourne": "Melbourne_Coffee",
    "tiger": "Tiger_Beer",                                     # Tiger Delivery = Tiger Keg
    "wine merchants": "The_Warehouse_Wine", "warehouse": "The_Warehouse_Wine",
}

# Our own name on a bill-to / own sales slip -> supplier not identifiable from this read.
SELF = ["wine bakery", "winebakery", "cafe wine", "cofe-wire", "cage wine",
        "wine crouch", "wine o", "r cafe"]

# Known vendor but NO supplier Telegram group in SUPPLIER_CHATS (cash / local / service).
NOGROUP = {
    "atlas": "Atlas Ice — BIG recurring supplier, NO group",
    "angkor market": "Angkor Market (grocery)", "i4b": "Angkor Market (i4B receipts)",
    "big c": "Big C supermarket", "home top": "Home Top Market",
    "lucky express": "Lucky Express (logistics)", "cpa printing": "CPA Printing",
    "dynamic security": "Dynamic Security (service)", "oyo": "OYO (soap/handicraft)",
    "song heng": "Song Heng (gas)",
    "repertoire": "Repertoire Culinaire (fine foods)",
    "cake supply": "The Cake Supply Shop (has ABA acct)",
}


def classify(vendor: str):
    v = (vendor or "").strip().lower()
    if not v:
        return ("BLANK", None)
    for key, group in CURATED.items():
        if key in v:
            return ("MATCHED", group)
    for key, note in NOGROUP.items():
        if key in v:
            return ("NOGROUP", note)
    for key in SELF:
        if key in v:
            return ("SELF", None)
    if v == "aba":
        return ("PAYMENT_SLIP", None)
    return ("UNSURE", None)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ocr_catalogue.jsonl"
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    rec = [r for r in rows if r.get("doc_type") == "receipt"]

    matched = defaultdict(Counter)     # group -> Counter(raw vendor)
    nogroup = Counter()
    unsure = defaultdict(list)         # raw vendor -> [files]
    self_n = blank_n = slip_n = 0

    for r in rec:
        bucket, key = classify(r.get("vendor"))
        raw = (r.get("vendor") or "").strip()
        if bucket == "MATCHED":
            matched[key][raw] += 1
        elif bucket == "NOGROUP":
            nogroup[key] += 1
        elif bucket == "SELF":
            self_n += 1
        elif bucket == "BLANK":
            blank_n += 1
        elif bucket == "PAYMENT_SLIP":
            slip_n += 1
        else:
            unsure[raw].append(r["file"])

    print(f"=== {len(rec)} receipts ===\n")
    print("--- MATCHED to a supplier group (draft acc_vendors seed) ---")
    tot_m = 0
    for group in sorted(matched, key=lambda g: -sum(matched[g].values())):
        n = sum(matched[group].values())
        tot_m += n
        gid = LABEL_TO_ID.get(group, "?")
        variants = ", ".join(f"{v}×{c}" for v, c in matched[group].most_common())
        print(f"  {n:>3}  {group}  (group_id {gid})")
        print(f"       [{variants}]")
    print(f"  -> {tot_m} receipts matched to {len(matched)} groups\n")

    print("--- KNOWN vendor but NO supplier group (cash / local / service) ---")
    for note, n in nogroup.most_common():
        print(f"  {n:>3}  {note}")
    print(f"  -> {sum(nogroup.values())} receipts\n")

    print(f"--- OUR OWN name / bill-to (supplier unreadable from this image): {self_n}")
    print(f"--- BLANK vendor (amount readable, name not captured): {blank_n}")
    print(f"--- ABA payment slips misfiled as receipts: {slip_n}\n")

    print("--- UNSURE — need your call ---")
    for raw, files in sorted(unsure.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(files):>3}  {raw or '(?)'}   e.g. {files[0]}")
    print(f"  -> {sum(len(f) for f in unsure.values())} receipts\n")

    total = tot_m + sum(nogroup.values()) + self_n + blank_n + slip_n + \
        sum(len(f) for f in unsure.values())
    print(f"reconcile: {total} == {len(rec)} receipts")


if __name__ == "__main__":
    main()
