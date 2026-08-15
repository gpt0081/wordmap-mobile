from __future__ import annotations

VERSION = "0.5.0"


def make_save_notes(core, original_save_notes):
    def save_notes(vault, graph, top=30):
        original_save_notes(vault, graph, top=top)
        words_dir = core.wordmap_dirs(vault)["words"]

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

            text = note.read_text(encoding="utf-8")
            marker = f"빈도: **{int(meta.get('frequency', 0))}**"
            block = (
                f"{marker}\n\n"
                "## 사전 정보\n"
                f"- 표제어: **{token}**\n"
                f"- 품사: **{pos_ko}**\n"
                f"- 분석 신뢰도: {confidence:.2f}\n"
                f"- 관찰된 형태: {form_text}\n"
            )

            if marker in text:
                text = text.replace(marker, block, 1)
                note.write_text(text, encoding="utf-8")

    return save_notes


def apply(core):
    original = core.save_notes
    core.save_notes = make_save_notes(core, original)
    return core
