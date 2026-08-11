import json
from pathlib import Path
from .generator import generate_dataset
from .validator import validate_dataset
from .splitter import split_by_family
from . import pairs
from .validator import validate_pairs_and_splits

CFG_PATH = Path(__file__).parent / 'config.json'
CFG = json.loads(CFG_PATH.read_text())


def run(small=False):
    print('Generating examples (small=%s)...' % small)
    examples = generate_dataset(seed=CFG['random_seed'], targets=CFG['targets'], small=small)
    # generated_all is written under the rie-ml package datasets folder
    all_path = Path(__file__).resolve().parents[1] / 'datasets' / 'generated' / 'v1' / 'generated_all.jsonl'
    print('Running basic dataset validator...')
    tax = Path('rie-ml/domain-packs/ecommerce/taxonomy/labels.json')
    errs = validate_dataset(all_path, tax)
    if errs:
        print('Validator found errors (first 20):')
        for e in errs[:20]:
            print('-', e)
    else:
        print('No dataset validation errors (basic checks).')

    print('Splitting into train/validation/test...')
    ntrain, nval, ntest = split_by_family(all_path, CFG['targets'], seed=CFG['random_seed'])
    print('Splits created:', ntrain, nval, ntest)

    print('Building duplicate/conflict/clarification artifacts...')
    out_dir = Path(__file__).resolve().parents[1] / 'datasets' / 'generated' / 'v1'
    all_examples = [json.loads(l) for l in open(out_dir / 'generated_all.jsonl', encoding='utf-8').read().splitlines() if l.strip()]
    dup = pairs.build_duplicate_pairs(all_examples, CFG['targets']['duplicate_pairs'], seed=CFG['random_seed'])
    conf = pairs.build_conflict_pairs(CFG['targets']['conflict_pairs'], seed=CFG['random_seed'])
    clar = pairs.build_clarifications(all_examples, CFG['targets']['clarifications'], seed=CFG['random_seed'])
    (out_dir / 'duplicate_pairs.jsonl').write_text('\n'.join(json.dumps(p, ensure_ascii=False) for p in dup), encoding='utf-8')
    (out_dir / 'conflict_pairs.jsonl').write_text('\n'.join(json.dumps(p, ensure_ascii=False) for p in conf), encoding='utf-8')
    (out_dir / 'clarifications.jsonl').write_text('\n'.join(json.dumps(p, ensure_ascii=False) for p in clar), encoding='utf-8')
    print('Wrote pairs: dup=%d conf=%d clar=%d' % (len(dup), len(conf), len(clar)))

    print('Running stronger validation (pairs + splits)...')
    dup_path = out_dir / 'duplicate_pairs.jsonl'
    conf_path = out_dir / 'conflict_pairs.jsonl'
    split_dir = out_dir
    pair_errs = validate_pairs_and_splits(all_path, dup_path, conf_path, split_dir)
    if pair_errs:
        print('Pair/split validation issues (first 30):')
        for e in pair_errs[:30]:
            print('-', e)
    else:
        print('No pair/split validation issues detected.')


if __name__ == '__main__':
    # default to full run when invoked directly from CLI
    run(small=False)
