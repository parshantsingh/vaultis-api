class LedgerError(Exception):
    """A problem with the transfer request itself — safe to show to the client as a 400."""


class SameWalletError(LedgerError):
    pass


class CurrencyMismatchError(LedgerError):
    pass


class InsufficientFundsError(LedgerError):
    pass


class LedgerIntegrityError(Exception):
    """A transaction's entries didn't sum to zero. This means a bug in this code, not a
    bad request — deliberately NOT a LedgerError subclass, so it surfaces as a 500
    instead of being shown to the client as if it were their mistake."""
