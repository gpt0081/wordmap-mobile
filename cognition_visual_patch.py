from __future__ import annotations

VERSION = "0.18.0"


def apply(visualizer):
    if getattr(visualizer, "_cognition_visual_patched", False):
        return visualizer
    original = visualizer.build_visual_trace

    def build_visual_trace(result):
        stages = original(result)
        additions = []

        priming = result.get("점화상태") or {}
        prime_rows = priming.get("사용전") or []
        if prime_rows:
            additions.append({
                "name": "점화 메모리",
                "kind": "점화",
                "activation": {
                    row.get("표제어"): float(row.get("점화도", 0))
                    for row in prime_rows
                    if row.get("표제어")
                },
                "path": [],
                "candidate_ids": [],
                "message": "이전 대화가 미리 활성화해 둔 개념입니다. 턴이 지날수록 감쇠합니다.",
            })

        streams = result.get("연상폭포") or []
        assoc_rows = result.get("연상활성화") or []
        if streams or assoc_rows:
            best_path = list((streams[0] or {}).get("경로") or []) if streams else []
            additions.append({
                "name": "연상 폭포",
                "kind": "연상폭포",
                "activation": {
                    row.get("표제어"): float(row.get("유효활성", row.get("연상도", 0)))
                    for row in assoc_rows
                    if row.get("표제어")
                },
                "path": best_path,
                "candidate_ids": [
                    row.get("끝점") for row in streams[:8] if row.get("끝점")
                ],
                "thought_streams": streams[:8],
                "message": "점화와 현재 입력에서 여러 연상 경로가 파동처럼 퍼지고, 문맥과 충돌하는 경로는 억제됩니다.",
            })

        if not additions:
            return stages

        insert_at = 1
        for i, stage in enumerate(stages):
            if stage.get("name") == "입력 개념":
                insert_at = i + 1
                break
        return stages[:insert_at] + additions + stages[insert_at:]

    visualizer.build_visual_trace = build_visual_trace
    visualizer._cognition_visual_patched = True
    visualizer.cognition_visual_version = VERSION
    return visualizer
