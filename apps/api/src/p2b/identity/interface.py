"""Public interface of the identity module. Other modules import only this file."""

from p2b.identity.accounts import create_account_for
from p2b.identity.confirmations import (
    ConfirmationStarted,
    start_confirmation,
    verify_confirmation,
)
from p2b.identity.dependencies import require_actor
from p2b.identity.service import Actor, primary_emails
from p2b.identity.staff import active_roles

__all__ = [
    "Actor",
    "ConfirmationStarted",
    "active_roles",
    "create_account_for",
    "primary_emails",
    "require_actor",
    "start_confirmation",
    "verify_confirmation",
]
