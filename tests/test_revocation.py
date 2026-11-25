from app.material import example
from app.modules.licensing.ledger import RevocationLedger


def bid(cue_id, start, end):
    return {'cue_id': cue_id, 'ranges': [[start, end]]}


def sign(client, **extra):
    return client.post('/api/runs', json={'sample': 'dirty', **extra})


def download(client, key):
    return client.get(f"/api/delivery/{key}/export")


def test_new_package_is_signed(client):
    old = sign(client).json
    new = sign(client, withdrawals=[bid('C104', '1800', '1810')]).json
    assert new['id'] != old['id'] and not new['reused']
    assert new['counts']['withdrawn'] == '10'
    assert download(client, new['id']).status_code == 200


def test_old_package_stops_downloading(client):
    old = sign(client).json
    sign(client, withdrawals=[bid('C104', '1800', '1810')])
    response = download(client, old['id'])
    assert (response.status_code, response.json['code']) == (409, 'WITHDRAWN')
    assert client.get(f"/api/delivery/{old['id']}").json['code'] == 'WITHDRAWN'


def test_banned_frames_only_on_cut_footage_keep_old_package(client):
    old = sign(client).json
    result = sign(client, withdrawals=[bid('C101', '1000', '1200')]).json
    assert result['id'] == old['id'] and result['reused']
    assert download(client, old['id']).status_code == 200
    assert client.get('/api/runs').json['count'] == 1


def test_banned_frames_only_in_pending_gap_keep_old_package(client):
    old = sign(client).json
    result = sign(client, withdrawals=[bid('C103', '2000', '2200')]).json
    assert result['id'] == old['id']
    assert download(client, old['id']).status_code == 200


def test_retry_after_failed_signing_is_idempotent(client):
    old = sign(client).json
    broken = dict(example('dirty'), cuts='cut,start,end,target,kind\nA,1,100,0,KEEP\nB,99,110,,REMOVE\n')
    broken['withdrawals'] = [bid('C104', '1800', '1810')]
    assert client.post('/api/runs', json=broken).json['code'] == 'CUT_OVERLAP'
    # The revocation landed even though the new package did not.
    assert download(client, old['id']).json['code'] == 'WITHDRAWN'
    good = dict(example('dirty'), withdrawals=[bid('C104', '1800', '1810')])
    first = client.post('/api/runs', json=good).json
    second = client.post('/api/runs', json=good).json
    assert (first['reused'], second['reused']) == (False, True)
    assert first['id'] == second['id']
    assert client.get('/api/runs').json['count'] == 2
    assert len(tuple(client.application.extensions['revocation_ledger'].root.iterdir())) == 1
    assert download(client, first['id']).status_code == 200
    assert download(client, old['id']).json['code'] == 'WITHDRAWN'


def test_withdrawal_is_not_replayed_into_downloadable_cut_footage(client):
    sign(client, withdrawals=[bid('C104', '1800', '1810')])
    again = sign(client).json
    # A later package without the withdrawal still honours the live ban.
    assert again['counts']['withdrawn'] == '10'
    assert download(client, again['id']).status_code == 200


def test_other_reel_with_same_cue_id_is_unaffected(client):
    dirty = sign(client).json
    clean = client.post('/api/runs', json={'sample': 'clean'}).json
    sign(client, withdrawals=[bid('C104', '1800', '1810')])
    assert download(client, clean['id']).status_code == 200
    assert download(client, dirty['id']).json['code'] == 'WITHDRAWN'


def test_repeat_reproduces_archived_version(client):
    old = sign(client).json
    sign(client, withdrawals=[bid('C104', '1800', '1810')])
    result = client.post(f"/api/runs/{old['id']}/repeat").json
    assert result['reused'] and result['manifest'] == old['manifest']


def test_withdrawal_of_unknown_cue_never_signs(client):
    old = sign(client).json
    response = sign(client, withdrawals=[bid('C999', '1', '2')])
    assert (response.status_code, response.json['code']) == (422, 'NO_CUE')
    assert client.get('/api/runs').json['count'] == 1
    assert download(client, old['id']).status_code == 200


def test_delivery_page_reports_withdrawal(client):
    old = sign(client).json
    sign(client, withdrawals=[bid('C104', '1800', '1810')])
    page = client.get(f"/sheet/delivery?run={old['id']}")
    assert (page.status_code, '该交付包含已撤回许可的源帧' in page.get_data(as_text=True)) == (409, True)


def test_ledger_scope_separates_reels(tmp_path):
    ledger = RevocationLedger(tmp_path)
    cue = dict(cue_id='C1', track='t', format='FRAME', **{'in': '0', 'out': '5'}, text='a')
    other = dict(cue, cue_id='C2')
    one, two = RevocationLedger.scope([cue]), RevocationLedger.scope([other])
    ledger.register(one, [bid('C1', '0', '5')])
    assert ledger.all(one) and not ledger.all(two)


def test_withdrawals_json_shorthand(client):
    new = sign(client, withdrawals={'C104': [['1800', '1810']]}).json
    assert new['counts']['withdrawn'] == '10'


def test_withdrawal_csv_payload(client):
    new = sign(client, withdrawals='cue_id,start,end\nC104,1800,1810\n').json
    assert new['counts']['withdrawn'] == '10'


def test_malformed_withdrawal_is_refused(client):
    response = sign(client, withdrawals=[bid('C104', '9', '1')])
    assert (response.status_code, response.json['code']) == (422, 'WITHDRAWAL')
    assert client.get('/api/runs').json['count'] == 0


def test_withdrawal_split_across_kept_and_pending(client):
    # C103 spans KEEP [1900,2000), GAP [2000,2200), KEEP [2200,2300).
    result = sign(client, withdrawals=[bid('C103', '1950', '2050')]).json
    entry = client.application.extensions['cut_archive'].read(result['id'])
    rows = [(row['start'], row['end'], row['kind']) for row in entry['stages']['edits']['rows']
            if row['cue_id'] == 'C103']
    assert rows == [('1900', '1950', 'KEEP'), ('1950', '2000', 'WITHDRAWN'),
                    ('2000', '2200', 'GAP'), ('2200', '2300', 'KEEP')]
    assert result['counts']['withdrawn'] == '50'
    assert result['counts']['pending'] == '200'
    assert entry['stages']['balance']['balanced']


def test_later_withdrawal_also_blocks_the_reissued_package(client):
    first = sign(client, withdrawals=[bid('C104', '1800', '1810')]).json
    assert download(client, first['id']).status_code == 200
    sign(client, withdrawals=[bid('C117', '930', '940')])
    assert download(client, first['id']).json['code'] == 'WITHDRAWN'
    latest = sign(client).json
    assert download(client, latest['id']).status_code == 200
    assert latest['counts']['overlap_target_frames'] == 65 - 8

