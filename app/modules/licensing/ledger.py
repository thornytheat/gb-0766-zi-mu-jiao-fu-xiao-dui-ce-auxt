import json
import os
from fractions import Fraction
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.digests import encode, digest
from .service import merge


class RevocationLedger:
    """Append-only register of withdrawn source frames.

    Entries are scoped to the accepted subtitle line-up of the reel they were
    filed against, so a withdrawal never blocks an unrelated reel that happens
    to reuse a subtitle number.  The scope is derived from cue identity and
    timecode, not raw file bytes, so re-exporting the same sheet under a
    different line ending still matches.

    A withdrawal is durable before any new package is signed, so a failed
    re-sign still leaves the old package blocked.  Filenames are the digest of
    the scope and the normalized withdrawal, so retrying the same revocation is
    a no-op and never signs a second package.
    """

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def scope(cues):
        identity = sorted((cue['cue_id'], cue['track'], cue['format'], cue['in'], cue['out'], cue['text'])
                          for cue in cues)
        return digest(encode(['reel', identity]))

    def scope_of(self, record):
        return self.scope(record['stages']['source']['rows'])

    def key(self, scope, withdrawals):
        return digest(encode(['withdrawal', scope, withdrawals]))

    def register(self, scope, withdrawals):
        key = self.key(scope, withdrawals)
        path = self.root / f'{key}.json'
        if path.exists():
            return key, False
        with NamedTemporaryFile(dir=self.root, prefix='.draft-', delete=False) as draft:
            draft_path = Path(draft.name)
            try:
                draft.write(encode(dict(id=key, scope=scope, withdrawals=withdrawals)))
                draft.flush()
                os.fsync(draft.fileno())
                try:
                    os.link(draft_path, path)
                except FileExistsError:
                    return key, False
            finally:
                draft_path.unlink(missing_ok=True)
        self._sync()
        return key, True

    def _sync(self):
        descriptor = os.open(self.root, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def entries(self, scope=None):
        result = []
        for file in sorted(self.root.glob('*.json')):
            try:
                values = json.loads(file.read_bytes())
            except (OSError, ValueError):
                continue
            if not (isinstance(values, dict) and isinstance(values.get('withdrawals'), list)):
                continue
            if scope is not None and values.get('scope') != scope:
                continue
            result.append(values)
        return result

    def all(self, scope=None):
        return merge(*[entry['withdrawals'] for entry in self.entries(scope)])

    def bans(self, scope=None):
        bans = []
        for entry in self.entries(scope):
            for value in entry['withdrawals']:
                for start, end in value['ranges']:
                    bans.append((value['cue_id'], value.get('track'), Fraction(start), Fraction(end)))
        return bans
