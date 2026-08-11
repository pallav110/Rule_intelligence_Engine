import json
import random
import uuid
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
PACKS_DIR = ROOT / "domain-packs"
OUT_DIR = ROOT / "datasets" / "generated" / "v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# load local config (targets, seed, and new paraphrase control)
CFG = json.loads((Path(__file__).parent / 'config.json').read_text(encoding='utf-8'))


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def parse_glossary(gloss_path: Path):
    txt = gloss_path.read_text(encoding="utf-8")
    # find backticked identifiers like `invoices.amount_cents`
    lines = {}
    for line in txt.splitlines():
        m = re.match(r"- `([a-zA-Z0-9_\.]+)`: ?(.*)$", line.strip())
        if m:
            key = m.group(1)
            desc = m.group(2)
            lines[key] = desc
    return lines


def discover_packs():
    packs = []
    for p in PACKS_DIR.iterdir():
        if p.is_dir():
            packs.append(p)
    return sorted(packs)


def build_rule_families(pack_path: Path):
    rules_file = pack_path / "rules" / "active_rules.json"
    rules = load_json(rules_file)
    families = []
    for r in rules:
        family_id = f"{pack_path.name}_{r.get('rule_id')}"
        families.append((family_id, r))
    return families


SIMPLE_TEMPLATES = {
    "metric_definition": [
        "{term} should be computed as {expr}.",
        "Calculate {term} by {expr}.",
        "Include only {expr} in {term}."
    ],
    "filter_rule": [
        "Exclude records where {cond} from {term}.",
        "Do not count {cond} in {term}.",
        "Ignore {cond} when computing {term}."
    ],
    "status_mapping": [
        "Treat status values {vals} as {term}.",
        "Map {vals} to {term} status.",
        "Consider {vals} equivalent for {term}."
    ],
    "time_rule": [
        "Compute {term} using {window} window.",
        "Use {window} when measuring {term}."
    ],
    "join_correction": [
        "Join {table_a} to {table_b} using {field} instead of {alt}.",
        "Use {field} as the join key for {term}."
    ],
    "data_quality_issue": [
        "Rows with {cond} indicate a data quality problem in {table}.",
        "Flag records where {cond} for review." 
    ],
    "entity_definition": [
        "An {term} is any record with {cond}.",
        "Define {term} as rows where {cond}."
    ]
}


def pick_template(category, rule, glossary, schema):
    tlist = SIMPLE_TEMPLATES.get(category) or ["{term} needs attention: {cond}"]
    return random.choice(tlist)


def condition_to_text(cond):
    f = cond.get('field')
    op = cond.get('operator')
    val = cond.get('value')
    if isinstance(val, list):
        vals = ", ".join(map(str, val))
        return f"{f} {op} [{vals}]"
    return f"{f} {op} {val}"


def generate_example(domain, family_id, rule, glossary, schema, seq):
    category = rule.get('rule_category') or 'unclear_feedback'
    term = rule.get('business_term') or 'unknown_term'
    conds = rule.get('conditions', [])
    cond_text = '; '.join(condition_to_text(c) for c in conds[:2]) if conds else 'unspecified condition'
    template = pick_template(category, rule, glossary, schema)
    # prepare template kwargs
    # derive table_a/table_b if available
    table_a = kwargs_table = (conds[0].get('field').split('.')[0] if conds else '')
    table_b = ''
    if rule.get('affected_entities'):
        tabs = rule.get('affected_entities', {}).get('tables', [])
        if len(tabs) >= 2:
            table_a, table_b = tabs[0], tabs[1]
        elif len(tabs) == 1:
            table_a = tabs[0]

    kwargs = {
        'term': term.replace('_', ' '),
        'expr': cond_text,
        'cond': cond_text,
        'table': (conds[0].get('field').split('.')[0] if conds else ''),
        'field': (conds[0].get('field') if conds else ''),
        'alt': '',
        'table_a': table_a,
        'table_b': table_b,
        'vals': ','.join(map(str, conds[0].get('value'))) if conds and isinstance(conds[0].get('value'), list) else (conds[0].get('value') if conds else ''),
        'window': rule.get('scope') or 'global'
    }
    text = template.format(**kwargs)
    # small variations
    if random.random() < 0.1:
        # Hinglish mix
        text = text + " (please remove yeh quickly)"
    if random.random() < 0.05:
        # grammatical error
        text = text.replace('should be', 'should')
    return {
        'feedback_id': f"GEN_{domain.upper()}_{seq:06d}",
        'domain': domain,
        'feedback_text': text,
        'feedback_type': 'business_rule_correction' if category != 'non_rule_feedback' else 'non_rule_feedback',
        'rule_category': category,
        'is_actionable': True if category != 'unclear_feedback' else False,
        'requires_clarification': False if category != 'unclear_feedback' else True,
        'rule_family_id': family_id,
        'rules': [
            {
                'business_term': term,
                'operation': rule.get('operation'),
                'conditions': conds,
                'scope': rule.get('scope'),
                'time_window': rule.get('time_window'),
                'threshold': rule.get('threshold'),
                'affected_entities': rule.get('affected_entities')
            }
        ],
        'annotation_version': 'gen_v1',
        'source': 'synthetic_generator'
    }


def generate_dataset(seed=42, targets=None, small=False):
    random.seed(seed)
    packs = discover_packs()
    # compute domain targets
    total_main = sum(targets[k] for k in ('train','validation','test'))
    per_domain = {}
    base = total_main // len(packs)
    for i,p in enumerate(packs):
        per_domain[p.name] = base + (1 if i < (total_main % len(packs)) else 0)

    all_examples = []
    rule_families = {}
    min_paraphrases = CFG.get('min_paraphrases_per_family', 1)
    for pack in packs:
        domain = pack.name
        families = build_rule_families(pack)
        schema = load_json(pack / 'schema' / 'schema.json')
        gloss = parse_glossary(pack / 'documentation' / 'business_glossary.md')
        rule_families[domain] = [f for f,_ in families]
        num_families = len(families)
        domain_target = 50 if small else per_domain[domain]
        # ensure we generate at least `min_paraphrases` examples per family so
        # the duplicate-pair builder has enough paraphrases to create many pairs.
        per_family = max(min_paraphrases, domain_target // max(1, num_families))
        seq = len(all_examples)
        for family_id, rule in families:
            for i in range(per_family):
                seq += 1
                ex = generate_example(domain, family_id, rule, gloss, schema, seq)
                all_examples.append(ex)

    # shuffle deterministically
    random.shuffle(all_examples)
    # write a flat generated file before splitting
    out_all = OUT_DIR / 'generated_all.jsonl'
    with out_all.open('w', encoding='utf-8') as fh:
        for e in all_examples:
            fh.write(json.dumps(e, ensure_ascii=False) + '\n')
    return all_examples


if __name__ == '__main__':
    import sys
    cfg = json.loads((Path(__file__).parent / 'config.json').read_text())
    small = True
    if len(sys.argv) > 1 and sys.argv[1] in ('full', '--full'):
        small = False
    examples = generate_dataset(seed=cfg['random_seed'], targets=cfg['targets'], small=small)
    print(f"Generated {len(examples)} synthetic examples ({'small' if small else 'full'} run).")
