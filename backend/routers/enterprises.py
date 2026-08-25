from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import crud, schemas
from database import get_db
from models import DataSource, Department
from security import get_current_user

router = APIRouter(prefix="/api/admin/enterprises", tags=["enterprises"], dependencies=[Depends(get_current_user)])

@router.get("/", response_model=List[schemas.EnterpriseResponse])
def read_enterprises(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_enterprises(db, skip=skip, limit=limit)


@router.get("/{enterprise_id}/data_sources", response_model=List[schemas.DataSourceResponse])
def read_enterprise_data_sources(enterprise_id: int, db: Session = Depends(get_db)):
    if crud.get_enterprise(db, enterprise_id) is None:
        raise HTTPException(status_code=404, detail="Enterprise not found")
    return crud.get_enterprise_data_sources(db, enterprise_id)

@router.get("/{enterprise_id}", response_model=schemas.EnterpriseResponse)
def read_enterprise(enterprise_id: int, db: Session = Depends(get_db)):
    db_ent = crud.get_enterprise(db, enterprise_id)
    if db_ent is None:
        raise HTTPException(status_code=404, detail="Enterprise not found")
    return db_ent

@router.post("/", response_model=schemas.EnterpriseResponse)
def create_enterprise(enterprise: schemas.EnterpriseCreate, db: Session = Depends(get_db)):
    name = enterprise.name.strip()
    duplicate = next(
        (item for item in crud.get_enterprises(db, limit=10000) if item.name.strip().casefold() == name.casefold()),
        None,
    )
    if duplicate:
        raise HTTPException(status_code=409, detail={"message": f"企业名称“{name}”已存在"})
    return crud.create_enterprise(db, enterprise.model_copy(update={"name": name}))

@router.put("/{enterprise_id}", response_model=schemas.EnterpriseResponse)
def update_enterprise(enterprise_id: int, enterprise: schemas.EnterpriseUpdate, db: Session = Depends(get_db)):
    name = enterprise.name.strip()
    duplicate = next(
        (
            item for item in crud.get_enterprises(db, limit=10000)
            if item.id != enterprise_id and item.name.strip().casefold() == name.casefold()
        ),
        None,
    )
    if duplicate:
        raise HTTPException(status_code=409, detail={"message": f"企业名称“{name}”已存在"})
    db_ent = crud.update_enterprise(db, enterprise_id, enterprise.model_copy(update={"name": name}))
    if db_ent is None:
        raise HTTPException(status_code=404, detail="Enterprise not found")
    return db_ent

@router.delete("/{enterprise_id}", response_model=dict)
def delete_enterprise(enterprise_id: int, db: Session = Depends(get_db)):
    if db.query(DataSource).filter(DataSource.enterprise_id == enterprise_id).first() or db.query(Department).filter(Department.enterprise_id == enterprise_id).first():
        raise HTTPException(status_code=409, detail={"message": "该企业已关联数据源或部门，不能删除；请先迁移或删除下属记录"})
    success = crud.delete_enterprise(db, enterprise_id)
    if not success:
        raise HTTPException(status_code=404, detail="Enterprise not found")
    return {"detail": "deleted"}
