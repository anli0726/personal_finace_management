"""Summarize and cluster transaction descriptions from statement CSVs.

Produces a JSON file for the lightweight dashboard in spending_classifier/dashboard/.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
from difflib import SequenceMatcher
from typing import Dict, Iterable, List


DESCRIPTION_FIELDS = (
    "Description",
    "Transaction Description",
    "description",
    "Merchant",
    "merchant",
)

CATEGORY_FIELDS = (
    "Category",
    "category",
)

AMOUNT_FIELDS = (
    "Amount",
    "amount",
    "Debit",
    "debit",
    "Credit",
    "credit",
    "Debit/Credit",
    "Value",
)

DATE_FIELDS = (
    "Transaction Date",
    "Date",
    "date",
    "Post Date",
)


def normalize_text(text: str) -> str:
    lowered = (text or "").lower()
    lowered = re.sub(r"\bwww\.", "", lowered)
    lowered = re.sub(r"\b([a-z0-9-]+)\.(com|net|org|co|io|us|edu)\b", r"\1", lowered)
    lowered = re.sub(r"\b[0-9a-z]*\d+[0-9a-z]*\b", " ", lowered)
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def tokenize(text: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return " ".join(tokens)


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    prefix_len = 0
    for ch_a, ch_b in zip(a, b):
        if ch_a != ch_b:
            break
        prefix_len += 1
    return prefix_len / max(len(a), len(b))


def parse_amount(raw: str) -> float | None:
    if raw is None:
        return None
    cleaned = str(raw).strip().replace("$", "").replace(",", "").replace("\u2009", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_year(raw: str) -> int | None:
    if not raw:
        return None
    value = str(raw).strip()
    match = re.match(r"^(\d{4})[-/]\d{1,2}[-/]\d{1,2}$", value)
    if match:
        return int(match.group(1))
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", value)
    if match:
        return int(match.group(3))
    return None


def read_transactions(paths: Iterable[pathlib.Path]) -> List[Dict[str, object]]:
    transactions: List[Dict[str, object]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                value = ""
                for field in DESCRIPTION_FIELDS:
                    if field in row and row[field]:
                        value = row[field]
                        break
                if not value:
                    continue

                amount = None
                for field in AMOUNT_FIELDS:
                    if field not in row or not row[field]:
                        continue
                    parsed = parse_amount(row[field])
                    if parsed is None:
                        continue
                    if field.lower() == "debit":
                        amount = -abs(parsed)
                    elif field.lower() == "credit":
                        amount = abs(parsed)
                    else:
                        amount = parsed
                    break
                if amount is None:
                    continue

                category_value = ""
                for field in CATEGORY_FIELDS:
                    if field in row and row[field]:
                        category_value = str(row[field]).strip()
                        break

                date_value = ""
                for field in DATE_FIELDS:
                    if field in row and row[field]:
                        date_value = str(row[field]).strip()
                        break
                year_value = parse_year(date_value)

                transactions.append(
                    {
                        "description": value.strip(),
                        "amount": amount,
                        "date": date_value,
                        "year": year_value,
                        "category": category_value,
                        "source_file": path.name,
                    }
                )
    return transactions


def aggregate_descriptions(transactions: Iterable[Dict[str, object]]) -> Dict[tuple[str, str], Dict[str, float]]:
    agg: Dict[tuple[str, str], Dict[str, float]] = {}
    for item in transactions:
        desc = str(item["description"])
        amount = float(item["amount"])
        category = str(item.get("category") or "").strip()
        key = (desc, category)
        if key not in agg:
            agg[key] = {"count": 0.0, "spending": 0.0, "spending_count": 0.0}
        agg[key]["count"] += 1.0
        if amount < 0:
            agg[key]["spending"] += abs(amount)
            agg[key]["spending_count"] += 1.0
    return agg


def cluster_descriptions(
    aggregates: Dict[tuple[str, str], Dict[str, float]],
    transactions_by_desc: Dict[tuple[str, str], List[Dict[str, object]]],
    threshold: float,
) -> List[Dict[str, object]]:
    items: List[Tuple[tuple[str, str], Dict[str, float]]] = sorted(
        aggregates.items(),
        key=lambda kv: (-kv[1]["count"], kv[0][0], kv[0][1]),
    )
    assigned: Dict[str, str] = {}
    clusters: List[Dict[str, object]] = []

    for (desc, category), stats in items:
        key = (desc, category)
        if key in assigned:
            continue

        root = desc
        root_category = category
        root_norm = normalize_text(desc)
        root_tokens = tokenize(desc)
        cluster_items = [
            {
                "description": desc,
                "category": category,
                "count": int(stats["count"]),
                "total_spending": round(stats["spending"], 2),
                "spending_count": int(stats["spending_count"]),
            }
        ]
        assigned[key] = root

        for (other_desc, other_category), other_stats in items:
            other_key = (other_desc, other_category)
            if other_key in assigned:
                continue
            if root_category and other_category and root_category != other_category:
                continue
            other_norm = normalize_text(other_desc)
            if not other_norm:
                continue
            if similarity(root_norm, other_norm) >= threshold:
                cluster_items.append(
                    {
                        "description": other_desc,
                        "category": other_category,
                        "count": int(other_stats["count"]),
                        "total_spending": round(other_stats["spending"], 2),
                        "spending_count": int(other_stats["spending_count"]),
                    }
                )
                assigned[other_key] = root

        total_count = sum(item["count"] for item in cluster_items)
        total_spending = round(sum(item["total_spending"] for item in cluster_items), 2)
        spending_count = sum(item["spending_count"] for item in cluster_items)
        cluster_transactions: List[Dict[str, object]] = []
        for item in cluster_items:
            cluster_transactions.extend(transactions_by_desc.get((item["description"], item["category"]), []))
        cluster_transactions.sort(key=lambda t: (str(t.get("date", "")), str(t.get("description", ""))))

        root_label = f"{root} • {root_category}" if root_category else root
        clusters.append(
            {
                "root_description": root,
                "root_category": root_category,
                "root_label": root_label,
                "root_tokens": root_tokens,
                "total_count": total_count,
                "total_spending": total_spending,
                "spending_count": spending_count,
                "items": cluster_items,
                "transactions": cluster_transactions,
            }
        )

    return clusters


def build_summary(paths: Iterable[pathlib.Path], threshold: float) -> Dict[str, object]:
    path_list = list(paths)
    transactions = read_transactions(path_list)
    aggregates = aggregate_descriptions(transactions)
    transactions_by_desc: Dict[tuple[str, str], List[Dict[str, object]]] = {}
    for txn in transactions:
        desc = str(txn["description"])
        category = str(txn.get("category") or "").strip()
        transactions_by_desc.setdefault((desc, category), []).append(txn)
    clusters = cluster_descriptions(aggregates, transactions_by_desc, threshold)
    mapping: Dict[str, List[str]] = {}
    for cluster in clusters:
        root = cluster["root_label"]
        mapping[root] = [item["description"] for item in cluster["items"]]

    return {
        "stats": {
            "statement_files": len(path_list),
            "total_transactions": len(transactions),
            "unique_descriptions": len(aggregates),
            "similarity_threshold": threshold,
        },
        "mapping": mapping,
        "clusters": clusters,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize and cluster transaction descriptions.")
    parser.add_argument(
        "--statements-dir",
        default=str(pathlib.Path(__file__).resolve().parent / "statements"),
        help="Directory containing statement CSVs.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Similarity threshold (0-1) for grouping descriptions.",
    )
    parser.add_argument(
        "--out",
        default=str(pathlib.Path(__file__).resolve().parent / "dashboard" / "data.json"),
        help="Output JSON path for the dashboard.",
    )
    args = parser.parse_args()

    statements_dir = pathlib.Path(args.statements_dir)
    paths = sorted(statements_dir.glob("*.CSV"))
    summary = build_summary(paths, args.threshold)

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print(f"Wrote summary to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
