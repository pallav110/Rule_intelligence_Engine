"""Database diagnostic service to debug retrieval issues."""

from sqlalchemy import text


class DatabaseDiagnosticService:
    """Diagnose database queries and data availability."""

    @staticmethod
    def check_rules_for_workspace_domain(db, workspace_id: str, domain_id: str) -> dict:
        """Check what rules exist for a given workspace and domain."""
        try:
            query = text(
                """
                SELECT rule_id, business_term, operation, workspace_id, domain_id, status
                FROM rules
                WHERE workspace_id = :workspace_id
                  AND domain_id = :domain_id
                ORDER BY created_at DESC
                LIMIT 20
            """
            )
            result = db.execute(query, {"workspace_id": workspace_id, "domain_id": domain_id})
            rows = result.fetchall()

            return {
                "workspace_id": workspace_id,
                "domain_id": domain_id,
                "count": len(rows),
                "rules": [
                    {
                        "rule_id": row[0],
                        "business_term": row[1],
                        "operation": row[2],
                        "workspace_id": row[3],
                        "domain_id": row[4],
                        "status": row[5],
                    }
                    for row in rows
                ]
            }
        except Exception as e:
            return {
                "error": str(e),
                "workspace_id": workspace_id,
                "domain_id": domain_id
            }

    @staticmethod
    def check_all_rules(db) -> dict:
        """Check all rules in database."""
        try:
            query = text(
                """
                SELECT rule_id, business_term, operation, workspace_id, domain_id, status, created_at
                FROM rules
                ORDER BY created_at DESC
                LIMIT 50
            """
            )
            result = db.execute(query)
            rows = result.fetchall()

            # Group by workspace/domain
            groups = {}
            for row in rows:
                key = f"{row[3]}/{row[4]}"
                if key not in groups:
                    groups[key] = []
                groups[key].append({
                    "rule_id": row[0],
                    "business_term": row[1],
                    "operation": row[2],
                    "workspace_id": row[3],
                    "domain_id": row[4],
                    "status": row[5],
                    "created_at": row[6],
                })

            return {
                "total_rules": len(rows),
                "groups": groups
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def check_domain_packs(db) -> dict:
        """Check available domain packs."""
        try:
            query = text(
                """
                SELECT domain_pack_id, name, status
                FROM domain_packs
                ORDER BY created_at DESC
                LIMIT 20
            """
            )
            result = db.execute(query)
            rows = result.fetchall()

            return {
                "count": len(rows),
                "packs": [
                    {
                        "domain_pack_id": row[0],
                        "name": row[1],
                        "status": row[2],
                    }
                    for row in rows
                ]
            }
        except Exception as e:
            return {"error": str(e)}
