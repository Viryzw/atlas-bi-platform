"""RAG index for metrics, data dictionary, schema and analysis rules.

The relational ``metrics`` and ``knowledge_documents`` tables are canonical.
Chroma is a derived index; live business schema is introspected during rebuild.
"""

from functools import lru_cache
import os
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional, Tuple

import chromadb
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy.orm import Session

from database import SessionLocal
from models import DataSource, KnowledgeDocument, Metric
from query_engine import get_schema_catalog


BASE_DIR = Path(__file__).resolve().parent
LOCAL_MODEL_PATH = Path(
    os.getenv("EMBEDDING_MODEL_PATH", str(BASE_DIR / "models" / "all-MiniLM-L6-v2"))
)
PERSIST_DIR = Path(os.getenv("KNOWLEDGE_BASE_DIR", str(BASE_DIR / "chroma_db")))
COLLECTION_NAME = "bi_knowledge"

_index_lock = RLock()


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    if not LOCAL_MODEL_PATH.exists():
        raise FileNotFoundError(f"本地嵌入模型不存在：{LOCAL_MODEL_PATH}")
    return HuggingFaceEmbeddings(model_name=str(LOCAL_MODEL_PATH))


def metric_to_document(metric: Metric) -> Tuple[str, Dict[str, Any]]:
    text = "\n".join(
        [
            "知识类型: 业务指标",
            f"指标名称: {metric.name}",
            f"主题领域: {metric.topic or '未分类'}",
            f"指标别名: {getattr(metric, 'aliases', None) or '无'}",
            f"口径说明: {metric.description or '无'}",
            f"权威计算表达式: {metric.sql_expr or '无'}",
            f"基础表: {getattr(metric, 'base_table', None) or '自动推断'}",
            f"时间字段: {getattr(metric, 'time_field', None) or '自动推断'}",
            f"分析维度: {getattr(metric, 'dimension_field', None) or '自动推断'}",
            f"单位: {getattr(metric, 'unit', None) or '无'}",
            f"数据源 ID: {metric.data_source_id}",
            "执行规则: 命中该指标时必须保持权威计算表达式，不得把 CASE 条件改写到 WHERE。",
        ]
    )
    metadata = {
        "source_type": "metric",
        "metric_id": metric.id,
        "name": metric.name,
        "topic": metric.topic or "未分类",
        "data_source_id": metric.data_source_id,
    }
    return text, metadata


def knowledge_document_to_document(document: KnowledgeDocument) -> Tuple[str, Dict[str, Any]]:
    category_labels = {
        "table": "表说明",
        "field": "字段含义",
        "rule": "分析规则",
        "question": "常见分析问题",
    }
    text = "\n".join(
        [
            f"知识类型: {category_labels.get(document.category, document.category)}",
            f"标题: {document.title}",
            f"内容: {document.content}",
            f"数据源 ID: {document.data_source_id or '通用'}",
        ]
    )
    metadata = {
        "source_type": "dictionary",
        "document_id": document.id,
        "category": document.category,
        "name": document.title,
        "data_source_id": document.data_source_id or 0,
    }
    return text, metadata


def schema_to_document(table: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    column_lines = []
    for column in table["columns"]:
        details = [column["type"], "可空" if column["nullable"] else "非空"]
        if column.get("comment"):
            details.append(f"含义: {column['comment']}")
        column_lines.append(f"- {column['name']}: {', '.join(details)}")
    text = "\n".join(
        [
            "知识类型: 数据库表结构",
            f"数据源: {table['data_source_name']}（ID {table['data_source_id']}）",
            f"表名: {table['table_name']}",
            "字段列表:",
            *column_lines,
            "执行规则: SQL 只能使用这里列出的真实表和字段。",
        ]
    )
    metadata = {
        "source_type": "schema",
        "name": table["table_name"],
        "table_name": table["table_name"],
        "data_source_id": table["data_source_id"],
    }
    return text, metadata


def _load_metrics() -> List[Metric]:
    db: Session = SessionLocal()
    try:
        return (
            db.query(Metric)
            .join(DataSource, Metric.data_source_id == DataSource.id)
            .filter(DataSource.is_active.is_(True))
            .order_by(Metric.id.asc())
            .all()
        )
    finally:
        db.close()


def _load_knowledge_documents() -> List[KnowledgeDocument]:
    db: Session = SessionLocal()
    try:
        return (
            db.query(KnowledgeDocument)
            .outerjoin(DataSource, KnowledgeDocument.data_source_id == DataSource.id)
            .filter(
                (KnowledgeDocument.data_source_id.is_(None))
                | (DataSource.is_active.is_(True))
            )
            .order_by(KnowledgeDocument.id.asc())
            .all()
        )
    finally:
        db.close()


def _load_schema_documents() -> List[Dict[str, Any]]:
    db: Session = SessionLocal()
    try:
        source_ids = [
            row[0]
            for row in db.query(DataSource.id)
            .filter(DataSource.is_active.is_(True))
            .order_by(DataSource.id.asc())
            .all()
        ]
    finally:
        db.close()
    documents: List[Dict[str, Any]] = []
    for source_id in source_ids:
        documents.extend(get_schema_catalog(source_id))
    return documents


def get_exact_metric_bindings(
    question: str,
    data_source_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return metrics explicitly named in the question for hard enforcement."""

    clean_question = (question or "").casefold()
    matches = []
    for metric in _load_metrics():
        if data_source_id is not None and int(metric.data_source_id) != int(data_source_id):
            continue
        name = (metric.name or "").strip()
        aliases = [item.strip() for item in (getattr(metric, "aliases", None) or "").split(",") if item.strip()]
        matched_name = next(
            (candidate for candidate in [name, *aliases] if candidate.casefold() in clean_question),
            None,
        )
        if matched_name:
            matches.append({
                "metric_id": metric.id,
                "name": name,
                "sql_expr": metric.sql_expr or "",
                "description": metric.description or "",
                "data_source_id": metric.data_source_id,
                "matched_name": matched_name,
            })
    return sorted(matches, key=lambda item: len(item["name"]), reverse=True)


def _collection_state() -> Tuple[bool, int]:
    if not PERSIST_DIR.exists():
        return False, 0
    client = chromadb.PersistentClient(path=str(PERSIST_DIR))
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        return False, 0
    return True, int(collection.count())


def _source_counts() -> Dict[str, int]:
    metric_count = len(_load_metrics())
    document_count = len(_load_knowledge_documents())
    schema_count = len(_load_schema_documents())
    return {
        "metric_count": metric_count,
        "document_count": document_count,
        "schema_count": schema_count,
        "source_count": metric_count + document_count + schema_count,
    }


def get_knowledge_base_status() -> Dict[str, Any]:
    counts = _source_counts()
    collection_exists, indexed_count = _collection_state()
    synchronized = collection_exists and indexed_count == counts["source_count"]
    return {
        "status": "ready" if synchronized else "stale",
        **counts,
        "indexed_count": indexed_count,
        "synchronized": synchronized,
    }


def build_knowledge_base() -> Dict[str, Any]:
    metrics = _load_metrics()
    knowledge_documents = _load_knowledge_documents()
    schema_documents = _load_schema_documents()

    documents: List[Tuple[str, str, Dict[str, Any]]] = []
    documents.extend(
        (f"metric:{metric.id}", *metric_to_document(metric))
        for metric in metrics
    )
    documents.extend(
        (f"dictionary:{document.id}", *knowledge_document_to_document(document))
        for document in knowledge_documents
    )
    documents.extend(
        (
            f"schema:{table['data_source_id']}:{table['table_name']}",
            *schema_to_document(table),
        )
        for table in schema_documents
    )

    with _index_lock:
        PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(PERSIST_DIR))
        collection_names = {
            collection.name if hasattr(collection, "name") else str(collection)
            for collection in client.list_collections()
        }
        if COLLECTION_NAME in collection_names:
            client.delete_collection(COLLECTION_NAME)

        if documents:
            ids = [item[0] for item in documents]
            texts = [item[1] for item in documents]
            metadatas = [item[2] for item in documents]
            Chroma.from_texts(
                texts,
                get_embeddings(),
                metadatas=metadatas,
                ids=ids,
                persist_directory=str(PERSIST_DIR),
                collection_name=COLLECTION_NAME,
            )
        else:
            client.get_or_create_collection(COLLECTION_NAME)

    indexed_count = _collection_state()[1]
    if indexed_count != len(documents):
        raise RuntimeError(
            f"知识库索引数量不一致：来源 {len(documents)} 条，索引 {indexed_count} 条"
        )

    return {
        "status": "ready",
        "metric_count": len(metrics),
        "document_count": len(knowledge_documents),
        "schema_count": len(schema_documents),
        "source_count": len(documents),
        "indexed_count": indexed_count,
        "synchronized": True,
    }


def retrieve_knowledge(
    query: str,
    k: int = 6,
    data_source_id: Optional[int] = None,
) -> Iterable[Any]:
    clean_query = (query or "").strip()
    if not clean_query or not PERSIST_DIR.exists() or _collection_state()[1] == 0:
        return []

    with _index_lock:
        vector_store = Chroma(
            persist_directory=str(PERSIST_DIR),
            embedding_function=get_embeddings(),
            collection_name=COLLECTION_NAME,
        )
        search_filter = None
        if data_source_id is not None:
            search_filter = {
                "data_source_id": {"$in": [0, int(data_source_id)]}
            }
        return vector_store.similarity_search(
            clean_query,
            k=max(1, int(k)),
            filter=search_filter,
        )
