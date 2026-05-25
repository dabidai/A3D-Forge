from pydantic import BaseModel


class RepairRequest(BaseModel):
    asset_id: str


class RepairResponse(BaseModel):
    asset_id: str
    task_id: str
    status: str
    defects_found: int
    auto_repaired: int
    needs_manual: int
    report: dict


class DefectInfo(BaseModel):
    type: str
    level: str
    description: str
    repairable: bool
    count: int


class DefectAnalysisResponse(BaseModel):
    asset_id: str
    overall_severity: str
    defects: list[DefectInfo]
    repair_script: str | None = None
    tutorial: str | None = None
