"""Pure accounting validation and statement arithmetic."""
from decimal import Decimal


def validate_balanced_journal(lines):
    if len(lines) < 2:
        raise ValueError("A journal must contain at least two lines.")
    debit = Decimal("0")
    credit = Decimal("0")
    for line in lines:
        d = Decimal(str(line.get("debit", "0")))
        c = Decimal(str(line.get("credit", "0")))
        if d < 0 or c < 0 or (d > 0 and c > 0) or (d == 0 and c == 0):
            raise ValueError("Each journal line must have one positive debit or credit only.")
        debit += d
        credit += c
    if debit <= 0 or debit != credit:
        raise ValueError("Journal debit and credit totals must be equal and greater than zero.")
    return debit, credit


def normal_balance(account_type: str) -> str:
    return "DEBIT" if account_type.upper() in {"ASSET", "EXPENSE"} else "CREDIT"


def account_balance(account_type: str, debit: Decimal, credit: Decimal) -> Decimal:
    return debit - credit if normal_balance(account_type) == "DEBIT" else credit - debit
