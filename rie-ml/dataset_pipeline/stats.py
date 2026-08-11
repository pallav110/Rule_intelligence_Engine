import json
import random
from pathlib import Path
from collections import Counter, defaultdict

OUT_DIR = Path(__file__).resolve().parents[1] / 'datasets' / 'generated' / 'v1'


def load_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]


def load_splits():
    splits = {}
    for name in ('train', 'validation', 'test'):
        path = OUT_DIR / f'{name}.jsonl'
        splits[name] = load_jsonl(path) if path.exists() else []
    return splits


def sample(items, n=10, seed=42):
    rnd = random.Random(seed)
    return rnd.sample(items, min(n, len(items)))


def format_pair(pair, kind='duplicate'):
    if kind == 'duplicate':
        a, b = pair['a'], pair['b']
        info = [
            f"{a['feedback_id']} ↔ {b['feedback_id']}",
            f"family={a.get('rule_family_id')}"
        ]
        return ' | '.join(info)
    else:
        a, b = pair['rule_a'], pair['rule_b']
        info = [
            f"{a.get('rule_id')} ↔ {b.get('rule_id')}",
            f"domain={pair.get('domain', 'n/a')}",
            f"type={pair.get('conflict_type', 'n/a')}"
        ]
        return ' | '.join(info)


def compute():
    all_ex = load_jsonl(OUT_DIR / 'generated_all.jsonl')
    dup_pairs = load_jsonl(OUT_DIR / 'duplicate_pairs.jsonl') if (OUT_DIR / 'duplicate_pairs.jsonl').exists() else []
    conf_pairs = load_jsonl(OUT_DIR / 'conflict_pairs.jsonl') if (OUT_DIR / 'conflict_pairs.jsonl').exists() else []
    clarifs = load_jsonl(OUT_DIR / 'clarifications.jsonl') if (OUT_DIR / 'clarifications.jsonl').exists() else []
    splits = load_splits()

    domains = Counter(e['domain'] for e in all_ex)
    cats = Counter(e.get('rule_category') for e in all_ex)
    families = Counter(e['rule_family_id'] for e in all_ex)
    unique_texts = len({e['feedback_text'] for e in all_ex})
    exact_duplicate_texts = len(all_ex) - unique_texts
    dup_exact_pairs = sum(1 for p in dup_pairs if p['a']['feedback_text'] == p['b']['feedback_text'])
    dup_family_mismatches = sum(1 for p in dup_pairs if p['a'].get('rule_family_id') != p['b'].get('rule_family_id'))

    split_counts = {name: len(records) for name, records in splits.items()}
    split_families = {name: {r['rule_family_id'] for r in records} for name, records in splits.items()}
    family_leakage = len([fid for records in split_families.values() for fid in records]) != len(set().union(*split_families.values()))

    id_to_split = {}
    for name, records in splits.items():
        for rec in records:
            id_to_split[rec['feedback_id']] = name
    duplicate_cross_split = sum(
        1 for p in dup_pairs
        if id_to_split.get(p['a']['feedback_id']) and id_to_split.get(p['b']['feedback_id']) and id_to_split.get(p['a']['feedback_id']) != id_to_split.get(p['b']['feedback_id'])
    )

    conflict_types = Counter(p.get('conflict_type', 'unknown') for p in conf_pairs)
    conflict_term_mismatch = sum(
        1 for p in conf_pairs
        if p.get('rule_a', {}).get('business_term') and p.get('rule_b', {}).get('business_term') and p['rule_a']['business_term'] != p['rule_b']['business_term']
    )

    meta = {
        'generated_at': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
        'n_examples': len(all_ex),
        'by_domain': dict(domains),
        'by_category': dict(cats),
        'unique_feedback_texts': unique_texts,
        'exact_duplicate_feedback_texts': exact_duplicate_texts,
        'n_rule_families': len(families),
        'examples_per_rule_family': dict(families),
        'split_counts': split_counts,
        'n_duplicate_pairs': len(dup_pairs),
        'exact_text_duplicate_pairs': dup_exact_pairs,
        'duplicate_pair_family_mismatches': dup_family_mismatches,
        'duplicate_pair_cross_split': duplicate_cross_split,
        'n_conflict_pairs': len(conf_pairs),
        'conflict_types': dict(conflict_types),
        'conflict_term_mismatches': conflict_term_mismatch,
        'n_clarifications': len(clarifs),
        'split_family_leakage': family_leakage
    }
    (OUT_DIR / 'metadata.json').write_text(json.dumps(meta, indent=2))

    print('Dataset quality report')
    print('----------------------')
    print('Total examples:', meta['n_examples'])
    print('By domain:', meta['by_domain'])
    print('By category:', meta['by_category'])
    print('Unique feedback texts:', meta['unique_feedback_texts'])
    print('Exact duplicate feedback texts:', meta['exact_duplicate_feedback_texts'])
    print('Rule families:', meta['n_rule_families'])
    print('Split counts:', meta['split_counts'])
    print('Duplicate pairs:', meta['n_duplicate_pairs'])
    print('Exact-text duplicate pairs:', meta['exact_text_duplicate_pairs'])
    print('Duplicate pair family mismatches:', meta['duplicate_pair_family_mismatches'])
    print('Duplicate pair cross-split:', meta['duplicate_pair_cross_split'])
    print('Conflict pairs:', meta['n_conflict_pairs'])
    print('Conflict types:', meta['conflict_types'])
    print('Conflict business-term mismatches:', meta['conflict_term_mismatches'])
    print('Clarifications:', meta['n_clarifications'])
    print('Rule-family leakage across splits:', meta['split_family_leakage'])

    def maybe_print_samples(label, items, formatter, sample_size=10):
        if not items:
            return
        print(f'\n{label} (sample {min(sample_size, len(items))})')
        for item in sample(items, sample_size):
            print('-', formatter(item))

    maybe_print_samples('Duplicate pair samples', dup_pairs, lambda p: format_pair(p, kind='duplicate'))
    maybe_print_samples('Conflict pair samples', conf_pairs, lambda p: format_pair(p, kind='conflict'))
    maybe_print_samples('Clarification examples', clarifs, lambda c: f"{c['feedback_id']} | {c['feedback_text']} | family={c.get('rule_family_id')}")

    print('\nMetadata written:', OUT_DIR / 'metadata.json')


if __name__ == '__main__':
    compute()
