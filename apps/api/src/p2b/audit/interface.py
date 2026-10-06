"""Public interface of the audit module. Other modules import only this file."""

from p2b.audit.service import count_security_events, record, record_security_event

__all__ = ["count_security_events", "record", "record_security_event"]
