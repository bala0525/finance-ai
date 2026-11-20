import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from openpyxl import load_workbook


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _amount(value: Any) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None

    try:
        cleaned = str(value).replace(",", "").replace("$", "").strip()
        result = Decimal(cleaned)
        return abs(result)
    except (InvalidOperation, ValueError):
        return None


def _normalise(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", _text(value).lower())


def _reference(value: Any) -> str | None:
    text = _text(value).lower()
    patterns = [
        r"(?:cheque|check|ch\.?\s*no\.?|ch\.?\s*#|ref(?:erence)?\s*#?)\s*0*(\d+)",
        r"#\s*0*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    # Workbook examples commonly place the cheque number at the end.
    match = re.search(r"\b0*(\d{4,})\b", text)
    return match.group(1) if match else None


def _find_header(sheet, required_words: set[str], limit: int = 30):
    for row_index in range(1, min(sheet.max_row, limit) + 1):
        values = [
            _text(sheet.cell(row_index, col).value).lower()
            for col in range(1, sheet.max_column + 1)
        ]
        present = set(values)

        if all(any(word in cell for cell in values) for word in required_words):
            return row_index, values

    return None, []


def _read_cashbook(sheet) -> list[dict]:
    header_row = None

    for row_index in range(1, min(sheet.max_row, 30) + 1):
        row_values = [
            _text(sheet.cell(row_index, col).value).lower()
            for col in range(1, sheet.max_column + 1)
        ]
        if (
            any(value == "date" for value in row_values)
            and any("details" in value for value in row_values)
            and any("amount" in value for value in row_values)
        ):
            header_row = row_index
            break

    if header_row is None:
        raise ValueError("Could not find the Cashbook table header.")

    headers = [
        _text(sheet.cell(header_row, col).value).lower()
        for col in range(1, sheet.max_column + 1)
    ]

    # The supplied workbook has Debit and Credit blocks side-by-side.
    date_columns = [i for i, value in enumerate(headers) if value == "date"]
    detail_columns = [
        i for i, value in enumerate(headers)
        if "details" in value or "particulars" in value
    ]
    amount_columns = [
        i for i, value in enumerate(headers) if "amount" in value
    ]

    if len(date_columns) < 2 or len(detail_columns) < 2 or len(amount_columns) < 2:
        raise ValueError(
            "Cashbook must contain separate debit and credit date/details/amount columns."
        )

    transactions = []

    for row_index in range(header_row + 1, sheet.max_row + 1):
        for side_index, side in enumerate(("DEBIT", "CREDIT")):
            date_col = date_columns[side_index] + 1
            detail_col = detail_columns[side_index] + 1
            amount_col = amount_columns[side_index] + 1

            raw_date = sheet.cell(row_index, date_col).value
            description = _text(sheet.cell(row_index, detail_col).value)
            amount = _amount(sheet.cell(row_index, amount_col).value)

            if not description or amount is None:
                continue

            transactions.append({
                "source": "CASHBOOK",
                "row": row_index,
                "date": _json_value(raw_date),
                "description": description,
                "amount": float(amount),
                "direction": side,
                "reference": _reference(description),
            })

    if not transactions:
        raise ValueError("No Cashbook transactions were found.")

    return transactions


def _read_bank_statement(sheet) -> list[dict]:
    header_row = None
    headers = []

    for row_index in range(1, min(sheet.max_row, 30) + 1):
        row_values = [
            _text(sheet.cell(row_index, col).value).lower()
            for col in range(1, sheet.max_column + 1)
        ]

        has_date = any(value == "date" for value in row_values)
        has_description = any(
            "particular" in value or "description" in value
            for value in row_values
        )
        has_amount_side = any(
            value == "debit" for value in row_values
        ) and any(value == "credit" for value in row_values)

        if has_date and has_description and has_amount_side:
            header_row = row_index
            headers = row_values
            break

    if header_row is None:
        raise ValueError("Could not find the Bank Statement table header.")

    date_col = next(i for i, value in enumerate(headers) if value == "date")
    description_col = next(
        i for i, value in enumerate(headers)
        if "particular" in value or "description" in value
    )
    debit_col = next(i for i, value in enumerate(headers) if value == "debit")
    credit_col = next(i for i, value in enumerate(headers) if value == "credit")

    transactions = []

    for row_index in range(header_row + 1, sheet.max_row + 1):
        raw_date = sheet.cell(row_index, date_col + 1).value
        description = _text(
            sheet.cell(row_index, description_col + 1).value
        )
        debit = _amount(sheet.cell(row_index, debit_col + 1).value)
        credit = _amount(sheet.cell(row_index, credit_col + 1).value)

        if not description:
            continue

        if debit is not None and debit > 0:
            transactions.append({
                "source": "BANK_STATEMENT",
                "row": row_index,
                "date": _json_value(raw_date),
                "description": description,
                "amount": float(debit),
                "direction": "DEBIT",
                "reference": _reference(description),
            })

        if credit is not None and credit > 0:
            transactions.append({
                "source": "BANK_STATEMENT",
                "row": row_index,
                "date": _json_value(raw_date),
                "description": description,
                "amount": float(credit),
                "direction": "CREDIT",
                "reference": _reference(description),
            })

    if not transactions:
        raise ValueError("No Bank Statement transactions were found.")

    return transactions


def _match_transactions(cashbook: list[dict], bank: list[dict]) -> dict:
    matches = []
    unmatched_cashbook = []
    unmatched_bank = []
    used_bank_rows: set[int] = set()

    for cash_tx in cashbook:
        candidates = []

        for bank_index, bank_tx in enumerate(bank):
            if bank_index in used_bank_rows:
                continue

            if abs(cash_tx["amount"] - bank_tx["amount"]) > 0.005:
                continue

            cash_ref = cash_tx.get("reference")
            bank_ref = bank_tx.get("reference")

            cash_desc = _normalise(cash_tx["description"])
            bank_desc = _normalise(bank_tx["description"])

            same_reference = (
                cash_ref is not None
                and bank_ref is not None
                and cash_ref == bank_ref
            )
            description_overlap = (
                cash_desc in bank_desc or bank_desc in cash_desc
            ) if cash_desc and bank_desc else False

            if same_reference:
                candidates.append((bank_index, "AMOUNT_AND_REFERENCE"))
            elif description_overlap:
                candidates.append((bank_index, "AMOUNT_AND_DESCRIPTION"))

        if len(candidates) == 1:
            bank_index, match_method = candidates[0]
            used_bank_rows.add(bank_index)

            matches.append({
                "cashbook": cash_tx,
                "bankStatement": bank[bank_index],
                "matchMethod": match_method,
                "amountDifference": 0.0,
            })
        elif len(candidates) > 1:
            unmatched_cashbook.append({
                **cash_tx,
                "reason": "AMBIGUOUS_MATCH",
            })
        else:
            unmatched_cashbook.append({
                **cash_tx,
                "reason": "NO_EXACT_AMOUNT_AND_REFERENCE_OR_DESCRIPTION_MATCH",
            })

    for bank_index, bank_tx in enumerate(bank):
        if bank_index not in used_bank_rows:
            unmatched_bank.append({
                **bank_tx,
                "reason": "NO_MATCHING_CASHBOOK_TRANSACTION",
            })

    return {
        "matched": matches,
        "unmatchedCashbook": unmatched_cashbook,
        "unmatchedBankStatement": unmatched_bank,
    }


def reconcile_workbook(content: bytes, extension: str) -> dict:
    if extension.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError(
            "Reconciliation currently supports .xlsx and .xlsm files."
        )

    workbook = load_workbook(
        BytesIO(content),
        read_only=True,
        data_only=True,
    )

    try:
        if "Company Cashbook" not in workbook.sheetnames:
            raise ValueError("Worksheet 'Company Cashbook' was not found.")

        if "Bank Statement" not in workbook.sheetnames:
            raise ValueError("Worksheet 'Bank Statement' was not found.")

        cashbook = _read_cashbook(workbook["Company Cashbook"])
        bank = _read_bank_statement(workbook["Bank Statement"])
        result = _match_transactions(cashbook, bank)

        summary = {
            "cashbookTransactionCount": len(cashbook),
            "bankTransactionCount": len(bank),
            "matchedCount": len(result["matched"]),
            "unmatchedCashbookCount": len(result["unmatchedCashbook"]),
            "unmatchedBankCount": len(result["unmatchedBankStatement"]),
            "status": (
                "REVIEW_REQUIRED"
                if result["unmatchedCashbook"] or result["unmatchedBankStatement"]
                else "MATCHED"
            ),
            "matchingPolicy": (
                "Exact amount plus a unique matching reference or description. "
                "Ambiguous matches remain unmatched."
            ),
        }

        return {
            "summary": summary,
            "results": result,
        }
    finally:
        workbook.close()
