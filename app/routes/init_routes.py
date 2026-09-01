"""Endpoint to initialize/seed reference data (conflicting rules, etc.)."""


def register_init_endpoints(app, db_session):
    """Register initialization endpoints."""
    from fastapi import Depends
    from app.db.database import get_db
    from app.db.migrations.seed_conflicting_rules import (
        create_conflicting_rules_table,
        seed_conflicting_rules,
        seed_all_domains
    )

    @app.post("/v1/admin/init/seed-conflicting-rules")
    def seed_conflicting_rules_endpoint(
        workspace_id: str = "e8af6af9-3bbe-4117-a007-f55db418bc30",
        domain_id: str = None,
        db=Depends(get_db),
    ):
        """
        Admin endpoint to seed conflicting_rules.json into database.

        Usage:
        - POST /v1/admin/init/seed-conflicting-rules?workspace_id=WS&domain_id=ecommerce
        - POST /v1/admin/init/seed-conflicting-rules?workspace_id=WS  (seeds all domains)
        """
        try:
            # Create table
            create_conflicting_rules_table(db)

            if domain_id:
                # Seed single domain
                count = seed_conflicting_rules(db, domain_id, workspace_id)
                return {
                    "success": True,
                    "message": f"Seeded {count} conflicting rules for {domain_id}",
                    "domain_id": domain_id,
                    "count": count,
                    "workspace_id": workspace_id
                }
            else:
                # Seed all domains
                seed_all_domains(db, workspace_id)
                return {
                    "success": True,
                    "message": "Seeded conflicting rules for all domain packs",
                    "workspace_id": workspace_id
                }

        except Exception as e:
            print(f"Error seeding conflicting rules: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    @app.get("/v1/admin/check-conflicting-rules")
    def check_conflicting_rules_endpoint(
        rule_id: str,
        workspace_id: str = "e8af6af9-3bbe-4117-a007-f55db418bc30",
        domain_id: str = "ecommerce",
        db=Depends(get_db),
    ):
        """
        Check if a rule has known conflicts.

        Usage:
        - GET /v1/admin/check-conflicting-rules?rule_id=EC_R001&workspace_id=WS&domain_id=ecommerce
        """
        try:
            from sqlalchemy import text

            query = text("""
                SELECT rule_id, conflicts_with, conflict_type, rule_name, description
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

            conflicts = [dict(row._mapping) for row in result]

            return {
                "rule_id": rule_id,
                "has_known_conflicts": len(conflicts) > 0,
                "conflicts": conflicts,
                "workspace_id": workspace_id,
                "domain_id": domain_id
            }

        except Exception as e:
            print(f"Error checking conflicts: {e}")
            return {
                "error": str(e),
                "rule_id": rule_id
            }
