from pydantic import BaseModel


class UserLogRequest(BaseModel):
    session_id: str
    action: str
    page: str | None = None
    asset_id: str | None = None
    details: dict | None = None
