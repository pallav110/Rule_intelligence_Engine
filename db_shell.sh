#!/bin/bash

echo "🐳 Connecting to Rule Intelligence Engine Database"
echo "================================================"
echo "Database: rule_intelligence_engine"
echo "User: rie_user"
echo "Container: rie_postgres"
echo ""
echo "Type SQL commands directly (e.g., SELECT * FROM rules;)"
echo "Exit with: \\q or Ctrl+D"
echo "================================================"
echo ""

# Connect to the PostgreSQL container
docker exec -i rie_postgres psql -U rie_user -d rule_intelligence_engine
