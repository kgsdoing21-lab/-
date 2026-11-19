"""파주시 교회를 카카오 로컬 API로 수집해 읍·면·동(행정동)별로 집계한다.

키워드 검색은 한 번에 최대 45건만 주므로, 파주 영역을 사각형으로 나눠
결과가 45건 미만이 될 때까지 재귀 분할한다.
카카오 REST API 키는 환경 변수 KAKAO_REST_API_KEY 에서 읽는다.
"""
import csv, json, os, sys, time, urllib.parse, urllib.request
from collections import Counter

API = "https://dapi.kakao.com"
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
BBOX = (126.60, 37.66, 127.03, 38.00)  # 파주시 전체를 덮는 범위
HDR = {"Authorization": "KakaoAK " + os.environ.get("KAKAO_REST_API_KEY", "proxy-injected")}


def get(path, **params):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=20) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            if attempt == 4:
                raise
            time.sleep(1 + attempt)


def search_rect(x1, y1, x2, y2, found, depth=0):
    rect = f"{x1},{y1},{x2},{y2}"
    first = get("/v2/local/search/keyword.json", query="교회", rect=rect, page=1, size=15)
    total = first["meta"]["total_count"]
    if total >= 45 and depth < 12:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        for r in ((x1, y1, mx, my), (mx, y1, x2, my), (x1, my, mx, y2), (mx, my, x2, y2)):
            search_rect(*r, found, depth + 1)
        return
    docs, page, meta = first["documents"], 1, first["meta"]
    while not meta["is_end"] and page < 3:
        page += 1
        res = get("/v2/local/search/keyword.json", query="교회", rect=rect, page=page, size=15)
        docs += res["documents"]
        meta = res["meta"]
    for d in docs:
        found[d["id"]] = d


def main():
    found = {}
    search_rect(*BBOX, found)
    rows = []
    for d in found.values():
        addr = d.get("address_name", "")
        if "파주시" not in addr:
            continue
        cat = d.get("category_name", "")
        if "교회" not in cat.split(">")[-1] and "기독교" not in cat:
            continue  # 교회 이름이 들어간 카페·주차장 등 제외
        reg = get("/v2/local/geo/coord2regioncode.json", x=d["x"], y=d["y"])
        h = next((r for r in reg["documents"] if r["region_type"] == "H"), {})
        rows.append({
            "읍면동": h.get("region_3depth_name", "?"),
            "교회명": d["place_name"],
            "카테고리": cat,
            "지번주소": addr,
            "도로명주소": d.get("road_address_name", ""),
            "전화": d.get("phone", ""),
            "x": d["x"], "y": d["y"],
        })
    rows.sort(key=lambda r: (r["읍면동"], r["교회명"]))
    with open(f"{OUT}/paju_churches.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    cnt = Counter(r["읍면동"] for r in rows)
    with open(f"{OUT}/paju_church_counts.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["읍면동", "교회수"])
        for k, v in sorted(cnt.items()):
            w.writerow([k, v])
        w.writerow(["합계", sum(cnt.values())])
    print(json.dumps({"raw": len(found), "churches": len(rows), "counts": cnt}, ensure_ascii=False))


if __name__ == "__main__":
    main()
