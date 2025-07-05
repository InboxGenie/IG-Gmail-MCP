from typing import List, Literal, Optional
from pydantic import BaseModel
from datetime import datetime

class QueryFilter(BaseModel):
    inboxes: Optional[List[Literal["ALL", "GMAIL"]]] = None
    recipients: Optional[List[str]] = None
    from_email: Optional[str] = None
    start_date: Optional[datetime] = None
    start_time: Optional[str] = None
    end_date: Optional[datetime] = None
    end_time: Optional[str] = None


    def start_date_timestamp(self) -> int:
        day, month, year = self.start_date.day, self.start_date.month, self.start_date.year
        time: str = self.start_time or "00:00"
        _date: datetime = datetime.strptime(f"{day}/{month}/{year} {time}", "%d/%m/%Y %H:%M")
        return int(_date.timestamp())

    def end_date_timestamp(self) -> int:
        day, month, year = self.end_date.day, self.end_date.month, self.end_date.year
        time: str = self.end_time or "23:59"
        _date: datetime = datetime.strptime(f"{day}/{month}/{year} {time}", "%d/%m/%Y %H:%M")
        return int(_date.timestamp())


type OrderableField = Literal["date"]
type OrderDirection = Literal["asc", "desc"]