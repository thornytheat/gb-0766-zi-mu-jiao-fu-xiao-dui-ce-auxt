from datetime import datetime, timezone
from time import perf_counter_ns

from app.digests import digest, encode, fingerprints
from app.modules.licensing.service import covers, digest_of, identities, merge, relevant
from app.modules.source.service import receive
from app.pipeline import inspect
from app.problems import Rejection
from app.settings import VERSION

WITHDRAWAL_FIELDS = ('withdrawals', 'withdraw', 'revocations')


def record(store, material, ledger=None, honour=True):
    """Sign a package and archive it.

    ``honour`` applies every withdrawal still on the ledger for this reel (a
    fresh submission must respect all licences currently in force).  A
    recomputation of an already archived version sets it false so it reproduces
    exactly what was filed.
    """
    start = perf_counter_ns()
    submitted = next((material[key] for key in WITHDRAWAL_FIELDS if material.get(key)), [])
    source = receive(material['cues'])
    scope = ledger.scope(source['rows']) if ledger is not None else None
    if submitted:
        covers(submitted, identities(source))
        # Persist the revocation before computing anything: if signing the new
        # package fails, the old package must already be barred from download.
        # Registering is keyed by content, so a retry is a no-op.
        if ledger is not None:
            ledger.register(scope, submitted)
    inherited = ledger.all(scope) if ledger is not None and honour else []
    effective = relevant(merge(inherited, submitted), source['rows'])
    signed = dict(material, withdrawals=effective) if effective else \
        {name: text for name, text in material.items() if name not in WITHDRAWAL_FIELDS}
    stages = inspect(signed)
    if effective and 'WITHDRAWN' not in stages['edits']['counts']:
        # Nothing still broadcast lost its licence (the ban fell only on
        # removed or ungated frames), so the earlier package still stands.
        signed = {name: text for name, text in material.items() if name not in WITHDRAWAL_FIELDS}
        stages = inspect(signed)
        effective = []
    hashes = fingerprints(signed)
    key = digest(encode([VERSION, hashes]))
    result_hash = digest(encode(stages))
    manifest = dict(id=key, version=VERSION, input_sha256=hashes, result_sha256=result_hash,
                    created_at=datetime.now(timezone.utc).isoformat(), elapsed_us=(perf_counter_ns() - start) // 1000)
    if effective:
        manifest['withdrawal_sha256'] = digest_of(effective)
    actual, reused = store.publish(key, dict(manifest=manifest, original=signed, stages=stages))
    if actual['manifest']['result_sha256'] != result_hash or digest(encode(actual['stages'])) != result_hash:
        raise Rejection('DRIFT', '复算与已归档结果不一致', 409)
    return dict(summary(actual), reused=reused)


def summary(record):
    return dict(id=record['manifest']['id'], manifest=record['manifest'], counts=record['stages']['balance']['counts'])
