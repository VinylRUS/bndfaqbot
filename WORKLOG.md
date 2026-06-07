# HelpDesk Bot v6 Worklog

## Task: Fix all bugs in HelpDesk bot v5

### Root Cause Analysis
The `handle_free_text` handler in `user.py` was consuming ALL text messages before FSM handlers in other routers (operator, admin) could process them. Since `user_router` is registered first in the Dispatcher, its handlers are checked first. When `handle_free_text` matched a text message, it consumed the event — even if it then did nothing (returned early because FSM state was active). This caused:
- Operator replies being silently dropped
- FAQ add/edit text input being silently dropped
- Any FSM text input from admin/operator being lost

### Bugs Fixed
1. **No notifications about new tickets** — Added notification to all operators/admins when a ticket is created
2. **Taking ticket should start dialog immediately** — `take_ticket` now sets OperatorReply FSM state immediately
3. **Operator replies don't reach user** — Fixed by StateFilter(None) on handle_free_text
4. **FAQ add doesn't work** — Same root cause as #3
5. **FAQ edit already existed but was broken** — Same root cause as #3, now works
6. **User can't reply in active tickets** — Added full user reply flow with UserReply FSM state

### Files Modified
- `bot/handlers/user.py` — StateFilter(None), user reply, notifications, back_to_my_tickets
- `bot/handlers/operator.py` — take_ticket enters reply mode, send_reply shows actions
- `bot/states/ticket_states.py` — Added UserReply state
- `bot/keyboards/user.py` — Added get_user_ticket_detail_keyboard
- `services/ticket_service.py` — Status transitions based on sender role
