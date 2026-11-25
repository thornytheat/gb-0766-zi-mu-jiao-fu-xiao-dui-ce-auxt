from fractions import Fraction

from app.digests import digest, encode, fingerprints
from app.problems import Rejection


def verify(record, bans=None):
    stamp = record['manifest']
    if (fingerprints(record['original']) != stamp['input_sha256'] or
            digest(encode(record['stages'])) != stamp['result_sha256'] or
            not record['stages']['source']['counts']['balanced'] or
            not record['stages']['balance']['balanced']):
        raise Rejection('INVALID_EVIDENCE', '证据散列或覆盖勾稽不符', 409)
    if bans and blocked(record, bans):
        raise Rejection('WITHDRAWN', '该交付包含已撤回许可的源帧，请签发新包', 409)
    return stamp


def blocked(record, bans):
    """True when any delivered source frame of ``record`` lost its licence."""
    for row in record['stages']['edits']['rows']:
        if row['kind'] != 'KEEP':
            continue
        left, right = Fraction(row['start']), Fraction(row['end'])
        for cue_id, track, start, end in bans:
            if cue_id != row['cue_id'] or (track is not None and track != row['track']):
                continue
            if start < right and left < end:
                return True
    return False
