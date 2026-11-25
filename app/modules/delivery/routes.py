from flask import Blueprint, current_app, jsonify
from app.modules.runs.routes import archive
from .checks import verify
from .service import signing

delivery = Blueprint('delivery', __name__)


def bans(record):
    ledger = current_app.extensions['revocation_ledger']
    return ledger.bans(ledger.scope_of(record))


@delivery.get('/api/delivery/<key>')
def certificate(key):
    record = archive().read(key)
    return jsonify(verified=True, certificate=verify(record, bans(record)))


@delivery.get('/api/delivery/<key>/export')
def export(key):
    record = archive().read(key)
    response = jsonify(signing(record, bans(record)))
    response.headers['Content-Disposition'] = f'attachment; filename="caption-proof-{key}.json"'
    return response
