from pydantic import BaseModel, Field


class DatasetVersionCreateRequest(BaseModel):
    dataset_name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    domain_pack_version: str = Field(min_length=1, max_length=50)
    annotation_version: str = Field(min_length=1, max_length=50)
    source: str = Field(min_length=1, max_length=50)
    path: str = Field(min_length=1, max_length=255)


class DatasetVersionResponse(BaseModel):
    dataset_version_id: str
    dataset_name: str
    version: str
    domain_pack_version: str
    annotation_version: str
    source: str
    path: str
    status: str


class DatasetVersionListResponse(BaseModel):
    datasets: list[DatasetVersionResponse]
