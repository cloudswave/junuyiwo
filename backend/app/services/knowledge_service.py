from datetime import date
from sqlalchemy.orm import Session

from ..models import KnowledgeNode, KnowledgeLink


def get_or_create_node(db: Session, node_name: str, category: str | None = None) -> KnowledgeNode:
    node = db.query(KnowledgeNode).filter(KnowledgeNode.node_name == node_name).first()
    if not node:
        node = KnowledgeNode(
            node_name=node_name,
            category=category,
            first_appearance_date=date.today(),
        )
        db.add(node)
        db.commit()
        db.refresh(node)
    return node


def create_node(db: Session, node_name: str, category: str | None = None) -> KnowledgeNode:
    existing = db.query(KnowledgeNode).filter(KnowledgeNode.node_name == node_name).first()
    if existing:
        return existing
    node = KnowledgeNode(
        node_name=node_name,
        category=category,
        first_appearance_date=date.today(),
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


def get_all_nodes(db: Session, category: str | None = None) -> list[KnowledgeNode]:
    q = db.query(KnowledgeNode).order_by(KnowledgeNode.total_articles.desc())
    if category:
        q = q.filter(KnowledgeNode.category == category)
    return q.all()


def get_node_by_id(db: Session, node_id: int) -> KnowledgeNode | None:
    return db.query(KnowledgeNode).filter(KnowledgeNode.id == node_id).first()


def update_node_category(db: Session, node_id: int, category: str) -> KnowledgeNode | None:
    node = db.query(KnowledgeNode).filter(KnowledgeNode.id == node_id).first()
    if node:
        node.category = category
        db.commit()
        db.refresh(node)
    return node


def mark_node_reviewed(db: Session, node_id: int) -> KnowledgeNode | None:
    node = db.query(KnowledgeNode).filter(KnowledgeNode.id == node_id).first()
    if node:
        node.last_review_date = date.today()
        node.total_articles += 1
        db.commit()
        db.refresh(node)
    return node


def delete_node(db: Session, node_id: int) -> bool:
    node = db.query(KnowledgeNode).filter(KnowledgeNode.id == node_id).first()
    if node:
        db.query(KnowledgeLink).filter(
            (KnowledgeLink.node_a_id == node_id) | (KnowledgeLink.node_b_id == node_id)
        ).delete()
        db.delete(node)
        db.commit()
        return True
    return False


def get_all_links(db: Session) -> list[KnowledgeLink]:
    return db.query(KnowledgeLink).all()


def create_link(
    db: Session,
    node_a_id: int,
    node_b_id: int,
    link_type: str,
    strength: int = 1,
) -> KnowledgeLink | None:
    a = db.query(KnowledgeNode).filter(KnowledgeNode.id == node_a_id).first()
    b = db.query(KnowledgeNode).filter(KnowledgeNode.id == node_b_id).first()
    if not a or not b:
        return None

    existing = db.query(KnowledgeLink).filter(
        ((KnowledgeLink.node_a_id == node_a_id) & (KnowledgeLink.node_b_id == node_b_id))
        | ((KnowledgeLink.node_a_id == node_b_id) & (KnowledgeLink.node_b_id == node_a_id))
    ).first()
    if existing:
        existing.strength += 1
        db.commit()
        db.refresh(existing)
        return existing

    link = KnowledgeLink(
        node_a_id=node_a_id,
        node_b_id=node_b_id,
        link_type=link_type,
        strength=strength,
        discovered_date=date.today(),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def delete_link(db: Session, link_id: int) -> bool:
    link = db.query(KnowledgeLink).filter(KnowledgeLink.id == link_id).first()
    if link:
        db.delete(link)
        db.commit()
        return True
    return False


def get_graph(db: Session) -> dict:
    nodes = get_all_nodes(db)
    links = get_all_links(db)
    return {"nodes": nodes, "links": links}


def get_node_neighbors(db: Session, node_id: int) -> dict:
    node = db.query(KnowledgeNode).filter(KnowledgeNode.id == node_id).first()
    if not node:
        return {"node": None, "neighbors": []}

    links = db.query(KnowledgeLink).filter(
        (KnowledgeLink.node_a_id == node_id) | (KnowledgeLink.node_b_id == node_id)
    ).all()

    neighbor_ids = set()
    for link in links:
        neighbor_id = link.node_b_id if link.node_a_id == node_id else link.node_a_id
        neighbor_ids.add(neighbor_id)

    neighbors = db.query(KnowledgeNode).filter(KnowledgeNode.id.in_(neighbor_ids)).all() if neighbor_ids else []

    return {
        "node": node,
        "neighbors": [{"node": n, "link_type": next(
            l.link_type for l in links
            if (l.node_a_id == node_id and l.node_b_id == n.id)
            or (l.node_b_id == node_id and l.node_a_id == n.id)
        )} for n in neighbors],
    }
