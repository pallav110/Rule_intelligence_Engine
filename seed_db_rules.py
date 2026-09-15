#!/usr/bin/env python3
"""Seed DB rules table from domain-pack JSON active_rules files (§3.3 Rule Repository)."""
import sys, os, json
sys.path.insert(0, '.')
os.chdir('/home/spxlpt133/Desktop/Rule-intelligence-Engine')

from sqlalchemy import create_engine, text
engine = create_engine('postgresql://rie_user:rie_password@localhost:5432/rule_intelligence_engine')

# Need a workspace to attach to — use the workspace the test admin/reviewer
# belong to (e8af6af9-...) so §3.3 activation's require_workspace() passes.
with engine.connect() as conn:
    ws = conn.execute(text("""
        SELECT wm.workspace_id FROM workspace_members wm
        JOIN users u ON u.user_id = wm.user_id
        JOIN workspaces w ON w.workspace_id = wm.workspace_id
        WHERE u.email = 'admin@rie.local'
        ORDER BY wm.created_at LIMIT 1
    """)).fetchone()
    workspace_id = ws[0] if ws else "e8af6af9-3bbe-4117-a007-f55db418bc30"
    print("Using workspace:", workspace_id)

def humanize(ident):
    """'access_restriction' -> 'Access Restriction' (title-case words, drop _)."""
    if not ident:
        return ""
    return " ".join(w.title() for w in str(ident).replace("_", " ").split())


with engine.connect() as conn:
    count_before = conn.execute(text("SELECT count(*) FROM rules")).scalar()
    print("Rules before seed:", count_before)

    for pack in ["ecommerce", "customer_support", "saas_subscription"]:
        path = f"rie_ml/domain-packs/{pack}/rules/active_rules.json"
        if not os.path.exists(path):
            continue
        with open(path) as f:
            rules = json.load(f)
        for r in rules:
            # Some domain packs (saas_subscription, customer_support) have no
            # ``rule_name``/``description`` key. Derive a readable name from the
            # business term + operation so the rule repository always shows one.
            bt = r.get("business_term") or "rule"
            op = r.get("operation") or ""
            raw_desc = r.get("description") or r.get("rule_name")
            # Derived humanized name prioritizes the business term (already a
            # descriptive noun-phrase); fall back to the operation verb.
            name = r.get("rule_name") or raw_desc or (humanize(r.get("business_term")) or humanize(op))
            desc = raw_desc or f"{name or (humanize(r.get('business_term')) or 'Rule')} rule ({r.get('rule_category','rule')})"

            # Insert as DRAFT (eligible for activation workflow). On conflict,
            # refresh the display metadata (rule_name / rule_definition) so a
            # re-run repairs earlier nulls — but never touch ``status``, so an
            # already-activated rule stays active.
            conn.execute(text("""
                INSERT INTO rules (rule_id, workspace_id, domain_id, rule_name, business_term,
                rule_category, operation, conditions, scope, threshold, time_window,
                affected_tables, affected_columns, affected_entities, rule_definition,
                status, created_at)
                VALUES (:rid, :ws, :dom, :name, :bt, :cat, :op, :cond, :scope,
                :thresh, :tw, :atabs, :atcols, :ent, :def, 'draft', NOW())
                ON CONFLICT (rule_id) DO UPDATE SET
                    rule_name = EXCLUDED.rule_name,
                    rule_definition = EXCLUDED.rule_definition
            """), {
                "rid": r.get("rule_id"),
                "ws": workspace_id,
                "dom": pack,
                "name": name,
                "bt": bt,
                "cat": r.get("rule_category"),
                "op": r.get("operation"),
                "cond": json.dumps(r.get("conditions", [])),
                "scope": json.dumps(r.get("scope")) if r.get("scope") else None,
                "thresh": json.dumps(r.get("threshold")) if r.get("threshold") is not None else None,
                "tw": json.dumps(r.get("time_window")) if r.get("time_window") is not None else None,
                "atabs": json.dumps(r.get("affected_entities", {}).get("tables", [])),
                "atcols": json.dumps(r.get("affected_entities", {}).get("columns", [])),
                "ent": json.dumps(r.get("affected_entities", {})),
                "def": json.dumps({"description": desc}),
            })
        print("Seeded", len(rules), "from", pack)
    conn.commit()

with engine.connect() as conn:
    count_after = conn.execute(text("SELECT count(*) FROM rules")).scalar()
    res = conn.execute(text("SELECT status, count(*) FROM rules GROUP BY status"))
    print("Rules after seed:", count_after)
    for r in res:
        print("  Status", r[0], ":", r[1])
