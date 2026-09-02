"""
Seed domain_packs table with the three domain packs.

This fixes the foreign key constraint violation:
  analysis_runs.domain_pack_id references domain_packs.domain_pack_id
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "app"))

from db.database import SessionLocal
from db.models.domain_pack import DomainPack
from sqlalchemy.exc import IntegrityError


def seed_domain_packs():
    """Seed the domain_packs table with three domain packs"""

    db = SessionLocal()

    try:
        domain_packs = [
            {
                "domain_pack_id": "ecommerce",
                "name": "E-Commerce Domain Pack",
                "version": "v0.1.0",
                "description": "Domain pack for e-commerce business rules including orders, products, customers, payments, and refunds",
                "schema_metadata": {
                    "tables": ["customers", "orders", "order_items", "products", "payments", "refunds", "regions"],
                    "relationships": {
                        "orders": ["customers", "regions"],
                        "order_items": ["orders", "products"],
                        "payments": ["orders"],
                        "refunds": ["orders"]
                    }
                },
                "glossary": {
                    "Revenue": "Total payment amount from completed orders",
                    "Active Customer": "Customer with at least one order in the last 90 days",
                    "Cancelled Order": "Order with status = 'Cancelled'"
                },
                "taxonomy_mapping": {
                    "business_terms": ["Revenue", "Active Customer", "Order Value", "Refund Rate"],
                    "operations": ["calculate", "filter", "aggregate", "classify"]
                },
                "status": "active"
            },
            {
                "domain_pack_id": "customer_support",
                "name": "Customer Support Domain Pack",
                "version": "v0.1.0",
                "description": "Domain pack for customer support rules including tickets, agents, departments, and satisfaction",
                "schema_metadata": {
                    "tables": ["customers", "tickets", "agents", "departments", "ticket_events", "satisfaction_scores"],
                    "relationships": {
                        "tickets": ["customers", "agents", "departments"],
                        "ticket_events": ["tickets"],
                        "satisfaction_scores": ["tickets"]
                    }
                },
                "glossary": {
                    "Resolution Time": "Time from ticket creation to ticket closure",
                    "First Response Time": "Time from ticket creation to first agent response",
                    "Escalated Ticket": "Ticket with priority = 'High' or 'Critical'"
                },
                "taxonomy_mapping": {
                    "business_terms": ["Resolution Time", "SLA Compliance", "Agent Performance"],
                    "operations": ["measure", "classify", "escalate", "route"]
                },
                "status": "active"
            },
            {
                "domain_pack_id": "saas_subscription",
                "name": "SaaS Subscription Domain Pack",
                "version": "v0.1.0",
                "description": "Domain pack for SaaS subscription management including organizations, users, plans, invoices, and events",
                "schema_metadata": {
                    "tables": ["organizations", "users", "subscription_plans", "subscriptions", "invoices", "payments", "product_events"],
                    "relationships": {
                        "users": ["organizations"],
                        "subscriptions": ["organizations", "subscription_plans"],
                        "invoices": ["subscriptions"],
                        "payments": ["invoices"],
                        "product_events": ["users"]
                    }
                },
                "glossary": {
                    "MRR": "Monthly Recurring Revenue from active subscriptions",
                    "Churn Rate": "Percentage of cancelled subscriptions in a period",
                    "Active Subscription": "Subscription with status = 'Active'"
                },
                "taxonomy_mapping": {
                    "business_terms": ["MRR", "ARR", "Churn Rate", "Active Subscription"],
                    "operations": ["calculate", "track", "forecast", "segment"]
                },
                "status": "active"
            }
        ]

        added_count = 0
        skipped_count = 0

        for pack_data in domain_packs:
            # Check if domain pack already exists
            existing = db.query(DomainPack).filter_by(
                domain_pack_id=pack_data["domain_pack_id"]
            ).first()

            if existing:
                print(f"⚠️  Domain pack '{pack_data['domain_pack_id']}' already exists, skipping...")
                skipped_count += 1
                continue

            # Create new domain pack
            domain_pack = DomainPack(
                domain_pack_id=pack_data["domain_pack_id"],
                name=pack_data["name"],
                version=pack_data["version"],
                description=pack_data["description"],
                schema_metadata=pack_data["schema_metadata"],
                glossary=pack_data["glossary"],
                taxonomy_mapping=pack_data["taxonomy_mapping"],
                status=pack_data["status"],
                created_at=datetime.utcnow()
            )

            db.add(domain_pack)
            print(f"✅ Added domain pack: {pack_data['domain_pack_id']}")
            added_count += 1

        db.commit()

        print(f"\n{'=' * 60}")
        print(f"Domain Packs Seeding Complete")
        print(f"{'=' * 60}")
        print(f"Added: {added_count}")
        print(f"Skipped (already exist): {skipped_count}")
        print(f"Total: {len(domain_packs)}")

    except IntegrityError as e:
        db.rollback()
        print(f"❌ Integrity error: {e}")
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding domain packs: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding domain_packs table...")
    seed_domain_packs()
    print("\n✅ Done!")
