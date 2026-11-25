from bisect import bisect_right
from fractions import Fraction
from math import ceil

from app.modules.clock.timecode import RATIO
from app.modules.licensing.service import ranges_for
from app.rational import show


def map_cues(cues, edit_list, withdrawals=None):
    endpoints = [edit['end'] for edit in edit_list]
    fragments = []
    for cue in cues:
        cursor, end = Fraction(cue['start']), Fraction(cue['end'])
        banned = ranges_for(withdrawals, cue['cue_id'], cue['track']) if withdrawals else []
        for edit in edit_list[bisect_right(endpoints, cursor):]:
            if edit['start'] >= end:
                break
            left, right = max(cursor, edit['start']), min(end, edit['end'])
            if cursor < left:
                fragments.append(fragment(cue, cursor, left, None))
            if edit['kind'] != 'KEEP' or not banned:
                fragments.append(fragment(cue, left, right, edit))
            else:
                fragments.extend(licensed(cue, left, right, edit, banned))
            cursor = right
        if cursor < end:
            fragments.append(fragment(cue, cursor, end, None))
    counts = {kind: sum(row['kind'] == kind for row in fragments) for kind in ('KEEP', 'REMOVE', 'GAP')}
    banned = sum(row['kind'] == 'WITHDRAWN' for row in fragments)
    if banned:
        counts['WITHDRAWN'] = banned
    return dict(rows=fragments, cuts=edit_list, counts=counts)


def licensed(cue, start, end, edit, banned):
    """Split a kept or pending fragment on the withdrawn source frames."""
    cursor = start
    for left, right in banned:
        if right <= cursor or left >= end:
            continue
        left, right = max(left, cursor), min(right, end)
        if cursor < left:
            yield fragment(cue, cursor, left, edit)
        yield fragment(cue, left, right, edit, banned=True)
        cursor = right
    if cursor < end:
        yield fragment(cue, cursor, end, edit)


def fragment(cue, start, end, edit, banned=False):
    kind = edit['kind'] if edit else 'GAP'
    if banned:
        kind = 'WITHDRAWN'
    result = dict(cue_id=cue['cue_id'], track=cue['track'], line=cue['line'], text=cue['text'],
                  start=show(start), end=show(end), kind=kind, cut=edit['cut'] if edit else None,
                  cut_line=edit['line'] if edit else None)
    if kind in ('KEEP', 'WITHDRAWN') and edit:
        left = edit['target'] + (start - edit['start']) * RATIO
        right = edit['target'] + (end - edit['start']) * RATIO
        result.update(target_start=show(left), target_end=show(right), frame_in=ceil(left), frame_out=ceil(right))
    return result
