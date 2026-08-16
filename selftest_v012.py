#!/usr/bin/env python3

import benchmark
import event_graph


def main():
    result = benchmark.run()
    assert result["passed"] == result["total"], result
    frames = result["learned"]["predicate_frames"]
    assert "먹다" in frames, frames
    assert any("행위자" in frame and "대상" in frame for frame in frames["먹다"]), frames["먹다"]

    # The same predicate observed across different actors/places must share a
    # predicate-frame family instead of becoming unrelated word chains.
    graph = {}
    for sentence in benchmark.CORPUS[:3]:
        event = event_graph.extract_event(sentence)
        assert event, sentence
        event_graph.accumulate_event(graph, event)
    data = graph["상황지도"]
    assert data["사건수"] == 3, data
    assert len(data["서술어프레임"].get("먹다", {})) >= 1, data

    print("WordMap v0.12.0 situation/event graph self-test: OK")


if __name__ == "__main__":
    main()
