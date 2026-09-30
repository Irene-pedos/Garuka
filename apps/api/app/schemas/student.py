import uuid
from datetime import date

from pydantic import BaseModel

from app.models.student import ConsentSourceEnum, SexEnum, StudentStatusEnum
from app.models.user import LanguageEnum


class ClassCreate(BaseModel):
    name: str
    grade: int
    academic_year: int
    class_teacher_id: uuid.UUID | None = None


class ClassUpdate(BaseModel):
    name: str | None = None
    grade: int | None = None
    academic_year: int | None = None
    class_teacher_id: uuid.UUID | None = None


class ClassResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    name: str
    grade: int
    academic_year: int
    class_teacher_id: uuid.UUID | None = None

    class Config:
        from_attributes = True


class GuardianCreate(BaseModel):
    full_name: str
    phone_e164: str
    relationship: str | None = "guardian"
    is_primary: bool = True
    language: LanguageEnum = LanguageEnum.rw


class GuardianResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    phone_masked: str
    language: LanguageEnum
    consent_source: ConsentSourceEnum | None = None
    sms_opt_out: bool

    class Config:
        from_attributes = True


class StudentCreate(BaseModel):
    school_id: uuid.UUID
    class_id: uuid.UUID
    roll_number: int
    full_name: str
    student_code: str | None = None
    sex: SexEnum | None = None
    birth_year: int | None = None
    is_repeater: bool = False
    enrolled_at: date | None = None


class StudentUpdate(BaseModel):
    class_id: uuid.UUID | None = None
    roll_number: int | None = None
    full_name: str | None = None
    student_code: str | None = None
    sex: SexEnum | None = None
    birth_year: int | None = None
    is_repeater: bool | None = None
    status: StudentStatusEnum | None = None


class StudentResponse(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    class_id: uuid.UUID
    class_name: str | None = None
    roll_number: int
    full_name: str
    student_code: str | None = None
    sex: SexEnum | None = None
    birth_year: int | None = None
    is_repeater: bool
    status: StudentStatusEnum
    enrolled_at: date
    guardians: list[GuardianResponse] = []

    class Config:
        from_attributes = True


class CSVImportRowError(BaseModel):
    row: int
    message: str


class CSVImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[CSVImportRowError]
