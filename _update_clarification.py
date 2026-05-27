from shared.database import receipt_upsert_answered
import config

CHAT = config.DAILY_REPORT_CHAT_ID

receipt_upsert_answered(
    chat_id=CHAT,
    photo_msg_id=511071,
    bot_msg_id=511086,
    question="Can you tell me what this says? I can see Big easy delivery 2.00B, Cafe de paris 2.00B, Bliss & Beats 1.60B, Change small gas 2.50B, Flour delivery 2.50B but hard to read.",
    answer=(
        "This is a mixed handwritten expense sheet. Some lines are delivery charges we paid upfront "
        "for B2B customers (Big Easy, Cafe de Paris, Bliss & Beats etc) who repay us later. "
        "Change small gas means small gas canisters for our portable movable stoves used at bakery "
        "stations - staff take these to any workstation for cake and bakery work. Flour delivery is "
        "a delivery fee. These are all receiptless expenses so staff write them down instead of a receipt. "
        "This is a valid expense document."
    ),
    sender_name="Owner",
)
print("Updated.")
