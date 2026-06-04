import requests
import time
import json
import os
import sys

API = "https://api.csqaq.com"
HDR = lambda token: {"ApiToken": token, "User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

TOKENS = [t.strip() for t in os.environ.get("CSQAQ_TOKENS", "").split(",") if t.strip()]


def bind_with_retry(token, max_retries=3):
    """bind_local_ip，429频率限制时等待30s重试"""
    for attempt in range(max_retries + 1):
        r = requests.post(f"{API}/api/v1/sys/bind_local_ip", headers=HDR(token)).json()
        code = r.get("code")
        if code == 200:
            return r
        if code == 429:
            if attempt < max_retries:
                print(f"  bind 429频率限制, 30s后重试 ({attempt+1}/{max_retries})...")
                time.sleep(30)
                continue
            else:
                print(f"  bind 429频率限制, 已达最大重试次数")
                return r
        return r
    return r


def collect_user_trade(user_id, token):
    """采集单个用户的交易记录"""
    print(f"采集用户交易: user_id={user_id}, token={token[:8]}...")

    # 1. bind
    print("[1/3] bind...")
    bind_r = bind_with_retry(token)
    print(f"  bind: code={bind_r.get('code')}")
    if bind_r.get("code") != 200:
        return {"user_id": user_id, "error": "bind_failed", "detail": bind_r.get("msg", "")}
    time.sleep(5)

    # 2. get_task_info - 获取用户监控任务信息
    print("[2/3] get_task_info...")
    info_r = requests.post(f"{API}/api/v1/task/get_task_info",
                           headers=HDR(token), json={"task_id": str(user_id)}).json()
    if info_r.get("code") != 200:
        return {"user_id": user_id, "error": "get_task_info_failed", "detail": info_r.get("msg", "")}

    task_info = info_r.get("data", {})
    time.sleep(1.1)

    # 3. get_task_business - 获取交易记录（分页）
    print("[3/3] get_task_business...")
    all_trades = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        trade_r = requests.post(f"{API}/api/v1/task/get_task_business",
                                headers=HDR(token),
                                json={"task_id": str(user_id), "page_index": page,
                                      "page_size": 50, "type": "ALL"}).json()
        if trade_r.get("code") != 200:
            if page == 1:
                return {"user_id": user_id, "error": "get_task_business_failed",
                        "detail": trade_r.get("msg", "")}
            break

        trade_data = trade_r.get("data", {})
        items = trade_data.get("data", [])
        all_trades.extend(items)

        total_count = trade_data.get("total", 0)
        total_pages = max(1, (total_count + 49) // 50)
        print(f"  page {page}/{total_pages}, got {len(items)} trades")
        page += 1
        if page <= total_pages:
            time.sleep(1.1)

    return {
        "user_id": user_id,
        "task_info": task_info,
        "trades": all_trades,
        "trade_count": len(all_trades),
        "error": None,
    }


def collect_user_inventory(user_id, token):
    """采集单个用户的库存快照"""
    print(f"采集用户库存: user_id={user_id}, token={token[:8]}...")

    # 1. bind
    print("[1/2] bind...")
    bind_r = bind_with_retry(token)
    print(f"  bind: code={bind_r.get('code')}")
    if bind_r.get("code") != 200:
        return {"user_id": user_id, "error": "bind_failed", "detail": bind_r.get("msg", "")}
    time.sleep(5)

    # 2. get_task_info - 包含库存信息
    print("[2/2] get_task_info...")
    info_r = requests.post(f"{API}/api/v1/task/get_task_info",
                           headers=HDR(token), json={"task_id": str(user_id)}).json()
    if info_r.get("code") != 200:
        return {"user_id": user_id, "error": "get_task_info_failed", "detail": info_r.get("msg", "")}

    task_info = info_r.get("data", {})

    return {
        "user_id": user_id,
        "task_info": task_info,
        "error": None,
    }


def main():
    user_id = ""
    action = "trade"
    token_index = 0

    for i, arg in enumerate(sys.argv):
        if arg == "--user-id" and i + 1 < len(sys.argv):
            user_id = sys.argv[i + 1]
        if arg == "--action" and i + 1 < len(sys.argv):
            action = sys.argv[i + 1]
        if arg == "--token-index" and i + 1 < len(sys.argv):
            token_index = int(sys.argv[i + 1])

    if not user_id:
        print("错误: 缺少 --user-id 参数")
        sys.exit(1)

    if not TOKENS:
        print("错误: 未设置CSQAQ_TOKENS环境变量")
        sys.exit(1)

    token = TOKENS[token_index % len(TOKENS)]
    print(f"用户采集: user_id={user_id}, action={action}, token_index={token_index}")

    if action == "trade":
        result = collect_user_trade(user_id, token)
    elif action == "inventory":
        result = collect_user_inventory(user_id, token)
    else:
        print(f"错误: 未知 action={action}, 支持 trade/inventory")
        sys.exit(1)

    with open("result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"保存: result.json")


if __name__ == "__main__":
    main()
