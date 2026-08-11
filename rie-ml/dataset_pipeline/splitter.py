import json
import random
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'datasets' / 'generated' / 'v1'


def load_all(p: Path):
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]


def write_jsonl(path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + '\n')


def split_by_family(all_path, targets, seed=42):
    data = load_all(all_path)
    groups = defaultdict(list)
    for rec in data:
        groups[rec['rule_family_id']].append(rec)
    fams = list(groups.items())
    random.Random(seed).shuffle(fams)
    train_target = targets['train']
    val_target = targets['validation']
    test_target = targets['test']

    train, val, test = [], [], []
    # greedy assign families until targets met approximately
    for fid, items in fams:
        if len(train) < train_target:
            train.extend(items)
        elif len(val) < val_target:
            val.extend(items)
        else:
            test.extend(items)

    write_jsonl(OUT_DIR / 'train.jsonl', train)
    write_jsonl(OUT_DIR / 'validation.jsonl', val)
    write_jsonl(OUT_DIR / 'test.jsonl', test)
    return len(train), len(val), len(test)


if __name__ == '__main__':
    cfg = json.loads((Path(__file__).parent / 'config.json').read_text())
    ntrain, nval, ntest = split_by_family(Path(OUT_DIR / 'generated_all.jsonl'), cfg['targets'], seed=cfg['random_seed'])
    print('Splits:', ntrain, nval, ntest)
