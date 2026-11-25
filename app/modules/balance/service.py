from fractions import Fraction

from app.rational import show
from .coverage import overlapped, union_length


def balance(cues, mapped, overlaps, rejected):
    total = dict(original=Fraction(0), delivered=Fraction(0), removed=Fraction(0),
                 pending=Fraction(0), withdrawn=Fraction(0))
    rows = []
    for track in sorted({row['track'] for row in cues}):
        pieces = [row for row in mapped if row['track'] == track]
        exact = dict(original=union_length([row for row in cues if row['track'] == track]))
        for name, kind in [('delivered', 'KEEP'), ('removed', 'REMOVE'),
                           ('pending', 'GAP'), ('withdrawn', 'WITHDRAWN')]:
            exact[name] = union_length([row for row in pieces if row['kind'] == kind])
        # A banned frame still carried by another licensed cue stays in that
        # licensed bucket; only frames no other bucket covers are withdrawn.
        exact['withdrawn'] = overlapped([row for row in pieces if row['kind'] == 'WITHDRAWN'],
                                        [row for row in pieces if row['kind'] != 'WITHDRAWN'])
        for name, number in exact.items():
            total[name] += number
        row = {name: show(value) for name, value in exact.items()}
        if not exact['withdrawn']:
            row.pop('withdrawn')
        rows.append(dict(track=track, **row))
    gap = total['original'] - total['delivered'] - total['removed'] - total['pending'] - total['withdrawn']
    counts = {name: show(value) for name, value in total.items() if name != 'withdrawn'}
    counts.update(rejected_unmeasurable=rejected, overlap_target_frames=overlaps)
    if total['withdrawn']:
        counts['withdrawn'] = show(total['withdrawn'])
    return dict(rows=rows, counts=counts, balanced=gap == 0, difference=show(gap))
