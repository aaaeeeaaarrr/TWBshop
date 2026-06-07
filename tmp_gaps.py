"""Daily message counts for the 5 GM chats around the outage — find the holes."""
from shared.database import _db

CHATS = [("REPORT", -5136886404), ("StockChecks", -1003952029131),
         ("Supervisors", -4980513319), ("Management", -865916135)]
# COMMS id from config
import config
CHATS.append(("COMMS", getattr(config, "COMMS_CHAT_ID", None)
              or getattr(config, "COMMS_TRANSFERS_CHAT_ID", 0)))

with _db() as conn:
    with conn.cursor() as cur:
        for label, cid in CHATS:
            if not cid:
                print(label, ": no chat id in config")
                continue
            cur.execute("""
                SELECT LEFT(sent_at,10) AS day, COUNT(*) AS n
                FROM ops_messages
                WHERE chat_id=%s AND sent_at >= '2026-05-25' AND sent_at < '2026-06-03'
                GROUP BY 1 ORDER BY 1
            """, (cid,))
            rows = {r["day"]: r["n"] for r in cur.fetchall()}
            days = ["2026-05-%02d" % d for d in range(25, 32)] + ["2026-06-01", "2026-06-02"]
            print("%-12s %s" % (label, "  ".join("%s:%s" % (d[8:], rows.get(d, "·")) for d in days)))
