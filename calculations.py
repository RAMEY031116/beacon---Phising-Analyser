from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


def money(pence: int) -> str:
    pence = int(pence or 0)
    sign = '-' if pence < 0 else ''
    p = abs(pence)
    return f"{sign}£{p // 100:,}.{p % 100:02d}"


def to_pence(value) -> int:
    """Convert a pounds value to exact integer pence without float artefacts."""
    amount = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return int(amount * 100)


def week_bounds(day: date | None = None):
    day = day or date.today()
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def equal_split(amount_pence: int, member_ids: list[str]) -> dict[str, int]:
    """Split exactly, allocating any remainder pennies deterministically."""
    if not member_ids:
        return {}
    amount_pence = int(amount_pence)
    base, remainder = divmod(amount_pence, len(member_ids))
    return {
        member_id: base + (1 if idx < remainder else 0)
        for idx, member_id in enumerate(member_ids)
    }


def calculate_balances(
    members: list[dict],
    expenses: list[dict],
    splits_by_expense: dict[str, list[dict]],
    paid_settlements: list[dict],
) -> dict[str, int]:
    """
    Positive balance = should receive money.
    Negative balance = owes money.
    """
    balances = defaultdict(int)
    for member in members:
        balances[member['id']] += 0

    for expense in expenses:
        amount = int(expense['amount_pence'])
        payer_id = expense['paid_by_member_id']
        balances[payer_id] += amount
        for split in splits_by_expense.get(expense['id'], []):
            balances[split['member_id']] -= int(split['share_pence'])

    # A recorded payment moves both people toward zero.
    for settlement in paid_settlements:
        amount = int(settlement['amount_pence'])
        balances[settlement['from_member_id']] += amount
        balances[settlement['to_member_id']] -= amount

    return dict(balances)


def minimize_transfers(balances: dict[str, int]):
    creditors = [[member_id, amount] for member_id, amount in balances.items() if amount > 0]
    debtors = [[member_id, -amount] for member_id, amount in balances.items() if amount < 0]

    creditors.sort(key=lambda row: row[1], reverse=True)
    debtors.sort(key=lambda row: row[1], reverse=True)

    transfers = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor_id, owe = debtors[i]
        creditor_id, due = creditors[j]
        amount = min(owe, due)
        if amount > 0:
            transfers.append(
                {
                    'from_member_id': debtor_id,
                    'to_member_id': creditor_id,
                    'amount_pence': amount,
                }
            )
        debtors[i][1] -= amount
        creditors[j][1] -= amount
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return transfers
