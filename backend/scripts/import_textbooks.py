"""从 seed_data/ 导入所有预置教材数据到 knowledge_entries 表。

用法： cd backend && python scripts/import_textbooks.py
幂等：重复运行不会产生重复条目（按 title+lesson+grade_level+textbook_version 去重）
"""
import json
import sys
from pathlib import Path

# 确保能找到 app 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal, init_db
from app.models import KnowledgeEntry


SEED_DIR = Path(__file__).resolve().parent.parent.parent / "seed_data" / "textbooks"


def import_textbooks():
    init_db()
    db = SessionLocal()
    imported = 0
    skipped = 0

    try:
        for json_file in SEED_DIR.rglob("*.json"):
            rel_path = json_file.relative_to(SEED_DIR)
            print(f"\n--- {rel_path} ---")

            data = json.loads(json_file.read_text(encoding="utf-8"))
            version = data["textbook_version"]
            grade = data["grade_level"]
            subject = data["subject"]

            for lesson in data.get("lessons", []):
                lesson_name = lesson.get("lesson", "")
                content = lesson.get("content", "")
                characters = lesson.get("characters", [])
                knowledge_points = lesson.get("knowledge_points", [])

                # 0. 课文原文（如果有内容）
                if content:
                    existing_content = db.query(KnowledgeEntry).filter(
                        KnowledgeEntry.title == f"{lesson_name} - 课文原文",
                        KnowledgeEntry.lesson == lesson_name,
                    ).first()
                    if not existing_content:
                        entry = KnowledgeEntry(
                            student_id=0,
                            category="school",
                            subject=subject,
                            grade_level=grade,
                            textbook_version=version,
                            lesson=lesson_name,
                            title=f"{lesson_name} - 课文原文",
                            content=content,
                            keywords_json=characters if characters else [],
                            source="textbook_preload",
                            auto_approved=True,
                        )
                        db.add(entry)
                        imported += 1
                    else:
                        skipped += 1

                # 每个知识点作为一个独立条目
                for idx, kp in enumerate(knowledge_points):
                    title = f"{lesson_name} - 知识点{idx + 1}" if lesson_name else kp[:40]

                    # 去重检查
                    existing = db.query(KnowledgeEntry).filter(
                        KnowledgeEntry.title == title,
                        KnowledgeEntry.lesson == lesson_name,
                        KnowledgeEntry.grade_level == grade,
                        KnowledgeEntry.textbook_version == version,
                    ).first()

                    if existing:
                        skipped += 1
                        continue

                    entry = KnowledgeEntry(
                        student_id=0,  # 系统共享
                        category="school",
                        subject=subject,
                        grade_level=grade,
                        textbook_version=version,
                        lesson=lesson_name,
                        title=title,
                        content=kp,
                        keywords_json=characters if characters else [],
                        source="textbook_preload",
                        auto_approved=True,
                        used_count=0,
                    )
                    db.add(entry)
                    imported += 1

                db.commit()

        print(f"\n✓ 导入完成: {imported} 条新增, {skipped} 条已存在(跳过)")

    finally:
        db.close()


if __name__ == "__main__":
    import_textbooks()
