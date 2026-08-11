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
        "Include only {expr} in {term}.",
        "The {term} metric is based on {expr}.",
        "Measure {term} using {expr}.",
        "Compute {term} from {expr}.",
        "Derive {term} from {expr}."
    ],
    "filter_rule": [
        "Exclude records where {cond} from {term}.",
        "Do not count {cond} in {term}.",
        "Ignore {cond} when computing {term}.",
        "Remove rows with {cond} from the {term} calculation.",
        "Skip {cond} for the {term} metric.",
        "Do not include {cond} in {term}.",
        "Forget about records where {cond} for {term}."
    ],
    "status_mapping": [
        "Treat status values {vals} as {term}.",
        "Map {vals} to {term} status.",
        "Consider {vals} equivalent for {term}.",
        "Classify {vals} as {term}.",
        "Use {term} for status values {vals}.",
        "Count {vals} as {term}."
    ],
    "time_rule": [
        "Compute {term} using {window} window.",
        "Use {window} when measuring {term}.",
        "Apply a {window} window to {term}.",
        "Measure {term} with a {window} window.",
        "The {term} metric should use a {window} window."
    ],
    "join_correction": [
        "Join {table_a} to {table_b} using {field} instead of {alt}.",
        "Use {field} as the join key for {term}.",
        "The join between {table_a} and {table_b} should use {field}.",
        "Connect {table_a} and {table_b} on {field}."
    ],
    "data_quality_issue": [
        "Rows with {cond} indicate a data quality problem in {table}.",
        "Flag records where {cond} for review.",
        "There is a data quality issue when {cond}.",
        "Mark records with {cond} as suspect."
    ],
    "entity_definition": [
        "An {term} is any record with {cond}.",
        "Define {term} as rows where {cond}.",
        "Consider {term} to be records where {cond}.",
        "Classify a record as {term} if {cond}."
    ],
    "access_scope_rule": [
        "Restrict {term} to records where {cond}.",
        "Only count {term} for {cond}.",
        "Scope {term} to {cond}.",
        "Limit {term} calculations to {cond}.",
        "The {term} metric should only include {cond}."
    ],
    "calculation_correction": [
        "Compute {term} as {expr}.",
        "Use {expr} to calculate {term}.",
        "The {term} calculation should be {expr}.",
        "Calculate {term} using {expr}.",
        "The {term} formula is {expr}."
    ],
    "non_rule_feedback": [
        "{term} needs attention: {cond}.",
        "There is an issue with {cond} affecting {term}.",
        "We need to fix {cond} before {term} is correct.",
        "{term} is wrong because {cond}."
    ]
}

OPERATOR_LABELS = {
    'equals': 'equals',
    'greater_than': 'greater than',
    'less_than': 'less than',
    'in': 'in',
    'is_not_null': 'is present',
    'is_null': 'is missing',
    'contains': 'contains'
}


def pick_template(category, rule, glossary, schema):
    return random.choice(SIMPLE_TEMPLATES.get(category, ["{term} needs attention: {cond}."]))


def condition_to_text(cond):
    f = cond.get('field')
    op = cond.get('operator')
    val = cond.get('value')
    label = OPERATOR_LABELS.get(op, op)

    if isinstance(val, list):
        vals = ", ".join(str(x) for x in val)
        return f"{f} {label} [{vals}]"
    if op == 'is_not_null':
        return f"{f} is present"
    if op == 'is_null':
        return f"{f} is missing"
    if isinstance(val, bool):
        return f"{f} is {str(val).lower()}"
    if val is None:
        return f"{f} is null"
    if isinstance(val, str) and val.startswith('NOT_'):
        return f"{f} is not {val[4:]}"
    return f"{f} {label} {val}"

VARIATION_PREFIXES = [
    '',
    'Please',
    'We should',
    'The business needs to',
    'It should',
    'Make sure to'
]

VARIATION_REPLACEMENTS = [
    (' using ', ' via '),
    (' Compute ', ' Calculate '),
    (' count ', ' include '),
    (' exclude ', ' remove '),
    (' ignore ', ' skip '),
    (' should be ', ' should ')
]


def apply_text_variations(text):
    if random.random() < 0.16:
        prefix = random.choice(VARIATION_PREFIXES)
        if prefix:
            if text.endswith('.'):
                text = text[:-1]
            text = prefix + ' ' + text[0].lower() + text[1:]
            if not text.endswith('.'):
                text += '.'
    if random.random() < 0.2:
        old, new = random.choice(VARIATION_REPLACEMENTS)
        text = text.replace(old, new)
    if random.random() < 0.1:
        text = text.replace(' and ', ' & ')
    return text


def generate_example(domain, family_id, rule, glossary, schema, seq, existing_texts=None):
    category = rule.get('rule_category') or 'unclear_feedback'
    term = rule.get('business_term') or 'unknown_term'
    conds = rule.get('conditions', [])
    cond_text = ' and '.join(condition_to_text(c) for c in conds[:2]) if conds else 'unspecified condition'
    table_a = ''
    table_b = ''
    if rule.get('affected_entities'):
        tabs = rule.get('affected_entities', {}).get('tables', [])
        if len(tabs) >= 2:
            table_a, table_b = tabs[0], tabs[1]
        elif len(tabs) == 1:
            table_a = tabs[0]
    if not table_b and conds:
        table_b = conds[0].get('field', '').split('.')[0]

    alt = rule.get('alt_join_field') or 'the current key'
    if not alt:
        alt = 'the current key'

    kwargs = {
        'term': term.replace('_', ' '),
        'expr': cond_text,
        'cond': cond_text,
        'table': (conds[0].get('field').split('.')[0] if conds else ''),
        'field': (conds[0].get('field') if conds else ''),
        'alt': alt,
        'table_a': table_a,
        'table_b': table_b,
        'vals': ','.join(map(str, conds[0].get('value'))) if conds and isinstance(conds[0].get('value'), list) else (conds[0].get('value') if conds else ''),
        'window': rule.get('scope') or 'global'
    }

    if existing_texts is None:
        existing_texts = set()
    text = ''
    attempts = 0
    while attempts < 10:
        template = pick_template(category, rule, glossary, schema)
        text = template.format(**kwargs)
        text = apply_text_variations(text)
        if text not in existing_texts:
            break
        attempts += 1

    return {
        'feedback_id': f"GEN_{domain.upper()}_{seq:06d}",
        'domain': domain,
        'feedback_text': text,
        'feedback_type': 'business_rule_correction' if category != 'non_rule_feedback' else 'non_rule_feedback',
        'rule_category': category,
        'is_actionable': category != 'unclear_feedback',
        'requires_clarification': category == 'unclear_feedback',
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
            existing_texts = set()
            for i in range(per_family):
                seq += 1
                ex = generate_example(domain, family_id, rule, gloss, schema, seq, existing_texts=existing_texts)
                existing_texts.add(ex['feedback_text'])
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
