from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db
from knowledge_base import build_knowledge_base, get_knowledge_base_status
from security import get_current_user


router = APIRouter(prefix="/api/admin/knowledge", tags=["knowledge"], dependencies=[Depends(get_current_user)])


@router.get("/status")
def knowledge_status():
    """Report whether Chroma contains every current RAG source."""

    try:
        return get_knowledge_base_status()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": f"读取知识库状态失败：{exc}"},
        ) from exc


@router.post("/rebuild")
def rebuild_knowledge():
    """Rebuild metrics, dictionary documents and live schema in one index."""

    try:
        result = build_knowledge_base()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": f"知识库重建失败：{exc}"},
        ) from exc
    return {"detail": "知识库重建完成", **result}


def _validate_data_source(db: Session, data_source_id: int | None) -> None:
    if data_source_id is not None and crud.get_data_source(db, data_source_id) is None:
        raise HTTPException(
            status_code=400,
            detail={"message": f"数据源 ID {data_source_id} 不存在"},
        )


def _sync_after_write() -> None:
    try:
        build_knowledge_base()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": f"知识条目已写入数据库，但 RAG 索引同步失败：{exc}"},
        ) from exc


@router.get("/documents/", response_model=List[schemas.KnowledgeDocumentResponse])
def list_documents(skip: int = 0, limit: int = 200, db: Session = Depends(get_db)):
    return crud.get_knowledge_documents(db, skip=skip, limit=limit)


@router.post("/documents/", response_model=schemas.KnowledgeDocumentResponse)
def create_document(
    document: schemas.KnowledgeDocumentCreate,
    db: Session = Depends(get_db),
):
    _validate_data_source(db, document.data_source_id)
    record = crud.create_knowledge_document(db, document)
    _sync_after_write()
    return record


@router.put("/documents/{document_id}", response_model=schemas.KnowledgeDocumentResponse)
def update_document(
    document_id: int,
    document: schemas.KnowledgeDocumentUpdate,
    db: Session = Depends(get_db),
):
    _validate_data_source(db, document.data_source_id)
    record = crud.update_knowledge_document(db, document_id, document)
    if record is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    _sync_after_write()
    return record


@router.delete("/documents/{document_id}", response_model=dict)
def delete_document(document_id: int, db: Session = Depends(get_db)):
    if not crud.delete_knowledge_document(db, document_id):
        raise HTTPException(status_code=404, detail="Knowledge document not found")
    _sync_after_write()
    return {"detail": "deleted"}
