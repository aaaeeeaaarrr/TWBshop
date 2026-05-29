import psycopg2, sys
sys.path.insert(0, '/root/TWBshop')
from secrets import DATABASE_URL

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

def show_chat(chat_id, label=""):
    cur.execute("""
        SELECT sender_name, sent_at::date, COALESCE(media_type,'text') as mtype,
               COALESCE(text,'[no text]') as txt
        FROM ops_messages
        WHERE chat_id = %s
        ORDER BY sent_at
    """, (chat_id,))
    rows = cur.fetchall()
    print(f"\n{'='*60}")
    print(f"CHAT {chat_id} {label}")
    print(f"{'='*60}")
    for r in rows:
        sender = r[0] or 'None'
        print(f"  [{r[1]}] {sender[:25]:<25} [{r[2]}] {str(r[3])[:120]}")

# Voice-heavy applicant threads
show_chat(830013839, "Vtn - voice+photo Dec31 2025")
show_chat(375341521, "Bankkie - voice+sticker Dec20 2025")
show_chat(6760532895, "Moroi - voice+photo Dec12 2025")
show_chat(880867454, "Seounaro Houn - voice+photo Dec10-11 2025")
show_chat(737225396, "Reth Chanrath - voice+photo Dec2-3 2025")

conn.close()
