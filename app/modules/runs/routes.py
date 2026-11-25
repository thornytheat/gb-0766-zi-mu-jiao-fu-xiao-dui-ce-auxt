from flask import Blueprint, current_app, jsonify, request
from app.material import material
from .service import record, summary

runs = Blueprint('revisions', __name__, url_prefix='/api/runs')


def archive():
    return current_app.extensions['cut_archive']


def ledger():
    return current_app.extensions['revocation_ledger']


@runs.get('')
def index():
    stamps = archive().inventory()
    return jsonify(count=len(stamps), rows=stamps)


@runs.post('')
def publish():
    return jsonify(record(archive(), material(request.get_json(silent=True)), ledger()))


@runs.get('/<key>')
def detail(key):
    return jsonify(summary(archive().read(key)))


@runs.post('/<key>/repeat')
def repeat(key):
    # Recompute exactly what was archived; a later withdrawal must not rewrite
    # an earlier version's evidence.
    return jsonify(record(archive(), archive().read(key)['original'], ledger(), honour=False))
