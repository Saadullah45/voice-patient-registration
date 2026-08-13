"""Request/response schemas + all server-side validation.

The voice agent is NOT trusted for validation. Every rule in the data model is
enforced here so the API is safe even if called directly (rubric item: "do not
rely solely on the voice agent for validation").
"""
import re
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# --- constants --------------------------------------------------------------

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z '\-]*$")
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}
ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


class Sex(str, Enum):
    male = "Male"
    female = "Female"
    other = "Other"
    decline = "Decline to Answer"


# --- reusable validators ----------------------------------------------------

def _normalize_phone(value: str) -> str:
    """Strip to digits, drop a leading US country code, require exactly 10."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("phone_number must be a valid 10-digit U.S. number")
    if digits[0] in "01":
        raise ValueError("phone_number area code cannot start with 0 or 1")
    return digits


def _validate_name(value: str, field: str) -> str:
    value = (value or "").strip()
    if not (1 <= len(value) <= 50) or not NAME_RE.match(value):
        raise ValueError(f"{field} must be 1-50 letters (hyphens/apostrophes allowed)")
    return value


def _coerce_dob(value) -> date:
    """Accept MM/DD/YYYY (what the voice agent produces) or ISO YYYY-MM-DD."""
    if isinstance(value, date) and not isinstance(value, datetime):
        parsed = value
    else:
        s = str(value).strip()
        parsed = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(s, fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError("date_of_birth must be MM/DD/YYYY")
    if parsed > date.today():
        raise ValueError("date_of_birth cannot be in the future")
    if parsed.year < 1900:
        raise ValueError("date_of_birth year is implausible")
    return parsed


# --- create -----------------------------------------------------------------

class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    sex: Sex
    phone_number: str
    email: Optional[EmailStr] = None
    address_line_1: str = Field(min_length=1, max_length=200)
    address_line_2: Optional[str] = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str
    zip_code: str
    insurance_provider: Optional[str] = Field(default=None, max_length=120)
    insurance_member_id: Optional[str] = Field(default=None, max_length=60)
    preferred_language: str = "English"
    emergency_contact_name: Optional[str] = Field(default=None, max_length=120)
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name")
    @classmethod
    def _v_first(cls, v):
        return _validate_name(v, "first_name")

    @field_validator("last_name")
    @classmethod
    def _v_last(cls, v):
        return _validate_name(v, "last_name")

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def _v_dob(cls, v):
        return _coerce_dob(v)

    @field_validator("phone_number")
    @classmethod
    def _v_phone(cls, v):
        return _normalize_phone(v)

    @field_validator("emergency_contact_phone")
    @classmethod
    def _v_ec_phone(cls, v):
        return _normalize_phone(v) if v else v

    @field_validator("state")
    @classmethod
    def _v_state(cls, v):
        v = (v or "").strip().upper()
        if v not in US_STATES:
            raise ValueError("state must be a valid 2-letter U.S. abbreviation")
        return v

    @field_validator("zip_code")
    @classmethod
    def _v_zip(cls, v):
        v = (v or "").strip()
        if not ZIP_RE.match(v):
            raise ValueError("zip_code must be 5-digit or ZIP+4")
        return v


# --- update (all optional / partial) ---------------------------------------

class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    sex: Optional[Sex] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line_1: Optional[str] = Field(default=None, max_length=200)
    address_line_2: Optional[str] = Field(default=None, max_length=200)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = None
    zip_code: Optional[str] = None
    insurance_provider: Optional[str] = Field(default=None, max_length=120)
    insurance_member_id: Optional[str] = Field(default=None, max_length=60)
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = Field(default=None, max_length=120)
    emergency_contact_phone: Optional[str] = None

    # Reuse the same validators, but only when the field is actually provided.
    _v_first = field_validator("first_name")(lambda cls, v: _validate_name(v, "first_name") if v is not None else v)
    _v_last = field_validator("last_name")(lambda cls, v: _validate_name(v, "last_name") if v is not None else v)
    _v_dob = field_validator("date_of_birth", mode="before")(lambda cls, v: _coerce_dob(v) if v is not None else v)
    _v_phone = field_validator("phone_number")(lambda cls, v: _normalize_phone(v) if v else v)
    _v_ecphone = field_validator("emergency_contact_phone")(lambda cls, v: _normalize_phone(v) if v else v)

    @field_validator("state")
    @classmethod
    def _v_state(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if v not in US_STATES:
            raise ValueError("state must be a valid 2-letter U.S. abbreviation")
        return v

    @field_validator("zip_code")
    @classmethod
    def _v_zip(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not ZIP_RE.match(v):
            raise ValueError("zip_code must be 5-digit or ZIP+4")
        return v


# --- response ---------------------------------------------------------------

class PatientOut(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[str]
    address_line_1: str
    address_line_2: Optional[str]
    city: str
    state: str
    zip_code: str
    insurance_provider: Optional[str]
    insurance_member_id: Optional[str]
    preferred_language: str
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    model_config = {"from_attributes": True}
