import json
import random
import copy
from pathlib import Path
from collections import defaultdict
from itertools import combinations

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
    # build all possible unordered pairs within each family, shuffle, and
    # take up to target_pairs. This lets us create many duplicate pairs when
    # families have multiple paraphrases.
    candidates = []
    for fam, items in groups.items():
        if len(items) < 2:
            continue
        # enumerate all unordered pairs
        for ia, ib in combinations(range(len(items)), 2):
            a = items[ia]
            b = items[ib]
            candidates.append({'a': a, 'b': b, 'label': 'semantic_duplicate'})
    rnd.shuffle(candidates)
    return candidates[:target_pairs]


def _synthesize_conflict_variant(rule, pack_name, idx):
    # make a small synthetic conflicting variant of `rule`
    r = copy.deepcopy(rule)
    base_id = r.get('rule_id', 'R')
    r['rule_id'] = f"{base_id}_SYN_{idx}_{pack_name.upper()}"
    # toggle a high-level operation if present
    op = r.get('operation', '')
    if op == 'exclude':
        r['operation'] = 'include'
    else:
        r['operation'] = 'exclude'
    # tweak conditions to create a real-appearing contradiction
    for cond in r.get('conditions', []):
        val = cond.get('value')
        if isinstance(val, bool):
            cond['value'] = not val
        elif isinstance(val, (int, float)):
            # nudge numeric thresholds
            cond['value'] = val + 1
        elif isinstance(val, list):
            cond['value'] = list(reversed(val))
        elif isinstance(val, str) and val.endswith('_ago'):
            cond['value'] = '30_days_ago' if val != '30_days_ago' else '90_days_ago'
        else:
            # fallback: add a short negation marker
            cond['value'] = f"NOT_{val}"
    r['conflict_note'] = 'Synthetic conflicting variant'
    return r


def build_conflict_pairs(target_pairs, seed=42):
    rnd = random.Random(seed)
    pairs = []
    candidates = []
    # first use any explicit conflicts listed in domain packs
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
                candidates.append({'domain': pack.name, 'rule_a': a, 'rule_b': c, 'conflict_note': c.get('conflict_note','')})
        # synthesize additional conflicts from active rules in this pack
        for i, a in enumerate(active):
            # synthesize several variants per active rule to reach desired counts
            for j in range(6):
                b = _synthesize_conflict_variant(a, pack.name, f"{i}_{j}")
                candidates.append({'domain': pack.name, 'rule_a': a, 'rule_b': b, 'conflict_note': b.get('conflict_note','')})
    rnd.shuffle(candidates)
    return candidates[:target_pairs]


def build_clarifications(all_examples, target, seed=42):
    rnd = random.Random(seed)
    picks = rnd.sample(all_examples, min(target, len(all_examples)))
    clarifs = []
    for e in picks:
        c = dict(e)
        c['requires_clarification'] = True
        c['is_actionable'] = False
        c['rules'] = []
        c['clarification_reason'] = 'missing details: time_window/threshold/scope'
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
