import os, logging, datetime, random, requests, notify

_TZ8 = datetime.timezone(datetime.timedelta(hours=8))
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.Formatter.converter = lambda *_: datetime.datetime.now(_TZ8).timetuple()
logger = logging.getLogger(__name__)

BASE = "https://glados.cloud/api/user"
_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Safari/605.1.15",
]
HEADERS = {
    'referer': 'https://glados.cloud/console/checkin',
    'origin': 'https://glados.cloud',
    'content-type': 'application/json;charset=UTF-8',
}
PLANS = {"plan100": 100, "plan200": 200, "plan500": 500}


_mask = lambda c: f"{c[:4]}****{c[-4:]}" if len(c) > 12 else "****"


def api(path, cookie, data=None):
    try:
        r = requests.request(
            "POST" if data else "GET", f"{BASE}/{path}",
            headers={**HEADERS, 'cookie': cookie, 'user-agent': random.choice(_UAS)},
            json=data, timeout=15, verify=True,
        )
        return r.json() if r.ok else None
    except (requests.RequestException, ValueError):
        logger.error("请求 %s 失败 [%s]", path, _mask(cookie))
        return None


def toint(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def process(cookie, plan):
    c = api("checkin", cookie, {"token": "glados.cloud"})
    if not c:
        return "签到请求失败", "0", "获取失败", "获取失败", "兑换跳过"
    msg = c.get('message', '')
    pts = str(c.get('points', 0)) if "Got" in msg else "0"
    status = f"签到成功，获得 {pts} 积分" if "Got" in msg else "重复签到" if "Repeats" in msg else f"签到失败: {msg}"
    d = toint((api("status", cookie) or {}).get('data', {}).get('leftDays'))
    t = toint((api("points", cookie) or {}).get('points'))
    days = f"{d} 天" if d is not None else "获取失败"
    total = f"{t} 积分" if t is not None else "获取失败"
    if t is None:
        exch = "积分获取失败，跳过兑换"
    elif t >= PLANS.get(plan, 500):
        ex = api("exchange", cookie, {"planType": plan})
        exch = f"兑换成功：{plan}" if ex and ex.get('code') == 0 else f"兑换失败: {plan}"
    else:
        exch = f"积分不足，未兑换: {plan}"
    return status, pts, days, total, exch


def _notify(title, content=""):
    logger.info("%s\n%s", title, content)
    try:
        notify.send(title, content)
    except Exception:
        logger.error("通知发送失败")


def main():
    cookies = [c.strip() for c in os.environ.get("GLADOS_COOKIES", "").split('&') if c.strip()]
    plan = os.environ.get("GLADOS_EXCHANGE_PLAN", "plan500")
    if plan not in PLANS:
        plan = "plan500"
    if not cookies:
        return _notify("未找到 cookies!")
    results = [process(c, plan) for c in cookies]
    cnt = lambda kw, idx: sum(kw in r[idx] for r in results)
    title = f"GLaDOS 签到, 成功{cnt('成功', 0)}, 失败{cnt('失败', 0) + cnt('失败', 4)}, 重复{cnt('重复', 0)}"
    content = "\n".join(f"账号{i}: P:{p} 剩余天数:{d} 总积分:{t} | {s}; {e}"
                        for i, (s, p, d, t, e) in enumerate(results, 1))
    _notify(title, content)


if __name__ == '__main__':
    main()
