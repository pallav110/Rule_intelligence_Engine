# Section 4: Data Sources and Dataset Preparation

## Overview
The Rule Intelligence Engine (RIE) operates using controlled datasets...

## 4.1 Synthetic Feedback Dataset
- ~500–1,000 labelled examples
- Generated via manual + programmatic + LLM methods
- Manually reviewed before inclusion

## 4.2 Synthetic Business Domain Packs
### E-Commerce
- Customers, Orders, Order Items, Products, Payments, Refunds, Regions

### Customer Support
- Customers, Tickets, Agents, Departments, Ticket Events, Satisfaction Scores

### SaaS Subscription Management
- Organizations, Users, Subscription Plans, Invoices, Payments, Product Events

## 4.3 Public Datasets
- Kaggle, UCI ML, Govt open data
- Used for schema context, not as-is label sources

## 4.4 Manually Reviewed Evaluation Dataset
- Frozen benchmark (~200 examples)
- Never used in training/validation
- Ground truth for comparison

## 4.5 Data Preparation Strategy

| Dataset | Size | Purpose |
|---------|------|---------|
| Training | ~600 | Model training |
| Validation | ~150 | Hyperparameter tuning |
| Frozen Evaluation | ~200 | Final evaluation |
| Duplicate Pairs | ~150 | Duplicate detection eval |
| Conflict Pairs | ~150 | Conflict detection eval |
| Ambiguous Examples | ~100 | Clarification handling eval |

## 4.6 Data Privacy and Independence
- No production data used
- All synthetic or public
- Manual review required for any future production feedback

## 4.7 Dataset Annotation Guidelines

To ensure consistency across training and evaluation datasets, every feedback sample follows a standardized annotation protocol.

Each feedback instance is annotated with the following attributes:

### Classification Annotations

| Attribute | Description | Values |
|-----------|-------------|--------|
| **Feedback Type** | Identifies whether the feedback represents a business rule, issue report, feature request, question, or general feedback | `Business Rule`, `Issue Report`, `Feature Request`, `Question`, `General Feedback` |
| **Rule Category** | Categorizes actionable feedback into rule families | `Metric Definition`, `Filter Rule`, `Mapping Rule`, `Access Rule`, `Join Rule`, `Data Quality Rule` |
| **Actionability** | Determines whether rule extraction should continue | `true` / `false` |
| **Clarification Requirement** | Predicts whether additional information is likely to be required before rule extraction | `true` / `false` |

### Extraction Annotations

| Attribute | Description |
|-----------|-------------|
| **Business Term** | Primary business concept referenced (e.g., "Revenue") |
| **Operation** | Rule operation (e.g., Include, Exclude, Restrict) |
| **Conditions** | Structured field/operator/value tuples |
| **Scope** | Business scope of application |
| **Time Window** | Temporal constraint (if any) |
| **Threshold Values** | Numeric comparison values |
| **Affected Tables and Columns** | Database entities referenced |

### Relationship Annotations

| Attribute | Description |
|-----------|-------------|
| **Duplicate Relationship** | Whether feedback duplicates existing rules |
| **Conflict Relationship** | Whether feedback conflicts with existing rules |
| **Number of Extracted Rules** | Count of independent rules in the feedback |

### NER Annotations

| Attribute | Description |
|-----------|-------------|
| **Named Entity Recognition (NER) Labels** | BIO-tagged spans for Business Terms, Operations, Tables, Columns, Conditions, Values, Scopes, Time Windows, Thresholds |

> All annotations are independently reviewed by at least two reviewers. In cases of disagreement, the sample is escalated to a senior reviewer for final determination.

## 4.8 Dataset Distribution and Rule Families
- Metric Definition (30%), Filter Rules (20%), Mapping Rules (15%), Access Rules (15%), Data Quality Rules (10%), Ambiguous/Clarification (10%)
- rule_family_id groups paraphrases of same rule
- Prevents data leakage by keeping same-family examples in same split

## 4.9 Dataset Versioning and Source Tracking
- Version control for all datasets
- Metadata: Version, Creation Date, Source, License, Annotation Version, # Samples, Business Domain, Supported ML Task
