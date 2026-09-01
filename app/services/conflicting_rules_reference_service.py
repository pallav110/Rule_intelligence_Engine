"""Service to load and manage conflicting rules reference data."""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from sqlalchemy import text


class ConflictingRulesService:
    """Load and manage known conflicting rules from domain packs."""

    @staticmethod
    def load_conflicting_rules_from_json(domain_id: str) -> List[Dict[str, Any]]:
        """
        Load conflicting_rules.json from domain pack.

        Returns list of conflicting rule definitions:
        [
            {
                "rule_id": "EC_CR001",
                "conflicts_with": "EC_R003",
                "business_term": "revenue",
                "operation": "include",
                "conflict_type": "direct_conflict",
                ...
            }
        ]
        """
        try:
            rules_path = (
                Path(__file__).parent.parent.parent /
                "rie_ml" / "domain-packs" / domain_id / "rules" / "conflicting_rules.json"
            )

            if not rules_path.exists():
                return []

            with open(rules_path, 'r') as f:
                rules = json.load(f)
                return rules if isinstance(rules, list) else []
        except Exception as e:
            print(f"Error loading conflicting rules for {domain_id}: {e}")
            return []

    @staticmethod
    def seed_conflicting_rules_to_db(db, domain_id: str, workspace_id: str) -> int:
        """
        Load conflicting_rules.json and insert into database.

        Creates a mapping table:
        - rule_id (the conflicting rule)
        - conflicts_with (the active rule it conflicts with)
        - conflict_type (direct_conflict, potential_conflict, temporal_conflict)
        - business_term, operation, conditions, affected_entities

        Returns: Number of rules inserted
        """
        rules = ConflictingRulesService.load_conflicting_rules_from_json(domain_id)

        if not rules:
            print(f"No conflicting rules found for {domain_id}")
            return 0

        inserted_count = 0

        # First, ensure the conflicting_rules table exists
        try:
            create_table_query = text("""
                CREATE TABLE IF NOT EXISTS conflicting_rules_reference (
                    id SERIAL PRIMARY KEY,
                    workspace_id VARCHAR(255) NOT NULL,
                    domain_id VARCHAR(255) NOT NULL,
                    rule_id VARCHAR(255) NOT NULL UNIQUE,
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
            db.execute(create_table_query)
            db.commit()
        except Exception as e:
            print(f"Note: Table may already exist or error: {e}")

        # Insert each conflicting rule
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
                    ON CONFLICT (rule_id) DO UPDATE SET
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
                print(f"Error inserting rule {rule.get('rule_id')}: {e}")

        db.commit()
        print(f"✓ Seeded {inserted_count} conflicting rules for {domain_id}/{workspace_id}")
        return inserted_count

    @staticmethod
    def check_known_conflicts(db, rule_id: str, workspace_id: str, domain_id: str) -> List[Dict[str, Any]]:
        """
        Fast-path check: Look up rule_id in conflicting_rules_reference.

        Returns list of known conflicts for this rule:
        [
            {
                "conflicts_with": "EC_R003",
                "conflict_type": "direct_conflict",
                "description": "..."
            }
        ]
        """
        try:
            query = text("""
                SELECT
                    rule_id, conflicts_with, conflict_type, rule_name,
                    business_term, operation, description
                FROM conflicting_rules_reference
                WHERE workspace_id = :workspace_id
                  AND domain_id = :domain_id
                  AND (rule_id = :rule_id OR conflicts_with = :rule_id)
            """)

            result = db.execute(query, {
                "workspace_id": workspace_id,
                "domain_id": domain_id,
                "rule_id": rule_id
            })

            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
        except Exception as e:
            print(f"Error checking known conflicts for {rule_id}: {e}")
            return []
