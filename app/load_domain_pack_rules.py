"""Load domain pack rules into database with embeddings for Phase 3 pgvector search."""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import SessionLocal
from app.db.models.rule import Rule
from app.db.models.workspace import Workspace
from app.services.embedding_service import get_embedding_service
from sqlalchemy import text


def load_domain_pack_rules():
    """Load all domain pack rules into the database with embeddings."""

    db = SessionLocal()

    try:
        # Base workspace for domain pack rules
        WORKSPACE_ID = "domain_pack_workspace"

        # Create workspace if it doesn't exist
        existing_workspace = db.query(Workspace).filter_by(workspace_id=WORKSPACE_ID).first()
        if not existing_workspace:
            workspace = Workspace(
                workspace_id=WORKSPACE_ID,
                name="Domain Pack Rules",
                description="System workspace for domain pack reference rules",
                status="active",
            )
            db.add(workspace)
            db.commit()
            print(f"✅ Created workspace: {WORKSPACE_ID}\n")

        domain_packs_dir = Path(__file__).parent.parent / "rie_ml" / "domain-packs"
        domains = ["ecommerce", "customer_support", "saas_subscription"]

        embedding_service = get_embedding_service()
        total_loaded = 0

        for domain in domains:
            rules_file = domain_packs_dir / domain / "rules" / "active_rules.json"

            if not rules_file.exists():
                print(f"⚠️  Rules file not found: {rules_file}")
                continue

            with open(rules_file) as f:
                rules = json.load(f)

            print(f"\n📦 Loading {len(rules)} rules from {domain}...")

            for rule_data in rules:
                rule_id = rule_data.get("rule_id")

                # Check if rule already exists
                existing = db.query(Rule).filter_by(rule_id=rule_id).first()
                if existing:
                    print(f"  ⏭️  Skipping {rule_id} (already exists)")
                    continue

                # Create rule record
                rule = Rule(
                    rule_id=rule_id,
                    workspace_id=WORKSPACE_ID,
                    domain_id=domain,
                    business_term=rule_data.get("business_term"),
                    rule_category=rule_data.get("rule_category", "filter_rule"),
                    operation=rule_data.get("operation"),
                    conditions=rule_data.get("conditions", []),
                    scope=rule_data.get("scope", "global"),
                    affected_entities=rule_data.get("affected_entities", {}),
                    affected_tables=rule_data.get("affected_entities", {}).get("tables", []),
                    affected_columns=rule_data.get("affected_entities", {}).get("columns", []),
                    threshold=rule_data.get("threshold"),
                    time_window=rule_data.get("time_window", {}),
                    status="active",
                )
                db.add(rule)
                db.flush()

                # Generate and store embedding
                embedding_result = embedding_service.generate_rule_embedding(
                    rule={
                        "rule_id": rule_id,
                        "workspace_id": WORKSPACE_ID,
                        "business_term": rule_data.get("business_term"),
                        "operation": rule_data.get("operation"),
                        "conditions": rule_data.get("conditions", []),
                        "scope": rule_data.get("scope", "global"),
                        "affected_entities": rule_data.get("affected_entities", {}),
                        "time_window": rule_data.get("time_window", {}),
                    },
                    db=db,
                )

                if embedding_result and embedding_result.get("persisted"):
                    print(f"  ✅ Loaded {rule_id}: {rule_data.get('business_term')}")
                    total_loaded += 1
                else:
                    print(f"  ⚠️  Failed to generate embedding for {rule_id}")

            db.commit()

        print(f"\n✅ Successfully loaded {total_loaded} rules with embeddings")

        # Verify the data
        rule_count = db.execute(text("SELECT COUNT(*) FROM rules")).scalar()
        embedding_count = db.execute(text("SELECT COUNT(*) FROM rule_embeddings")).scalar()

        print(f"\n📊 Database status:")
        print(f"   Rules: {rule_count}")
        print(f"   Embeddings: {embedding_count}")

    except Exception as e:
        print(f"\n❌ Error loading domain pack rules: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 Loading domain pack rules into database with pgvector embeddings...\n")
    load_domain_pack_rules()
