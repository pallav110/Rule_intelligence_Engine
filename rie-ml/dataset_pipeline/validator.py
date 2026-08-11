import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'datasets' / 'generated' / 'v1'


def load_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]


def validate_dataset(all_path: Path, taxonomy_path: Path):
    data = load_jsonl(all_path)
    ids = set()
    errors = []
    taxonomy = json.loads(taxonomy_path.read_text(encoding='utf-8'))
    valid_categories = set(taxonomy.get('rule_categories', []))
    valid_feedback_types = set(taxonomy.get('feedback_types', []))

    for i,rec in enumerate(data):
        fid = rec.get('feedback_id')
        if not fid:
            errors.append(f"missing feedback_id at index {i}")
        if fid in ids:
            errors.append(f"duplicate feedback_id {fid}")
        ids.add(fid)
        ft = rec.get('feedback_type')
        if ft and ft not in valid_feedback_types:
            errors.append(f"invalid feedback_type {ft} in {fid}")
        rc = rec.get('rule_category')
        if rc and rc not in valid_categories and rc is not None:
            errors.append(f"invalid rule_category {rc} in {fid}")
        # minimal schema field checks
        for rule in rec.get('rules',[]):
            for cond in rule.get('conditions',[]):
                f = cond.get('field')
                if f and '.' not in f:
                    errors.append(f"malformed field {f} in {fid}")

    return errors


def validate_pairs_and_splits(all_path: Path, dup_path: Path, conf_path: Path, splits_dir: Path):
    errors = []
    all_recs = load_jsonl(all_path)
    id_map = {r.get('feedback_id'): r for r in all_recs}

    # load splits
    split_files = {
        'train': splits_dir / 'train.jsonl',
        'validation': splits_dir / 'validation.jsonl',
        'test': splits_dir / 'test.jsonl'
    }
    split_members = {}
    for k, p in split_files.items():
        if p.exists():
            split_members[k] = {r.get('feedback_id') for r in load_jsonl(p)}
        else:
            split_members[k] = set()

    # duplicate pairs
    if dup_path.exists():
        dup_lines = load_jsonl(dup_path)
        for i,pair in enumerate(dup_lines):
            a = pair.get('a') or {}
            b = pair.get('b') or {}
            aid = a.get('feedback_id')
            bid = b.get('feedback_id')
            if not aid or not bid:
                errors.append(f'duplicate pair {i} missing feedback ids')
                continue
            if aid not in id_map:
                errors.append(f'duplicate pair {i} a id {aid} not in generated_all')
            if bid not in id_map:
                errors.append(f'duplicate pair {i} b id {bid} not in generated_all')
            # they should share the same family
            af = a.get('rule_family_id')
            bf = b.get('rule_family_id')
            if af and bf and af != bf:
                errors.append(f'duplicate pair {i} family mismatch {af} != {bf}')
            # ensure both sides are from same split (avoid leakage)
            found = [k for k,v in split_members.items() if aid in v]
            found_b = [k for k,v in split_members.items() if bid in v]
            if found and found_b and found[0] != found_b[0]:
                errors.append(f'duplicate pair {i} crosses splits: {aid} in {found[0]} vs {bid} in {found_b[0]}')

    # conflict pairs
    if conf_path.exists():
        conf_lines = load_jsonl(conf_path)
        for i,pair in enumerate(conf_lines):
            a = pair.get('rule_a') or {}
            b = pair.get('rule_b') or {}
            aid = a.get('rule_id')
            bid = b.get('rule_id')
            if not aid or not bid:
                errors.append(f'conflict pair {i} missing rule ids')
                continue
            # basic sanity: business terms should match for a direct conflict
            at = a.get('business_term')
            bt = b.get('business_term')
            if at and bt and at != bt:
                # not necessarily an error, but flag potential mismatch
                errors.append(f'conflict pair {i} business_term mismatch {at} != {bt}')

    return errors


if __name__ == '__main__':
    allp = OUT_DIR / 'generated_all.jsonl'
    tax = Path('rie-ml/domain-packs/ecommerce/taxonomy/labels.json')
    errs = validate_dataset(allp, tax)
    if errs:
        print('Validation errors:')
        for e in errs[:50]:
            print('-', e)
    else:
        print('No dataset validation errors (basic checks).')
