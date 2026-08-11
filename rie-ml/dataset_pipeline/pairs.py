import json
import random
import copy
from pathlib import Path
from collections import defaultdict
from itertools import combinations
from .generator import condition_to_text

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'datasets' / 'generated' / 'v1'
PACKS_DIR = ROOT / 'domain-packs'


def load_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]


def build_duplicate_pairs(all_examples, target_pairs, seed=42):
    rnd = random.Random(seed)
    groups = defaultdict(list)
    for e in all_examples:
        groups[e['rule_family_id']].append(e)
    candidates = []
    for fam, items in groups.items():
        if len(items) < 2:
            continue
        for ia, ib in combinations(range(len(items)), 2):
            a = items[ia]
            b = items[ib]
            if a['feedback_text'] == b['feedback_text']:
                continue
            candidates.append({'a': a, 'b': b, 'label': 'semantic_duplicate'})
    rnd.shuffle(candidates)
    return candidates[:target_pairs]


def _is_conflict_pair(a, b):
    if a.get('business_term') != b.get('business_term'):
        return False
    opposite_ops = {
        ('exclude', 'include'),
        ('include', 'exclude'),
        ('map', 'replace'),
        ('replace', 'map'),
        ('restrict', 'include'),
        ('include', 'restrict')
    }
    return (a.get('operation'), b.get('operation')) in opposite_ops


def build_conflict_pairs(target_pairs, seed=42):
    rnd = random.Random(seed)
    candidates = []
    for pack in PACKS_DIR.iterdir():
        if not pack.is_dir():
            continue
        active = json.loads((pack / 'rules' / 'active_rules.json').read_text(encoding='utf-8'))
        conflicts = []
        try:
            conflicts = json.loads((pack / 'rules' / 'conflicting_rules.json').read_text(encoding='utf-8'))
        except Exception:
            conflicts = []
        active_by_term = {r['business_term']: r for r in active}
        for c in conflicts:
            term = c.get('business_term')
            a = active_by_term.get(term)
            if a:
                candidates.append({
                    'domain': pack.name,
                    'rule_a': a,
                    'rule_b': c,
                    'conflict_note': c.get('conflict_note', ''),
                    'conflict_type': c.get('conflict_type', 'direct_conflict')
                })
        # add direct conflict candidates from active rules sharing the same business term
        for ia, ib in combinations(range(len(active)), 2):
            a = active[ia]
            b = active[ib]
            if _is_conflict_pair(a, b):
                candidates.append({
                    'domain': pack.name,
                    'rule_a': a,
                    'rule_b': b,
                    'conflict_note': 'Derived from opposite operations on same business term',
                    'conflict_type': 'direct_conflict'
                })
    rnd.shuffle(candidates)
    return candidates[:target_pairs]

CLARIFICATION_TEMPLATES = [
    "What exactly should count as {term}?",
    "I need clarification on how {term} is defined.",
    "Should {cond} be included in {term}?",
    "How should we treat {cond} when calculating {term}?",
    "The business intent for {term} is unclear.",
    "Please clarify the expected behavior for {term}.",
    "It is unclear whether {cond} belongs in {term}."
]


def build_clarifications(all_examples, target, seed=42):
    rnd = random.Random(seed)
    templates = CLARIFICATION_TEMPLATES
    picks = rnd.sample(all_examples, min(target, len(all_examples)))
    clarifs = []
    for e in picks:
        term = e.get('rules', [{}])[0].get('business_term', 'the metric') or 'the metric'
        conds = e.get('rules', [{}])[0].get('conditions', [])
        cond_text = ' and '.join(condition_to_text(c) for c in conds[:2]) if conds else 'the relevant condition'
        template = rnd.choice(templates)
        text = template.format(term=term.replace('_', ' '), cond=cond_text)
        c = {
            'feedback_id': e['feedback_id'],
            'domain': e['domain'],
            'feedback_text': text,
            'feedback_type': 'unclear_feedback',
            'rule_category': None,
            'is_actionable': False,
            'requires_clarification': True,
            'rule_family_id': e['rule_family_id'],
            'rules': [],
            'annotation_version': 'gen_v1',
            'source': 'synthetic_generator',
            'clarification_reason': 'ambiguous business intent'
        }
        clarifs.append(c)
    return clarifs


if __name__ == '__main__':
    cfg = json.loads((Path(__file__).parent / 'config.json').read_text())
    all_examples = load_jsonl(OUT_DIR / 'generated_all.jsonl')
    dup_pairs = build_duplicate_pairs(all_examples, cfg['targets']['duplicate_pairs'], seed=cfg['random_seed'])
    conf_pairs = build_conflict_pairs(cfg['targets']['conflict_pairs'], seed=cfg['random_seed'])
    clarifs = build_clarifications(all_examples, cfg['targets']['clarifications'], seed=cfg['random_seed'])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'duplicate_pairs.jsonl').write_text('\n'.join(json.dumps(p, ensure_ascii=False) for p in dup_pairs))
    (OUT_DIR / 'conflict_pairs.jsonl').write_text('\n'.join(json.dumps(p, ensure_ascii=False) for p in conf_pairs))
    (OUT_DIR / 'clarifications.jsonl').write_text('\n'.join(json.dumps(p, ensure_ascii=False) for p in clarifs))
    print('Wrote duplicate_pairs:', len(dup_pairs), 'conflict_pairs:', len(conf_pairs), 'clarifications:', len(clarifs))
