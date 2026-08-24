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
- Separate annotations for classification + rule extraction
- Attributes: Feedback Type, Rule Category, Actionability, Clarification Required, Business Term, Operation, Conditions, Scope, Time Window, Thresholds, Affected Tables/Columns, Duplicate/Conflict Relationships, # Extracted Rules, NER Labels
- Minimum 2 reviewers, senior review for disagreements

## 4.8 Dataset Distribution and Rule Families
- Metric Definition (30%), Filter Rules (20%), Mapping Rules (15%), Access Rules (15%), Data Quality Rules (10%), Ambiguous/Clarification (10%)
- rule_family_id groups paraphrases of same rule
- Prevents data leakage by keeping same-family examples in same split

## 4.9 Dataset Versioning and Source Tracking
- Version control for all datasets
- Metadata: Version, Creation Date, Source, License, Annotation Version, # Samples, Business Domain, Supported ML Task
