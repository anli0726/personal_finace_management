from __future__ import annotations

from typing import List


def default_account_rows() -> List[dict[str, float | str]]:
    return [
        {
            "Name": "Cash Reserve",
            "Category": "cash",
            "Principal": 20000.0,
            "APR (%)": 1.0,
            "Interest Rate (%)": 0.0,
            "Start Month": "",
            "End Month": "",
            "Action at End": "keep",
        },
        {
            "Name": "Certificate of Deposit",
            "Category": "investment",
            "Principal": 10000.0,
            "APR (%)": 3.0,
            "Interest Rate (%)": 0.0,
            "Start Month": "",
            "End Month": "",
            "Action at End": "keep",
        },
        {
            "Name": "Index Fund",
            "Category": "investment",
            "Principal": 15000.0,
            "APR (%)": 5.0,
            "Interest Rate (%)": 0.0,
            "Start Month": "",
            "End Month": "",
            "Action at End": "keep",
        },
        {
            "Name": "HSA",
            "Category": "investment",
            "Principal": 6000.0,
            "APR (%)": 4.0,
            "Interest Rate (%)": 0.0,
            "Start Month": "",
            "End Month": "",
            "Action at End": "keep",
        },
        {
            "Name": "Taxable Brokerage",
            "Category": "investment",
            "Principal": 20000.0,
            "APR (%)": 6.0,
            "Interest Rate (%)": 0.0,
            "Start Month": "",
            "End Month": "",
            "Action at End": "keep",
        },
        {
            "Name": "401k",
            "Category": "investment",
            "Principal": 30000.0,
            "APR (%)": 6.0,
            "Interest Rate (%)": 0.0,
            "Start Month": "",
            "End Month": "",
            "Action at End": "keep",
        },
        {
            "Name": "Car",
            "Category": "asset",
            "Principal": 18000.0,
            "APR (%)": -12.0,
            "Interest Rate (%)": 0.0,
            "Start Month": "",
            "End Month": "",
            "Action at End": "keep",
        },
    ]
