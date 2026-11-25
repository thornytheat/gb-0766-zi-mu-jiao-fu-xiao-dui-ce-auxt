import pytest

from app.material import example
from app.modules.balance.service import balance
from app.modules.licensing.service import normalize
from app.pipeline import inspect
from app.problems import Rejection


def withdrawn(cue_id, start, end, track=None):
    entry = {'cue_id': cue_id, 'ranges': [[start, end]]}
    if track:
        entry['track'] = track
    return entry


def test_withdraw_parts_of_a_sentence_keeps_the_rest(dirty):
    sample = dict(example('dirty'), withdrawals=[withdrawn('C101', '950', '980')])
    rows = [row for row in inspect(sample)['edits']['rows'] if row['cue_id'] == 'C101']
    assert [(row['start'], row['end'], row['kind']) for row in rows] == [
        ('900', '950', 'KEEP'), ('950', '980', 'WITHDRAWN'), ('980', '1000', 'KEEP'),
        ('1000', '1200', 'REMOVE'), ('1200', '1300', 'KEEP')]


def test_sentence_is_not_dropped_wholesale(dirty):
    sample = dict(example('dirty'), withdrawals=[withdrawn('C104', '1801', '1805')])
    rows = [row for row in inspect(sample)['edits']['rows'] if row['cue_id'] == 'C104']
    assert [row['kind'] for row in rows] == ['KEEP', 'WITHDRAWN', 'KEEP']


def test_licensed_frames_stay_delivered(dirty):
    sample = dict(example('dirty'), withdrawals=[withdrawn('C104', '1800', '1810')])
    counts = inspect(sample)['balance']['counts']
    assert (counts['delivered'], counts['withdrawn']) == ('730', '10')
    assert inspect(sample)['balance']['balanced']


def test_banned_frames_still_counted_when_another_cue_covers(dirty):
    # C113 sits fully inside C101/C102's delivered span.  Its ban must not
    # shrink delivered coverage (another licensed cue still says those words);
    # it only removes C113 from the clash scan.
    base = inspect(example('dirty'))
    sample = dict(example('dirty'), withdrawals=[withdrawn('C113', '1255', '1290')])
    check = inspect(sample)
    assert check['balance']['counts']['delivered'] == base['balance']['counts']['delivered']
    assert 'withdrawn' not in check['balance']['counts']
    assert check['balance']['balanced']
    assert not any(len(row['lines']) >= 3 for row in check['overlaps']['rows'])


def test_clash_with_only_the_other_cue_disappears(dirty):
    sample = dict(example('dirty'), withdrawals=[withdrawn('C117', '930', '940')])
    check = inspect(sample)
    assert not any('C117' in row['cues'] for row in check['overlaps']['rows'])
    assert check['overlaps']['counts']['overlap_frames'] == 65 - 8
    # C117's frames stay delivered because C101 still carries them.
    assert check['balance']['counts']['delivered'] == '740'
    assert check['balance']['balanced']


def test_gap_withdrawal_does_not_claim_delivered(dirty):
    sample = dict(example('dirty'), withdrawals=[withdrawn('C103', '2000', '2200')])
    check = inspect(sample)
    assert check['balance']['counts']['pending'] == '200'
    assert 'withdrawn' not in check['balance']['counts']
    assert check['balance']['balanced']


def test_unknown_cue_is_rejected():
    sample = dict(example('dirty'), withdrawals=[withdrawn('C999', '1', '2')])
    with pytest.raises(Rejection) as error:
        inspect(sample)
    assert error.value.code == 'NO_CUE'


def test_ranges_are_normalized_and_merged():
    assert normalize([withdrawn('C1', '4', '6'), withdrawn('C1', '1', '5')]) == [
        {'cue_id': 'C1', 'ranges': [['1', '6']]}]
    assert normalize('cue_id,start,end\nC1,1,5\n') == [{'cue_id': 'C1', 'ranges': [['1', '5']]}]


def test_withdrawn_bucket_never_double_counts(dirty):
    # [2,6) and [8,12) stay licensed; only [0,2) and [6,8) are withdrawn.
    rows = [dict(start='0', end='10', kind='WITHDRAWN', track='t'),
            dict(start='2', end='6', kind='KEEP', track='t'),
            dict(start='8', end='12', kind='KEEP', track='t')]
    output = balance([dict(start='0', end='12', track='t')], rows, 0, 0)
    assert output['counts']['withdrawn'] == '4'
    assert output['counts']['delivered'] == '8'
    assert output['balanced']
