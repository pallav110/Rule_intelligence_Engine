"""Dataset splitter with rule_family_id awareness to prevent data leakage."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections import defaultdict


@dataclass
class SplitResult:
    """Result of dataset splitting."""
    train: list[dict[str, Any]]
    val: list[dict[str, Any]]
    test: list[dict[str, Any]]
    split_info: dict[str, Any]


class DatasetSplitter:
    """Splits dataset into train/val/test while keeping rule families together."""
    
    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed
        random.seed(random_seed)
    
    def split_by_rule_family(
        self,
        records: list[dict[str, Any]],
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        target_train_size: int | None = None,
        target_val_size: int | None = None,
        target_test_size: int | None = None,
    ) -> SplitResult:
        """
        Split records by rule_family_id to prevent data leakage.
        
        All records with the same rule_family_id will go to the same split.
        """
        # Group records by rule_family_id
        rule_family_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            rfid = record.get("rule_family_id", "unknown")
            rule_family_groups[rfid].append(record)
        
        # Convert to list for shuffling
        family_ids = list(rule_family_groups.keys())
        random.shuffle(family_ids)
        
        # Calculate target sizes if provided
        total_records = len(records)
        if target_train_size and target_val_size and target_test_size:
            # Use target sizes
            train_target = target_train_size
            val_target = target_val_size
            test_target = target_test_size
        else:
            # Use ratios
            train_target = int(total_records * train_ratio)
            val_target = int(total_records * val_ratio)
            test_target = total_records - train_target - val_target
        
        # Allocate families to splits
        train_families = []
        val_families = []
        test_families = []
        
        train_count = 0
        val_count = 0
        test_count = 0
        
        for family_id in family_ids:
            family_size = len(rule_family_groups[family_id])
            
            # Try to fill test first (frozen evaluation set)
            if test_count + family_size <= test_target:
                test_families.append(family_id)
                test_count += family_size
            # Then fill validation
            elif val_count + family_size <= val_target:
                val_families.append(family_id)
                val_count += family_size
            # Rest goes to training
            else:
                train_families.append(family_id)
                train_count += family_size
        
        # Assign records to splits
        train_records = []
        val_records = []
        test_records = []
        
        for family_id in train_families:
            train_records.extend(rule_family_groups[family_id])
        
        for family_id in val_families:
            val_records.extend(rule_family_groups[family_id])
        
        for family_id in test_families:
            test_records.extend(rule_family_groups[family_id])
        
        # Build split info
        split_info = {
            "total_records": total_records,
            "total_rule_families": len(family_ids),
            "train": {
                "count": len(train_records),
                "families": len(train_families),
                "family_ids": train_families,
                "ratio": len(train_records) / total_records if total_records > 0 else 0,
            },
            "val": {
                "count": len(val_records),
                "families": len(val_families),
                "family_ids": val_families,
                "ratio": len(val_records) / total_records if total_records > 0 else 0,
            },
            "test": {
                "count": len(test_records),
                "families": len(test_families),
                "family_ids": test_families,
                "ratio": len(test_records) / total_records if total_records > 0 else 0,
            },
            "random_seed": self.random_seed,
        }
        
        return SplitResult(train_records, val_records, test_records, split_info)
    
    def create_task_specific_datasets(
        self,
        records: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Create task-specific datasets from the full dataset.
        
        Returns:
            - classification: For feedback classification task
            - extraction: For structured rule extraction task
            - clarification: For clarification detection task
        """
        classification: list[dict[str, Any]] = []
        extraction: list[dict[str, Any]] = []
        clarification: list[dict[str, Any]] = []
        
        for record in records:
            # Classification dataset
            classification_record = {
                "feedback_id": record.get("feedback_id"),
                "feedback_text": record.get("feedback_text"),
                "feedback_type": record.get("feedback_type"),
                "rule_category": record.get("rule_category"),
                "is_actionable": record.get("is_actionable"),
                "requires_clarification": record.get("requires_clarification"),
            }
            classification.append(classification_record)
            
            # Extraction dataset (only for actionable records with rules)
            if record.get("is_actionable") and record.get("rules"):
                extraction_record = {
                    "feedback_id": record.get("feedback_id"),
                    "feedback_text": record.get("feedback_text"),
                    "rules": record.get("rules"),
                    "rule_family_id": record.get("rule_family_id"),
                }
                extraction.append(extraction_record)
            
            # Clarification dataset
            if record.get("requires_clarification"):
                clarification_record = {
                    "feedback_id": record.get("feedback_id"),
                    "feedback_text": record.get("feedback_text"),
                    "requires_clarification": True,
                    "reason": record.get("feedback_type", "unclear"),
                }
                clarification.append(clarification_record)
        
        return {
            "classification": classification,
            "extraction": extraction,
            "clarification": clarification,
        }
    
    def create_duplicate_pairs(
        self,
        records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Create duplicate pairs from records with same rule_family_id.
        
        Returns pairs of feedback IDs that are semantically equivalent.
        """
        # Group by rule_family_id
        rule_family_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            rfid = record.get("rule_family_id")
            if rfid and len(rule_family_groups[rfid]) < 2:  # Only families with 2+ records
                rule_family_groups[rfid].append(record)
        
        # Create pairs
        pairs: list[dict[str, Any]] = []
        pair_id = 0
        
        for rfid, group in rule_family_groups.items():
            if len(group) >= 2:
                # Create all pairs within the family
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        pair_id += 1
                        pairs.append({
                            "pair_id": f"DP{pair_id:04d}",
                            "feedback_id_1": group[i].get("feedback_id"),
                            "feedback_id_2": group[j].get("feedback_id"),
                            "rule_family_id": rfid,
                            "relationship": "semantic_duplicate",
                        })
        
        return pairs
    
    def create_conflict_pairs(
        self,
        records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Create conflict pairs from records with conflicting rule_family_ids.
        
        Looks for rule_family_ids with "_conflict" suffix and pairs them.
        """
        # Find conflict pairs
        conflict_map: dict[str, str] = {}  # base_id -> conflict_id
        for record in records:
            rfid = record.get("rule_family_id", "")
            if rfid.endswith("_conflict"):
                base_id = rfid.replace("_conflict", "")
                conflict_map[base_id] = rfid
        
        # Create pairs
        pairs: list[dict[str, Any]] = []
        pair_id = 0
        
        records_by_id = {r.get("feedback_id"): r for r in records}
        
        for base_rfid, conflict_rfid in conflict_map.items():
            # Find records with these rule_family_ids
            base_records = [r for r in records if r.get("rule_family_id") == base_rfid]
            conflict_records = [r for r in records if r.get("rule_family_id") == conflict_rfid]
            
            if base_records and conflict_records:
                pair_id += 1
                pairs.append({
                    "pair_id": f"CP{pair_id:04d}",
                    "feedback_id_1": base_records[0].get("feedback_id"),
                    "feedback_id_2": conflict_records[0].get("feedback_id"),
                    "rule_family_id_1": base_rfid,
                    "rule_family_id_2": conflict_rfid,
                    "relationship": "direct_conflict",
                })
        
        return pairs
