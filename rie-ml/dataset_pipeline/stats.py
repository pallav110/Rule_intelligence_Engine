import json
from pathlib import Path
from collections import Counter, defaultdict

OUT_DIR = Path(__file__).resolve().parents[1] / 'datasets' / 'generated' / 'v1'


def load_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]


def compute():
    all_ex = load_jsonl(OUT_DIR / 'generated_all.jsonl')
    domains = Counter(e['domain'] for e in all_ex)
    cats = Counter(e.get('rule_category') for e in all_ex)
    families = set(e['rule_family_id'] for e in all_ex)
    dup_pairs = load_jsonl(OUT_DIR / 'duplicate_pairs.jsonl') if (OUT_DIR / 'duplicate_pairs.jsonl').exists() else []
    conf_pairs = load_jsonl(OUT_DIR / 'conflict_pairs.jsonl') if (OUT_DIR / 'conflict_pairs.jsonl').exists() else []
    clarifs = load_jsonl(OUT_DIR / 'clarifications.jsonl') if (OUT_DIR / 'clarifications.jsonl').exists() else []

    meta = {
        'generated_at': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
        'n_examples': len(all_ex),
        'by_domain': dict(domains),
        'by_category': dict(cats),
        'n_rule_families': len(families),
        'n_duplicate_pairs': len(dup_pairs),
        'n_conflict_pairs': len(conf_pairs),
        'n_clarifications': len(clarifs)
    }
    (OUT_DIR / 'metadata.json').write_text(json.dumps(meta, indent=2))
    print('Metadata written:', meta)


if __name__ == '__main__':
    compute()
