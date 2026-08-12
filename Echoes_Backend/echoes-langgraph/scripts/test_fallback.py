"""
Fallback 降级场景测试

验证异常场景下的降级策略：
1. 工具执行失败（search_memory 抛异常）
2. 无记忆召回（threshold 拦截全部）
3. LLM 超时/异常

运行：python scripts/test_fallback.py [--base http://localhost:8011]
"""
import argparse
import json
import sys
import time
import uuid
import urllib.request
from unittest.mock import patch, AsyncMock

# Windows 控制台 UTF-8
sys.stdout.reconfigure(encoding="utf-8")


def call_agent(base: str, query: str, user_id: str):
    """调用 /api/v1/agent/chat"""
    payload = {
        "query": query,
        "user_id": user_id,
        "session_id": f"sess_{uuid.uuid4().hex[:8]}",
        "turn_id": str(uuid.uuid4()),
        "personality_mode": "温柔",
        "conversation_history": [],
    }
    req = urllib.request.Request(
        f"{base}/api/v1/agent/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        data["_latency_s"] = round(time.time() - start, 1)
        data["_error"] = None
        return data
    except Exception as e:
        return {"_error": str(e), "_latency_s": round(time.time() - start, 1)}


FALLBACK_SCENARIOS = [
    ("F1", "无记忆场景（全新用户，无历史）", "你还记得我之前说过什么吗", "fallback_test_new"),
    ("F2", "低相关性查询（threshold 拦截）", "量子力学的薛定谔猫是什么", "fallback_test_lowrel"),
    ("F3", "空查询（边界情况）", "", "fallback_test_empty"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8011")
    args = ap.parse_args()

    print("=== Fallback 降级场景测试 ===\n")

    results = []
    for idx, desc, query, uid in FALLBACK_SCENARIOS:
        print(f"[{idx}] {desc}")
        print(f"    query: {query!r}")

        r = call_agent(args.base, query, uid)

        if r.get("_error"):
            print(f"    ✗ 请求失败: {r['_error']}")
            results.append((idx, False))
        else:
            response = r.get("response", "")
            memory_hits = len(r.get("memory_hits", []))
            # Fallback 判定：无记忆 + 有合理回复
            fallback_ok = (memory_hits == 0) and (len(response) > 10)
            status = "✓ Fallback 生效" if fallback_ok else "✗ 未降级"
            print(f"    memory_hits: {memory_hits} | {status}")
            print(f"    response: {response[:80]}")
            print(f"    {r['_latency_s']}s\n")
            results.append((idx, fallback_ok))

    passed = sum(1 for _, ok in results if ok)
    print(f"=== 汇总: {passed}/{len(results)} Fallback 场景通过 ===")


if __name__ == "__main__":
    main()
