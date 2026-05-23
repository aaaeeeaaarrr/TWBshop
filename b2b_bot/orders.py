"""Facade — re-exports from order_parsing and order_handlers for backward compatibility."""

from b2b_bot.order_parsing import (  # noqa: F401
    _resolve_bread_history,
    _resolve_cake_history,
    _split_mini_items,
    _mini_rejection_note,
    _build_confirmation,
    _confirm_keyboard,
)
from b2b_bot.order_handlers import (  # noqa: F401
    _pending,
    _state,
    _last_confirmation,
    handle_group_message,
    handle_callback,
    handle_order_photo,
)
