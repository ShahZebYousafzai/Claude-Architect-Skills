"""Exceptions raised by the Northwind backend (Session 4).

A real order system does not return friendly dicts when it fails. It raises: the
network times out, a lookup finds nothing, a policy says no, a credential lacks a
scope. These classes are what our mock backend raises, so the tool layer you build
in the Session 4 notebook can translate each one into a STRUCTURED error that
Claude can act on.

Exception            -> errorCategory   -> default isRetryable
ServiceTimeout       -> transient       -> True   (same call may work a moment later)
InvalidInput         -> validation      -> False  (fix the input or ask the customer)
NotFound             -> validation      -> False  (the ID does not exist; retrying won't create it)
PolicyViolation      -> business        -> False  (a rule says no; explain, offer the alternative)
PermissionDenied     -> permission      -> False  (this agent/credential may not do this; hand off)

Note: "not found" for an ID the customer typed is a validation problem. An EMPTY
result for a valid query (a customer with no orders) is not an error at all.
"""


class NorthwindError(Exception):
    """Base class. `details` carries machine-readable context for the error payload."""

    def __init__(self, message, **details):
        super().__init__(message)
        self.message = message
        self.details = details


class ServiceTimeout(NorthwindError):
    """A downstream service did not answer in time. Usually fine a moment later."""


class InvalidInput(NorthwindError):
    """The call itself is malformed: wrong format, missing field, impossible value."""


class NotFound(NorthwindError):
    """A well-formed identifier that does not exist."""


class PolicyViolation(NorthwindError):
    """A business rule forbids the action. Has a code and a customer-safe explanation."""

    def __init__(self, message, *, code, customer_message, **details):
        super().__init__(message, code=code, **details)
        self.code = code
        self.customer_message = customer_message


class PermissionDenied(NorthwindError):
    """The caller (agent role or service credential) is not allowed to do this."""
