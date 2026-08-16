from __future__ import annotations

VERSION = "0.7.0"


def _tag_safe(value):
    return str(value).strip().replace(" ", "-").replace("/", "-") or "미분류"


def make_save_notes(core, original_save_notes):
    def save_notes(vault, graph, top=30):
        original_save_notes(vault, graph, top=top)
        words_dir = core.wordmap_dirs(vault)["words"]
        grammar_roles = (
            graph.get("문법", {})
            .get("표제어역할", {})
        )

        for token, meta in graph.get("nodes", {}).items():
            note = words_dir / f"{core.safe(token)}.md"
            if not note.exists():
                continue

            pos_ko = meta.get("pos_ko", "미분류")
            confidence = float(meta.get("lexicon_confidence", 0))
            forms = meta.get("forms_seen", {}) or {}
            form_text = ", ".join(
                f"{surface}({count})"
                for surface, count in list(forms.items())[:12]
            ) or "관찰형 없음"

            role_counts = grammar_roles.get(token, {}) or {}
            ranked_roles = sorted(
                ((role, int(count)) for role, count in role_counts.items()),
                key=lambda x: (-x[1], x[0]),
            )
            role_text = ", ".join(
                f"{role}({count})" for role, count in ranked_roles[:8]
            ) or "관찰된 문장 역할 없음"

            tags = [f"#품사/{_tag_safe(pos_ko)}"]
            tags.extend(
                f"#문장역할/{_tag_safe(role)}"
                for role, _count in ranked_roles[:8]
            )
            tag_text = " ".join(tags)

            text = note.read_text(encoding="utf-8")
            marker = f"빈도: **{int(meta.get('frequency', 0))}**"
            block = (
                f"{marker}\n\n"
                "## 사전 정보\n"
                f"- 표제어: **{token}**\n"
                f"- 품사: **{pos_ko}**\n"
                f"- 분석 신뢰도: {confidence:.2f}\n"
                f"- 관찰된 형태: {form_text}\n\n"
                "## 문법 태그\n"
                f"- 태그: {tag_text}\n"
                f"- 관찰된 문장 역할: {role_text}\n"
            )

            if marker in text:
                text = text.replace(marker, block, 1)
                note.write_text(text, encoding="utf-8")

    return save_notes


def apply(core):
    original = core.save_notes
    core.save_notes = make_save_notes(core, original)
    return core
