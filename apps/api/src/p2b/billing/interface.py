"""Public interface of the billing module. Other modules import only this file. Billing knows
nothing of professionals or construction (import-linter): it sells the package and AI credits,
never construction work."""

from p2b.billing.configuration import offer_published
from p2b.billing.credits import consume_credit, credit_balance, return_credit
from p2b.billing.entitlements import package_active, package_state, record_service_usage

__all__ = [
    "consume_credit",
    "credit_balance",
    "offer_published",
    "package_active",
    "package_state",
    "record_service_usage",
    "return_credit",
]
