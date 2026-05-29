"""Seed SHOP NOT REAL fake customer with realistic test data."""
import sys, json
sys.path.insert(0, r"C:\Users\Papa\TWBshop")
from secrets import DATABASE_URL
import psycopg2
from datetime import datetime, timezone, timedelta

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

CHAT_ID = -9999999001
NAME    = "SHOP NOT REAL"

def date_str(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")

def ts(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

now = datetime.now(timezone.utc).isoformat()

# ── 1. Customer ────────────────────────────────────────────────────────────
cur.execute("DELETE FROM b2b_recurring_confirmations WHERE recurring_order_id IN "
            "(SELECT id FROM b2b_recurring_orders WHERE group_chat_id = %s)", (CHAT_ID,))
for tbl in ["b2b_dispatch_reminders", "b2b_markpaid_requests", "b2b_payments",
            "b2b_cake_orders", "b2b_orders", "b2b_recurring_orders",
            "b2b_pending_verifications", "b2b_customers"]:
    cur.execute(f"DELETE FROM {tbl} WHERE group_chat_id = %s", (CHAT_ID,))

cur.execute("""
    INSERT INTO b2b_customers
        (group_chat_id, business_name, delivery_method, delivery_time,
         location, location_lat, location_lng, delivery_cost, credit, updated_at,
         bot_state, bot_cart, bot_pending, bot_last_confirmation,
         bot_editing_session, menu_message_id, menu_qty_pending)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,NULL,NULL,NULL,NULL,NULL)
""", (CHAT_ID, NAME, "delivery", "10:00",
      "Phnom Penh", 11.5560, 104.9282, 1.50, 0, now))
print("Customer created")

# ── 2. Past orders ─────────────────────────────────────────────────────────
orders = [
    # item,                    qty, grams, notes,             date,          status,      payment_status, batch
    ("French Baguette",        20,  None,  None,              date_str(14),  "fulfilled", "paid",         "batch-snr-01"),
    ("Croissant",              30,  None,  None,              date_str(14),  "fulfilled", "paid",         "batch-snr-01"),
    ("Pain Au Chocolat",       15,  None,  None,              date_str(14),  "fulfilled", "paid",         "batch-snr-01"),
    ("Multigrain Baguette",    10,  None,  None,              date_str(11),  "fulfilled", "paid",         "batch-snr-02"),
    ("Focaccia",                8,  None,  None,              date_str(11),  "fulfilled", "paid",         "batch-snr-02"),
    ("French Baguette",        25,  None,  None,              date_str(7),   "fulfilled", "paid",         "batch-snr-03"),
    ("Croissant",              40,  None,  None,              date_str(7),   "fulfilled", "paid",         "batch-snr-03"),
    ("Bagel",                  12,  None,  "sesame please",   date_str(7),   "fulfilled", "paid",         "batch-snr-03"),
    ("Multigrain Loaf",         5,  None,  None,              date_str(4),   "fulfilled", "unpaid",       "batch-snr-04"),
    ("Croissant",              35,  None,  None,              date_str(4),   "fulfilled", "unpaid",       "batch-snr-04"),
    ("Pain Au Chocolat",       20,  None,  None,              date_str(4),   "fulfilled", "unpaid",       "batch-snr-04"),
    ("French Baguette",        20,  None,  None,              date_str(2),   "fulfilled", "unpaid",       "batch-snr-05"),
    ("Croutons",                4,  None,  "extra crispy",    date_str(2),   "fulfilled", "unpaid",       "batch-snr-05"),
    ("Croissant",              50,  None,  None,              date_str(1),   "confirmed", "unpaid",       "batch-snr-06"),
    ("Multigrain Baguette",    15,  None,  None,              date_str(1),   "confirmed", "unpaid",       "batch-snr-06"),
]
for o in orders:
    cur.execute("""
        INSERT INTO b2b_orders
            (group_chat_id, business_name, item, quantity, grams, notes,
             delivery_date, status, payment_status, created_at, batch_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (CHAT_ID, NAME, o[0], o[1], o[2], o[3], o[4], o[5], o[6], now, o[7]))
print(f"Orders inserted: {len(orders)}")

# ── 3. Cake orders ─────────────────────────────────────────────────────────
cakes = [
    # item,                category,      order_type, qty, slices, date,         status,      payment_status, batch
    ("Birthday Cake 1kg", "celebration", "custom",    1,   8,      date_str(10), "fulfilled", "paid",         "batch-snr-02"),
    ("Wedding Tier Cake", "wedding",     "custom",    1,   24,     date_str(5),  "fulfilled", "unpaid",       "batch-snr-04"),
]
for c in cakes:
    cur.execute("""
        INSERT INTO b2b_cake_orders
            (group_chat_id, business_name, item, cake_category, order_type,
             quantity, slices, delivery_date, status, payment_status, created_at, batch_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (CHAT_ID, NAME, c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], now, c[8]))
print(f"Cake orders inserted: {len(cakes)}")

# ── 4. Payments ────────────────────────────────────────────────────────────
payments = [
    # amount, status,    method, covered_dates,                                            applied_at, created_at
    (45.50,  "applied", "ABA",  json.dumps([date_str(14)]),                               ts(13),     ts(14)),
    (38.20,  "applied", "Wing", json.dumps([date_str(11), date_str(10)]),                 ts(10),     ts(11)),
    (72.00,  "applied", "cash", json.dumps([date_str(7)]),                                ts(6),      ts(7)),
    (18.50,  "pending", "ABA",  None,                                                     None,       ts(1)),
]
for p in payments:
    cur.execute("""
        INSERT INTO b2b_payments
            (group_chat_id, business_name, amount, status, method,
             covered_dates, applied_at, created_at,
             screenshot_path, group_message_id, tg_file_unique_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,NULL)
    """, (CHAT_ID, NAME, p[0], p[1], p[2], p[3], p[4], p[5]))
print(f"Payments inserted: {len(payments)}")

# ── 5. Recurring orders ────────────────────────────────────────────────────
items_daily = json.dumps([
    {"item": "French Baguette", "quantity": 20},
    {"item": "Croissant",       "quantity": 30},
])
items_weekly = json.dumps([
    {"item": "Multigrain Loaf", "quantity": 5},
    {"item": "Focaccia",        "quantity": 6},
])

cur.execute("""
    INSERT INTO b2b_recurring_orders
        (group_chat_id, business_name, items_json, days_of_week,
         delivery_time, delivery_method, status, created_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
""", (CHAT_ID, NAME, items_daily, "0,1,2,3,4", "10:00", "delivery", "active", ts(20)))
rec_id1 = cur.fetchone()[0]

cur.execute("""
    INSERT INTO b2b_recurring_orders
        (group_chat_id, business_name, items_json, days_of_week,
         delivery_time, delivery_method, status, created_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
""", (CHAT_ID, NAME, items_weekly, "1", "14:00", "delivery", "active", ts(15)))
rec_id2 = cur.fetchone()[0]

# Confirmations for daily recurring (last 5 days)
for d in [5, 4, 3, 2, 1]:
    cur.execute("""
        INSERT INTO b2b_recurring_confirmations
            (recurring_order_id, fulfillment_date, status, reminder_sent, created_at)
        VALUES (%s,%s,%s,%s,%s)
    """, (rec_id1, date_str(d), "confirmed", 1, ts(d + 1)))

# 1 skipped + 1 pending for weekly
cur.execute("""
    INSERT INTO b2b_recurring_confirmations
        (recurring_order_id, fulfillment_date, status, reminder_sent, created_at)
    VALUES (%s,%s,%s,%s,%s)
""", (rec_id2, date_str(8), "skipped", 1, ts(9)))
cur.execute("""
    INSERT INTO b2b_recurring_confirmations
        (recurring_order_id, fulfillment_date, status, reminder_sent, created_at)
    VALUES (%s,%s,%s,%s,%s)
""", (rec_id2, date_str(0), "pending", 0, now))
print("Recurring orders + confirmations inserted")

# ── 6. Dispatch reminders ──────────────────────────────────────────────────
dispatches = [
    (date_str(14), "10:00", "delivery", "sent",    False, ts(14)),
    (date_str(7),  "10:00", "delivery", "sent",    False, ts(7)),
    (date_str(1),  "10:00", "delivery", "pending", False, now),
]
for d in dispatches:
    cur.execute("""
        INSERT INTO b2b_dispatch_reminders
            (group_chat_id, fulfillment_date, fulfillment_time,
             delivery_method, status, owner_message_id, snooze_until, escalated, created_at)
        VALUES (%s,%s,%s,%s,%s,NULL,NULL,%s,%s)
    """, (CHAT_ID, d[0], d[1], d[2], d[3], d[4], d[5]))
print(f"Dispatch reminders inserted: {len(dispatches)}")

# ── 7. Markpaid request (pending owner approval) ───────────────────────────
cur.execute("""
    INSERT INTO b2b_markpaid_requests
        (group_chat_id, business_name, amount, method,
         staff_user_id, staff_msg_id, owner_msg_id, status, covered_dates, created_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", (CHAT_ID, NAME, 52.30, "ABA",
      1271537077, 9991, 9992, "pending",
      json.dumps([date_str(4), date_str(2)]), ts(1)))
print("Markpaid request inserted")

conn.commit()
conn.close()
print("\nSHOP NOT REAL fully seeded.")
