"""Database migration to load conflicting_rules.json into conflicting_rules_reference table."""

import json
from pathlib import Path
from sqlalchemy import text


def create_conflicting_rules_table(db):
    """Create the conflicting_rules_reference table if it doesn't exist."""
    create_table_query = text("""
        CREATE TABLE IF NOT EXISTS conflicting_rules_reference (
            id SERIAL PRIMARY KEY,
            workspace_id VARCHAR(255) NOT NULL,
            domain_id VARCHAR(255) NOT NULL,
            rule_id VARCHAR(255) NOT NULL,
            conflicts_with VARCHAR(255) NOT NULL,
            rule_name VARCHAR(255),
            rule_category VARCHAR(100),
            business_term VARCHAR(255),
            operation VARCHAR(50),
            conditions JSONB,
            scope VARCHAR(100),
            time_window VARCHAR(100),
            threshold NUMERIC,
            affected_entities JSONB,
            conflict_type VARCHAR(50),
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(workspace_id, domain_id, rule_id)
        )
    """)
    try:
        db.execute(create_table_query)
        db.commit()
        print("✓ Created conflicting_rules_reference table")
    except Exception as e:
        print(f"✓ Table already exists or created: {e}")
        db.rollback()


def seed_conflicting_rules(db, domain_id: str, workspace_id: str) -> int:
    """
    Load conflicting_rules.json and seed into database.

    Returns: Number of rules inserted
    """
    # Load conflicting rules from JSON
    rules_path = (
        Path(__file__).parent.parent.parent /
        "rie_ml" / "domain-packs" / domain_id / "rules" / "conflicting_rules.json"
    )

    if not rules_path.exists():
        print(f"✗ conflicting_rules.json not found for {domain_id}")
        return 0

    try:
        with open(rules_path, 'r') as f:
            rules = json.load(f)
    except Exception as e:
        print(f"✗ Error reading {domain_id}/conflicting_rules.json: {e}")
        return 0

    if not isinstance(rules, list):
        print(f"✗ conflicting_rules.json is not a list for {domain_id}")
        return 0

    inserted_count = 0

    for rule in rules:
        try:
            insert_query = text("""
                INSERT INTO conflicting_rules_reference
                (workspace_id, domain_id, rule_id, conflicts_with, rule_name,
                 rule_category, business_term, operation, conditions, scope,
                 time_window, threshold, affected_entities, conflict_type, description)
                VALUES
                (:workspace_id, :domain_id, :rule_id, :conflicts_with, :rule_name,
                 :rule_category, :business_term, :operation, :conditions, :scope,
                 :time_window, :threshold, :affected_entities, :conflict_type, :description)
                ON CONFLICT (workspace_id, domain_id, rule_id) DO UPDATE SET
                    conflicts_with = EXCLUDED.conflicts_with,
                    conflict_type = EXCLUDED.conflict_type,
                    description = EXCLUDED.description
            """)

            db.execute(insert_query, {
                "workspace_id": workspace_id,
                "domain_id": domain_id,
                "rule_id": rule.get("rule_id"),
                "conflicts_with": rule.get("conflicts_with"),
                "rule_name": rule.get("rule_name"),
                "rule_category": rule.get("rule_category"),
                "business_term": rule.get("business_term"),
                "operation": rule.get("operation"),
                "conditions": json.dumps(rule.get("conditions", [])),
                "scope": rule.get("scope"),
                "time_window": rule.get("time_window"),
                "threshold": rule.get("threshold"),
                "affected_entities": json.dumps(rule.get("affected_entities", {})),
                "conflict_type": rule.get("conflict_type"),
                "description": rule.get("description"),
            })
            inserted_count += 1
        except Exception as e:
            print(f"  ✗ Error inserting {rule.get('rule_id')}: {e}")

    db.commit()
    print(f"  ✓ Seeded {inserted_count} conflicting rules for {domain_id}")
    return inserted_count


def seed_all_domains(db, workspace_id: str):
    """Seed conflicting rules for all domain packs."""
    from pathlib import Path

    # Try multiple possible paths (no hardcoded absolute paths)
    possible_paths = [
        Path(__file__).resolve().parent.parent.parent / "rie_ml" / "domain-packs",
        Path.cwd() / "rie_ml" / "domain-packs",
    ]

    domain_packs_path = None
    for path in possible_paths:
        if path.exists():
            domain_packs_path = path
            print(f"✓ Found domain-packs at: {domain_packs_path}")
            break

    if not domain_packs_path:
        print("✗ domain-packs directory not found at:")
        for p in possible_paths:
            print(f"   - {p}")
        return

    # Create table
    create_conflicting_rules_table(db)

    # Seed each domain pack
    domains_seeded = 0
    for domain_pack_dir in domain_packs_path.iterdir():
        if domain_pack_dir.is_dir():
            domain_id = domain_pack_dir.name
            print(f"Seeding {domain_id}...")
            count = seed_conflicting_rules(db, domain_id, workspace_id)
            if count > 0:
                domains_seeded += 1

    if domains_seeded > 0:
        print(f"✓ All conflicting rules seeded ({domains_seeded} domains)")
    else:
        print("✗ No conflicting rules were seeded")
