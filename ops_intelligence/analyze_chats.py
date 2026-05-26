"""Temporary analysis script — run once to identify unknown chats."""
import sys
sys.path.insert(0, '/root/TWBshop')
from shared.database import _db

unknown_chats = [
    (-1002813660308, "ABA TWB"),
    (-732167426, "Games WoC"),
    (-556644892, "Koh Kong Smoked Chicken"),
    (-580139431, "Drink Shop wine o clock"),
    (-740456627, "Tiger Wine Bakery 24"),
    (311350085, "Kety_Sek"),
    (1367519274, "speaking_duff"),
    (1018669211, "Choronai com"),
    (960564620, "Lina"),
    (-4189007723, "B2B The Deck"),
    (-436441225, "Auskhmer"),
    (-1001931273407, "Wine clock bakery Eco Hotel"),
    (835382782, "a95030"),
    (1914777265, "theodore_tedd"),
    (1138296296, "Hotline"),
    (6872279388, "Kingmeow23"),
    (1065466447, "kaglynn"),
    (5103368646, "Shailani"),
    (6184567467, "Quizilah"),
    (813908676, "Nham Bunler"),
    (5439025081, "Madam_Nich"),
    (531822321, "saoyupheng144"),
    (5571523375, "Rory_Tinker"),
    (338042906, "CoachAnt"),
    (1037994441, "maochanthol"),
    (338884417, "Sopheaplim1"),
    (820102470, "Ep0nymonym17"),
    (1264221168, "PrinceMoh007"),
    (6332752724, "vvc_smart"),
    (851284081, "Jamierainekh"),
    (1282381310, "Grabb"),
    (2110695725, "PastaHousePhnomPenh"),
    (1313155971, "RollingRR"),
    (-949802815, "Chicken pfoods"),
    (-777054775, "Grand Place Chocolate"),
    (-766343069, "AMN Grocery"),
    (-512565311, "Wine O clock old"),
    (-4695033653, "Betagro"),
    (843614398, "Coffee bean"),
    (-430839748, "OSTRA ORDER"),
    (-659134937, "LIM supplies"),
    (1265384008, "TukOutMerchantsBot"),
]

with _db() as conn:
    with conn.cursor() as cur:
        for chat_id, label in unknown_chats:
            cur.execute("""
                (SELECT sender_name, text, sent_at FROM ops_messages
                 WHERE chat_id = %s AND text != '' ORDER BY sent_at ASC LIMIT 4)
                UNION ALL
                (SELECT sender_name, text, sent_at FROM ops_messages
                 WHERE chat_id = %s AND text != '' ORDER BY sent_at DESC LIMIT 4)
            """, (chat_id, chat_id))
            rows = cur.fetchall()
            print("\n=== %s ===" % label)
            for r in rows:
                print("  [%s] %s: %s" % (
                    str(r['sent_at'])[:10],
                    str(r['sender_name'] or '?')[:20],
                    str(r['text'] or '')[:150]
                ))
