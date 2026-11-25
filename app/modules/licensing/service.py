from csv import Error as CSVError, reader
from fractions import Fraction
from io import StringIO

from app.digests import encode, digest
from app.problems import Rejection


def _frame(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise Rejection('WITHDRAWAL', '撤回帧号必须是整数或分数')
    try:
        number = Fraction(value.strip() if isinstance(value, str) else value)
    except (ValueError, ZeroDivisionError) as error:
        raise Rejection('WITHDRAWAL', '撤回帧号无法解析') from error
    if number < 0:
        raise Rejection('WITHDRAWAL', '撤回帧号不能为负')
    return number


def _range(item):
    if isinstance(item, dict):
        if set(item) != {'start', 'end'}:
            raise Rejection('WITHDRAWAL', '撤回区间需要 start 和 end')
        left, right = item['start'], item['end']
    elif isinstance(item, (list, tuple)) and len(item) == 2:
        left, right = item
    else:
        raise Rejection('WITHDRAWAL', '撤回区间应为 [start, end)')
    start, end = _frame(left), _frame(right)
    if start >= end:
        raise Rejection('WITHDRAWAL', '撤回区间必须左闭右开且非空')
    return start, end


def _merge_ranges(ranges):
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _entries(payload):
    if isinstance(payload, str):
        payload = _csv_entries(payload)
    if isinstance(payload, dict) and set(payload) == {'withdrawals'}:
        payload = payload['withdrawals']
    if isinstance(payload, dict) and payload and all(isinstance(value, list) for value in payload.values()) \
            and not ({'cue_id', 'cue', 'track', 'ranges', 'frames', 'segments', 'start', 'end'} & set(payload)):
        # {"C113": [[1255, 1290]], ...} shorthand.
        payload = [dict(cue_id=cue_id, ranges=ranges) for cue_id, ranges in payload.items()]
    if payload == []:
        return []
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not payload:
        raise Rejection('WITHDRAWAL', '请提交撤回的字幕号与源帧区间')
    return payload


def _csv_entries(text):
    try:
        rows = [row for row in reader(StringIO(text.removeprefix('﻿')), skipinitialspace=True)]
    except CSVError as error:
        raise Rejection('WITHDRAWAL', '撤回清单 CSV 损坏') from error
    rows = [[value.strip() for value in row] for row in rows if any(value.strip() for value in row)]
    if not rows:
        raise Rejection('WITHDRAWAL', '撤回清单为空')
    header = [value.lower() for value in rows[0]]
    if 'cue_id' not in header or 'start' not in header or 'end' not in header:
        raise Rejection('WITHDRAWAL', '撤回表头需要 cue_id,start,end')
    entries = []
    for row in rows[1:]:
        if len(row) != len(header):
            raise Rejection('WITHDRAWAL', '撤回表列数不符')
        value = dict(zip(header, row))
        entries.append(dict(cue_id=value['cue_id'], start=value['start'], end=value['end'],
                            **({'track': value['track']} if value.get('track') else {})))
    return entries


def normalize(payload):
    """Normalize a withdrawal payload to a deterministic, sorted ledger shape.

    One entry is ``{"cue_id": ..., "track": optional, "ranges": [["a","b"], ...]}``.
    Ranges are source frames and half-open.  Equivalent submissions collapse to
    the same value so a repeated withdrawal can never sign a second package.
    """
    grouped = {}
    for entry in _entries(payload):
        if not isinstance(entry, dict):
            raise Rejection('WITHDRAWAL', '每条撤回应为字幕对象')
        extra = set(entry) - {'cue_id', 'cue', 'track', 'ranges', 'frames', 'segments', 'start', 'end'}
        if extra:
            raise Rejection('WITHDRAWAL', f"撤回字段无效: {sorted(extra)[0]}")
        cue_id = entry.get('cue_id', entry.get('cue'))
        if not isinstance(cue_id, str) or not cue_id.strip():
            raise Rejection('WITHDRAWAL', '撤回需要字幕号')
        cue_id = cue_id.strip()
        track = entry.get('track')
        if track is not None and (not isinstance(track, str) or not track.strip()):
            raise Rejection('WITHDRAWAL', '轨道名无效')
        track = track.strip() if track is not None else None
        raw = entry.get('ranges', entry.get('frames', entry.get('segments')))
        if raw is None and 'start' in entry and 'end' in entry:
            raw = [[entry['start'], entry['end']]]
        if not isinstance(raw, list) or not raw:
            raise Rejection('WITHDRAWAL', '撤回需要源帧区间')
        ranges = [(start, end) for start, end in map(_range, raw)]
        grouped.setdefault((cue_id, track), []).extend(ranges)
    result = []
    for (cue_id, track), ranges in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1] or '')):
        value = {'cue_id': cue_id}
        if track is not None:
            value['track'] = track
        value['ranges'] = [[str(start), str(end)] for start, end in _merge_ranges(ranges)]
        result.append(value)
    return result


def merge(*groups):
    """Combine already-normalized withdrawal lists, merging per cue and range."""
    grouped = {}
    for group in groups:
        for entry in group or []:
            grouped.setdefault((entry['cue_id'], entry.get('track')),
                               []).extend((Fraction(start), Fraction(end)) for start, end in entry['ranges'])
    result = []
    for (cue_id, track), ranges in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1] or '')):
        value = {'cue_id': cue_id}
        if track is not None:
            value['track'] = track
        value['ranges'] = [[str(start), str(end)] for start, end in _merge_ranges(ranges)]
        result.append(value)
    return result


def materialize(withdrawals):
    """Turn ledger ranges back into Fractions."""
    return [(entry['cue_id'], entry.get('track'),
             [(Fraction(start), Fraction(end)) for start, end in entry['ranges']])
            for entry in withdrawals or []]


def ranges_for(withdrawals, cue_id, track):
    spans = []
    for entry_id, entry_track, ranges in materialize(withdrawals):
        if entry_id == cue_id and (entry_track is None or entry_track == track):
            spans.extend(ranges)
    return _merge_ranges(spans)


def relevant(withdrawals, cues):
    """Keep only withdrawals naming a cue that was actually accepted."""
    known = {(cue['cue_id'], cue['track']) for cue in cues}
    kept = [entry for entry in withdrawals or []
            if any(cue_id == entry['cue_id'] and (entry.get('track') is None or entry['track'] == track)
                   for cue_id, track in known)]
    return merge(kept)


def identities(source):
    """Every subtitle number the source file mentions, accepted or not.

    A withdrawal may legitimately name a cue that ended up isolated (conflict,
    bad timecode, missing field): those frames were never delivered, so the
    withdrawal is harmless but must not be mistaken for a typo.
    """
    seen = set()
    for bucket in ('rows', 'isolated', 'copies'):
        for row in source.get(bucket, []):
            if isinstance(row.get('cue_id'), str) and row['cue_id'].strip():
                seen.add(row['cue_id'].strip())
    return seen


def covers(withdrawals, known):
    """Reject a withdrawal that names no subtitle in the source file at all."""
    missing = [entry['cue_id'] for entry in withdrawals if entry['cue_id'] not in known]
    if missing:
        raise Rejection('NO_CUE', f"撤回的字幕不在原件内: {missing[0]}", 422)


def digest_of(withdrawals):
    """Stable hash of a normalized withdrawal list."""
    return digest(encode(['withdrawal', withdrawals]))
