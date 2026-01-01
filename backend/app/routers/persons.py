"""Person router for managing family members for joint tax returns."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models import get_db, Person
from ..schemas import PersonCreate, PersonUpdate, PersonResponse

router = APIRouter(prefix="/persons", tags=["persons"])


@router.get("/", response_model=List[PersonResponse])
async def get_persons(db: Session = Depends(get_db)) -> List[PersonResponse]:
    """Get all persons (for family tax returns)."""
    persons = db.query(Person).order_by(Person.is_primary.desc(), Person.name).all()
    return persons


@router.get("/{person_id}", response_model=PersonResponse)
async def get_person(person_id: int, db: Session = Depends(get_db)) -> PersonResponse:
    """Get a specific person by ID."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.post("/", response_model=PersonResponse)
async def create_person(person: PersonCreate, db: Session = Depends(get_db)) -> PersonResponse:
    """Create a new person (family member)."""
    # If this is the first person or marked as primary, ensure only one primary
    if person.is_primary:
        # Unset any existing primary
        db.query(Person).filter(Person.is_primary == True).update({"is_primary": False})

    # If no persons exist, make this one primary
    existing_count = db.query(Person).count()
    if existing_count == 0:
        person.is_primary = True

    db_person = Person(
        name=person.name,
        is_primary=person.is_primary,
        pps_number=person.pps_number,
        color=person.color,
    )
    db.add(db_person)
    db.commit()
    db.refresh(db_person)
    return db_person


@router.put("/{person_id}", response_model=PersonResponse)
async def update_person(
    person_id: int,
    person: PersonUpdate,
    db: Session = Depends(get_db)
) -> PersonResponse:
    """Update a person's details."""
    db_person = db.query(Person).filter(Person.id == person_id).first()
    if not db_person:
        raise HTTPException(status_code=404, detail="Person not found")

    if person.name is not None:
        db_person.name = person.name
    if person.pps_number is not None:
        db_person.pps_number = person.pps_number
    if person.color is not None:
        db_person.color = person.color

    db.commit()
    db.refresh(db_person)
    return db_person


@router.delete("/{person_id}")
async def delete_person(person_id: int, db: Session = Depends(get_db)):
    """Delete a person (cannot delete primary if they have transactions)."""
    db_person = db.query(Person).filter(Person.id == person_id).first()
    if not db_person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Check if person has transactions
    if db_person.transactions:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete person with transactions. Reassign transactions first."
        )

    db.delete(db_person)
    db.commit()
    return {"message": "Person deleted successfully"}


@router.post("/{person_id}/set-primary", response_model=PersonResponse)
async def set_primary_person(person_id: int, db: Session = Depends(get_db)) -> PersonResponse:
    """Set a person as the primary taxpayer."""
    db_person = db.query(Person).filter(Person.id == person_id).first()
    if not db_person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Unset any existing primary
    db.query(Person).filter(Person.is_primary == True).update({"is_primary": False})

    # Set this person as primary
    db_person.is_primary = True
    db.commit()
    db.refresh(db_person)
    return db_person


@router.get("/primary/default", response_model=PersonResponse)
async def get_or_create_primary(db: Session = Depends(get_db)) -> PersonResponse:
    """Get the primary person, creating a default one if none exists."""
    primary = db.query(Person).filter(Person.is_primary == True).first()

    if not primary:
        # Check if any person exists
        any_person = db.query(Person).first()
        if any_person:
            any_person.is_primary = True
            db.commit()
            db.refresh(any_person)
            return any_person

        # Create a default primary person
        primary = Person(
            name="Me",
            is_primary=True,
            color="#3B82F6",
        )
        db.add(primary)
        db.commit()
        db.refresh(primary)

    return primary
