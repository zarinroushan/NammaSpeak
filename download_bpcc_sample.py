
import csv
import os
import requests

API_URL = "https://datasets-server.huggingface.co/rows"

params = {
    "dataset": "ai4bharat/BPCC",
    "config": "bpcc-seed-latest",
    "split": "kan_Knda",
    "offset": 0,
    "length": 100,
}

rows_to_save = []
target_count = 1000

while len(rows_to_save) < target_count:
    params["offset"] = len(rows_to_save)

    token = os.environ.get("HF_TOKEN")

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(
        API_URL,
        params=params,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    batch = data.get("rows", [])
    if not batch:
        break

    for item in batch:
        row = item["row"]
        rows_to_save.append({
            "english": row.get("src", ""),
            "kannada": row.get("tgt", ""),
            "source_language": row.get("src_lang", ""),
            "target_language": row.get("tgt_lang", ""),
        })

    if len(batch) < 100:
        break

with open(
    "bpcc_kannada_sample.csv",
    "w",
    newline="",
    encoding="utf-8-sig",
) as file:
    writer = csv.DictWriter(
        file,
        fieldnames=[
            "english",
            "kannada",
            "source_language",
            "target_language",
        ],
    )
    writer.writeheader()
    writer.writerows(rows_to_save)

print(f"Saved {len(rows_to_save)} rows.")
