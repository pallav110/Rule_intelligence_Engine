from enum import Enum

from pydantic import BaseModel, Field


class ModelVersionStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"


class ModelVersionCreateRequest(BaseModel):
    model_name: str = Field(min_length=1)
    version: str = Field(min_length=1)


class ModelVersionResponse(BaseModel):
    model_version_id: str
    model_name: str
    version: str
    status: ModelVersionStatus
    artifact_path: str