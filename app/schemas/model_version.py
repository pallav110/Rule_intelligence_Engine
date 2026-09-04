from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field


class ModelVersionStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ModelType(str, Enum):
    CLASSIFICATION = "classification"
    RULE_EXTRACTION = "rule-extraction"
    DUPLICATE_DETECTION = "duplicate-detection"
    CONFLICT_DETECTION = "conflict-detection"
    CLARIFICATION = "clarification"
    SCHEMA_VALIDATION = "schema-validation"
    OTHER = "other"


class ModelVersionCreateRequest(BaseModel):
    model_name: str = Field(min_length=1, description="Model name (e.g., distilbert-classifier)")
    model_type: ModelType = Field(default=ModelType.OTHER, description="Model type per spec 8.11")
    version: str = Field(min_length=1, description="Semantic version (e.g., v1.0.0)")
    description: Optional[str] = Field(None, description="Model description")
    checkpoint_path: str = Field(min_length=1, description="Path to model checkpoint/artifact")
    training_dataset_version_id: Optional[str] = Field(None, description="Training dataset version ID")
    validation_dataset_version_id: Optional[str] = Field(None, description="Validation dataset version ID")
    annotation_scheme_version: Optional[str] = Field(None, description="Annotation scheme version")
    hyperparameters: Optional[Dict[str, Any]] = Field(None, description="Training hyperparameters")
    training_timestamp: Optional[datetime] = Field(None, description="Training timestamp")
    evaluation_metrics: Optional[Dict[str, Any]] = Field(None, description="Evaluation metrics")


class ModelVersionUpdateRequest(BaseModel):
    status: Optional[ModelVersionStatus] = Field(None, description="Promote/demote model status")
    description: Optional[str] = None
    evaluation_metrics: Optional[Dict[str, Any]] = None


class ModelVersionResponse(BaseModel):
    model_version_id: str
    model_name: str
    model_type: ModelType
    version: str
    description: Optional[str] = None
    checkpoint_path: str
    training_dataset_version_id: Optional[str] = None
    validation_dataset_version_id: Optional[str] = None
    annotation_scheme_version: Optional[str] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    training_timestamp: Optional[datetime] = None
    evaluation_metrics: Optional[Dict[str, Any]] = None
    status: ModelVersionStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True