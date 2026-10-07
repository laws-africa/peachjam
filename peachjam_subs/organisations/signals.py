from django.dispatch import Signal

organisation_invitation_accepted = Signal()
organisation_seat_assigned = Signal()
organisation_seat_released = Signal()
organisation_seat_plan_changed = Signal()
organisation_billing_recipients_changed = Signal()
organisation_ownership_transferred = Signal()
