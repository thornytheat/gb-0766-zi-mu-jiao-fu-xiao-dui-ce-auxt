from .modules.licensing.service import normalize
from .problems import Rejection
from .settings import SAMPLE_ROOT

ALIASES = ('withdrawals', 'withdraw', 'revocations')


def example(name):
    if name not in ('dirty', 'clean'):
        raise Rejection('NO_SAMPLE', '找不到交付样例', 404)
    root = SAMPLE_ROOT / name
    return {field: (root / f'{field}.csv').read_bytes().decode() for field in ('cues', 'cuts')}


def _withdrawals(body):
    present = [key for key in ALIASES if key in body]
    if not present:
        return None
    if len(present) > 1:
        raise Rejection('PAYLOAD', '请只提交一份撤回清单')
    payload = body[present[0]]
    if payload is None or (isinstance(payload, str) and not payload.strip()):
        return None
    return normalize(payload)


def material(body):
    if not isinstance(body, dict):
        raise Rejection('PAYLOAD', '提交字幕和切版 CSV')
    keys = set(body)
    if 'sample' in body and isinstance(body['sample'], str) and keys <= {'sample', *ALIASES}:
        files = example(body['sample'])
    elif {'cues', 'cuts'} <= keys and keys <= {'cues', 'cuts', *ALIASES} and all(
            isinstance(body[key], str) for key in ('cues', 'cuts')):
        files = {'cues': body['cues'], 'cuts': body['cuts']}
    else:
        raise Rejection('PAYLOAD', '提交字幕和切版 CSV')
    withdrawals = _withdrawals(body)
    if withdrawals:
        files['withdrawals'] = withdrawals
    return files
