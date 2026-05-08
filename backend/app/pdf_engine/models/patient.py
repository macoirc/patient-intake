"""Patient data model and facility configuration"""

from dataclasses import dataclass, field
from datetime import date


FACILITIES = {
    "facility_1": {
        "name": "Sample Facility 1",
        "address": "123 Main Street",
        "city_state_zip": "Anytown, PA 12345",
        "phone": "(777) 867-5309",
        "fax": "(777) 867-5310",
    },
    "facility_2": {
        "name": "Sample Facility 2",
        "address": "321 Oak Avenue",
        "city_state_zip": "Othertown, PA 12354",
        "phone": "(888) 555-6793",
        "fax": "(888) 555-6794",
    },
}


@dataclass
class PatientData:
    """Patient information used to populate intake forms."""

    patient_id: str
    patient_name: str
    facility: str
    admission_date: str = ""
    date_of_birth: str = ""
    counselor_name: str = ""
    medical_director: str = "Trapper John, MD"
    form_responses: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.patient_id:
            raise ValueError("patient_id is required")
        if not self.patient_id.isdigit():
            raise ValueError("patient_id must be numeric")
        if not self.patient_name:
            raise ValueError("patient_name is required")
        if self.facility not in FACILITIES:
            raise ValueError(
                f"facility must be one of: {', '.join(FACILITIES.keys())}"
            )
        if not self.admission_date:
            raise ValueError("admission_date is required")
        if not self.counselor_name:
            raise ValueError("counselor_name is required")

    @property
    def facility_info(self) -> dict:
        """Return info dict for the patient's active facility."""
        return FACILITIES[self.facility]

    @property
    def other_facility_info(self) -> dict:
        """Return info dict for the other facility."""
        other_key = next(k for k in FACILITIES if k != self.facility)
        return FACILITIES[other_key]

    @property
    def other_facility_key(self) -> str:
        return next(k for k in FACILITIES if k != self.facility)
