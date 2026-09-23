class LedgerError(Exception):
    """A problem with the transfer request itself — safe to show to the client as a 400.

    `code` is a stable identifier used as a metric label and log field, so those don't
    depend on class names that might be renamed."""

    code = "ledger_error"


class SameWalletError(LedgerError):
    code = "same_wallet"


class CurrencyMismatchError(LedgerError):
    code = "currency_mismatch"


class InsufficientFundsError(LedgerError):
    code = "insufficient_funds"


class LedgerIntegrityError(Exception):
    """A transaction's entries didn't sum to zero. This means a bug in this code, not a
    bad request — deliberately NOT a LedgerError subclass, so it surfaces as a 500
    instead of being shown to the client as if it were their mistake."""
