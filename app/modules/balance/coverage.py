from fractions import Fraction

from app.modules.overlaps.sweep import spans


def union_length(rows):
    intervals = [(Fraction(row['start']), Fraction(row['end']), index) for index, row in enumerate(rows)]
    return sum((right-left for left, right, _ in spans(intervals)), start=Fraction(0))


def merge(intervals):
    merged = []
    for left, right in sorted((left, right) for left, right in intervals if left < right):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    return merged


def overlapped(one, other):
    """Length of the union of ``one`` minus the union of ``other``.

    Used to keep the withdrawal bucket disjoint from the licensed buckets: a
    banned source frame that another licensed cue still covers stays counted
    as delivered, so the source ledger still balances.
    """
    blocked = merge((Fraction(row['start']), Fraction(row['end'])) for row in other)
    total = Fraction(0)
    for left, right in merge((Fraction(row['start']), Fraction(row['end'])) for row in one):
        cursor = left
        for b_left, b_right in blocked:
            if b_right <= cursor or b_left >= right:
                continue
            if cursor < b_left:
                total += b_left - cursor
            cursor = max(cursor, b_right)
            if cursor >= right:
                break
        if cursor < right:
            total += right - cursor
    return total
