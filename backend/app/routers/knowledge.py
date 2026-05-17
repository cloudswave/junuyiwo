from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    KnowledgeNodeCreate,
    KnowledgeNodeResponse,
    KnowledgeLinkResponse,
    KnowledgeGraphResponse,
)
from ..services.knowledge_service import (
    create_node,
    get_all_nodes,
    get_node_by_id,
    update_node_category,
    mark_node_reviewed,
    delete_node,
    get_all_links,
    create_link,
    delete_link,
    get_graph,
    get_node_neighbors,
)
from .students import get_current_student_id

router = APIRouter(prefix="/api/knowledge", tags=["知识图谱"])


@router.post("/nodes", response_model=KnowledgeNodeResponse)
def add_node(body: KnowledgeNodeCreate, db: Session = Depends(get_db)):
    return create_node(db, body.node_name, body.category)


@router.get("/nodes", response_model=list[KnowledgeNodeResponse])
def list_nodes(
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    student_id: int = Depends(get_current_student_id),
):
    nodes = get_all_nodes(db, category)
    return [n for n in nodes if n.student_id == student_id]


@router.get("/nodes/{node_id}", response_model=KnowledgeNodeResponse)
def get_node(node_id: int, db: Session = Depends(get_db)):
    node = get_node_by_id(db, node_id)
    if not node:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="知识点不存在")
    return node


@router.patch("/nodes/{node_id}/category")
def set_node_category(node_id: int, category: str, db: Session = Depends(get_db)):
    node = update_node_category(db, node_id, category)
    if not node:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="知识点不存在")
    return node


@router.post("/nodes/{node_id}/review")
def review_node(node_id: int, db: Session = Depends(get_db)):
    node = mark_node_reviewed(db, node_id)
    if not node:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="知识点不存在")
    return node


@router.delete("/nodes/{node_id}")
def remove_node(node_id: int, db: Session = Depends(get_db)):
    ok = delete_node(db, node_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="知识点不存在")
    return {"ok": True}


@router.get("/graph", response_model=KnowledgeGraphResponse)
def knowledge_graph(db: Session = Depends(get_db)):
    return get_graph(db)


@router.post("/links")
def add_link(
    node_a_id: int = Query(...),
    node_b_id: int = Query(...),
    link_type: str = Query(..., description="similar/cause_effect/part_of/opposite/story_connection"),
    strength: int = Query(1, ge=1, le=10),
    db: Session = Depends(get_db),
):
    link = create_link(db, node_a_id, node_b_id, link_type, strength)
    if not link:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="节点不存在")
    return link


@router.delete("/links/{link_id}")
def remove_link(link_id: int, db: Session = Depends(get_db)):
    ok = delete_link(db, link_id)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="关联不存在")
    return {"ok": True}


@router.get("/nodes/{node_id}/neighbors")
def node_neighbors(node_id: int, db: Session = Depends(get_db)):
    return get_node_neighbors(db, node_id)
