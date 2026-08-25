from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db
from security import get_current_user


router = APIRouter(prefix="/api/admin/departments", tags=["departments"], dependencies=[Depends(get_current_user)])


def _validate_enterprise(db: Session, enterprise_id: int) -> None:
    if crud.get_enterprise(db, enterprise_id) is None:
        raise HTTPException(status_code=400, detail={"message": f"企业 ID {enterprise_id} 不存在"})


def _validate_parent(
    db: Session,
    parent_id: int | None,
    enterprise_id: int,
    current_id: int | None = None,
) -> None:
    if parent_id is None:
        return
    if current_id is not None and int(parent_id) == int(current_id):
        raise HTTPException(status_code=400, detail={"message": "部门不能以自身作为上级"})
    parent = crud.get_department(db, parent_id)
    if parent is None:
        raise HTTPException(status_code=400, detail={"message": f"上级部门 ID {parent_id} 不存在"})
    if parent.enterprise_id != enterprise_id:
        raise HTTPException(status_code=400, detail={"message": "上级部门必须属于同一企业"})
    # Walk towards the root so an edit cannot make A -> B -> A. The UI
    # supports arbitrary depth, therefore cycle protection belongs here.
    visited = set()
    cursor = parent
    while cursor is not None and cursor.id not in visited:
        if current_id is not None and int(cursor.id) == int(current_id):
            raise HTTPException(status_code=400, detail={"message": "不能将部门移动到自己的下级部门"})
        visited.add(cursor.id)
        cursor = crud.get_department(db, cursor.parent_id) if cursor.parent_id else None


def _department_or_404(db: Session, department_id: int):
    department = crud.get_department(db, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail={"message": "部门不存在"})
    return department


def _validate_task_assignment(db: Session, department_id: int, task_id: int | None) -> None:
    if task_id is None:
        return
    if crud.get_department_task(db, department_id, task_id) is None:
        raise HTTPException(status_code=400, detail={"message": "所选任务不属于当前部门"})


@router.get("/", response_model=List[schemas.DepartmentResponse])
def list_departments(skip: int = 0, limit: int = 200, db: Session = Depends(get_db)):
    return crud.get_departments(db, skip, limit)


@router.get("/{department_id}/workspace", response_model=schemas.DepartmentWorkspaceResponse)
def read_department_workspace(department_id: int, db: Session = Depends(get_db)):
    department = _department_or_404(db, department_id)
    # Deliberately use equality filters inside both CRUD calls. A parent
    # workspace must never aggregate employees/tasks from descendants.
    return {
        "department": department,
        "employees": crud.get_department_employees(db, department_id),
        "tasks": crud.get_department_tasks(db, department_id),
    }


@router.post("/{department_id}/tasks", response_model=schemas.DepartmentTaskResponse)
def create_department_task(
    department_id: int,
    payload: schemas.DepartmentTaskCreate,
    db: Session = Depends(get_db),
):
    _department_or_404(db, department_id)
    return crud.create_department_task(db, department_id, payload)


@router.put("/{department_id}/tasks/{task_id}", response_model=schemas.DepartmentTaskResponse)
def update_department_task(
    department_id: int,
    task_id: int,
    payload: schemas.DepartmentTaskUpdate,
    db: Session = Depends(get_db),
):
    _department_or_404(db, department_id)
    record = crud.update_department_task(db, department_id, task_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail={"message": "任务不存在或不属于当前部门"})
    return record


@router.delete("/{department_id}/tasks/{task_id}")
def delete_department_task(department_id: int, task_id: int, db: Session = Depends(get_db)):
    _department_or_404(db, department_id)
    if not crud.delete_department_task(db, department_id, task_id):
        raise HTTPException(status_code=404, detail={"message": "任务不存在或不属于当前部门"})
    return {"detail": "deleted"}


@router.post("/{department_id}/employees", response_model=schemas.DepartmentEmployeeResponse)
def create_department_employee(
    department_id: int,
    payload: schemas.DepartmentEmployeeCreate,
    db: Session = Depends(get_db),
):
    _department_or_404(db, department_id)
    _validate_task_assignment(db, department_id, payload.task_id)
    return crud.create_department_employee(db, department_id, payload)


@router.put("/{department_id}/employees/{employee_id}", response_model=schemas.DepartmentEmployeeResponse)
def update_department_employee(
    department_id: int,
    employee_id: int,
    payload: schemas.DepartmentEmployeeUpdate,
    db: Session = Depends(get_db),
):
    _department_or_404(db, department_id)
    _validate_task_assignment(db, department_id, payload.task_id)
    record = crud.update_department_employee(db, department_id, employee_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail={"message": "员工不存在或不属于当前部门"})
    return record


@router.delete("/{department_id}/employees/{employee_id}")
def delete_department_employee(department_id: int, employee_id: int, db: Session = Depends(get_db)):
    _department_or_404(db, department_id)
    if not crud.delete_department_employee(db, department_id, employee_id):
        raise HTTPException(status_code=404, detail={"message": "员工不存在或不属于当前部门"})
    return {"detail": "deleted"}


@router.post("/", response_model=schemas.DepartmentResponse)
def create_department(payload: schemas.DepartmentCreate, db: Session = Depends(get_db)):
    _validate_enterprise(db, payload.enterprise_id)
    _validate_parent(db, payload.parent_id, payload.enterprise_id)
    return crud.create_department(db, payload)


@router.put("/{department_id}", response_model=schemas.DepartmentResponse)
def update_department(department_id: int, payload: schemas.DepartmentUpdate, db: Session = Depends(get_db)):
    _validate_enterprise(db, payload.enterprise_id)
    _validate_parent(db, payload.parent_id, payload.enterprise_id, department_id)
    record = crud.update_department(db, department_id, payload)
    if record is None:
        raise HTTPException(status_code=404, detail={"message": "部门不存在"})
    return record


@router.delete("/{department_id}")
def delete_department(department_id: int, db: Session = Depends(get_db)):
    if not crud.delete_department(db, department_id):
        raise HTTPException(status_code=404, detail={"message": "部门不存在"})
    return {"detail": "deleted"}
