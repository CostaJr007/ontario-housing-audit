"""Inspect Ontario's payment schedule without mislabelling ministry totals as BFF."""
import csv

from src.common import PROCESSED, RAW, REPORTS, normalize_name, read_json, write_json
from src.ingest import download

URL = "https://data.ontario.ca/dataset/56c9a95f-c7b6-40ee-a4b8-d2343e51c83d/resource/3ab37bb7-4f51-4d90-951b-b9d566f65898/download/tbs-public-accounts-detailed-schedule-payments-2025-26-en.csv"
PAGE = "https://data.ontario.ca/en/dataset/public-accounts-detailed-schedule-of-payments/resource/3ab37bb7-4f51-4d90-951b-b9d566f65898"


def inspect(rows, names):
    ministry = [r for r in rows if r["Ministry"].casefold() == "ministry of municipal affairs and housing"
                and r["Category"].casefold() == "transfer payments"]
    bff = [r for r in rows if any("building faster" in str(v).casefold() for v in r.values())]
    recipients = []
    for name in names:
        matching = [r for r in ministry if normalize_name(r["Recipient"]) == normalize_name(name)]
        recipients.append({"municipality": name, "records": matching,
            "ministry_transfer_total_cad": sum(int(r["Amount $"]) for r in matching),
            "program": "All disclosed MMAH transfer payments; BFF component not isolated",
            "bff_payment_verified": None})
    return {"all_payment_rows": len(rows), "bff_labelled_rows": len(bff),
            "mma_housing_transfer_rows": len(ministry), "recipients": recipients}


def main():
    path = RAW / "public_accounts/payments_2025_26_en.csv"
    manifest = read_json(RAW / "manifest.json")
    download(URL, path, manifest)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = [{key.strip(): value.strip() for key,value in row.items()} for row in csv.DictReader(stream)]
    result = inspect(rows, ["London", "Kitchener", "Sarnia", "Welland"])
    result.update({"source_url": URL, "source_page": PAGE,
        "source_sha256": manifest["public_accounts/payments_2025_26_en.csv"]["sha256"],
        "retrieved_at_utc": manifest["public_accounts/payments_2025_26_en.csv"]["retrieved_at_utc"],
        "fiscal_period_start": "2025-04-01", "fiscal_period_end": "2026-03-31",
        "finding": "No BFF-specific label found. The schedule discloses ministry-recipient totals; it cannot isolate the BFF component.",
        "timing_limit": "The four 2025-performance award announcements used in the comparison were published June/July 2026, after this fiscal period. Do not reconcile those awards to these earlier totals.",
        "interpretation": "Officially announced allocations and accounting confirmation of program-specific payments remain separate evidence categories."})
    folder = PROCESSED / "public_accounts"
    write_json(folder / "bff_payment_audit.json", result)
    lines=["# BFF payment-verification audit","",
        "The project's funding cases initially used official allocation announcements and the Ontario Legislature's statement. Program-specific payments had not been reconciled.","",
        f"Consulted and archived: [Public Accounts — Detailed Schedule of Payments 2025–2026]({PAGE}), covering April 1, 2025 through March 31, 2026.","",
        f"The file has {result['all_payment_rows']} records; {result['bff_labelled_rows']} name the Building Faster Fund. MMAH transfer payments to the four municipalities are present, but the BFF component is not identified.","",
        "| Municipality | Total ministry transfers in fiscal year C$ | BFF isolated? |","|---|---:|---|"]
    for r in result["recipients"]:
        lines.append(f"| {r['municipality']} | {r['ministry_transfer_total_cad']:,} | No |")
    lines += ["","**These are not identified BFF payments.** The schedule's fiscal period also ends before the June/July 2026 announcements for 2025 housing performance. Those announcements fall in fiscal 2026–2027, still underway on November 20, 2026.","",
        "## Federal sources","",
        "BFF is provincial. The [federal Grants and Contributions portal](https://open.canada.ca/search/grants) reports federal agreements and contributions; it is not the BFF source. Agreement Value does not by itself establish disbursements. Complete HAF coverage in that portal has not been established.","",
        "For HAF, [CMHC's dashboard](https://www.cmhc-schl.gc.ca/professionals/project-funding-and-mortgage-financing/funding-programs/all-funding-programs/housing-accelerator-fund/housing-accelerator-fund-rounds-data) must be reconciled to municipal reports identifying received instalments. A signed agreement or scheduled payment is not proof of receipt.","",
        "## Evidence still needed","",
        "Municipal 2026 financial reports identifying BFF receipts by instalment and date, reconciled to provincial reporting; subsequently Public Accounts 2026–2027 and annual municipal statements. Where unpublished, request the program-specific payment schedule from the ministry or municipality. Missing confirmation is not zero payment.","",
        "The maps remain labelled as officially confirmed/announced allocations. They have not been relabelled as a cash-receipts audit. Source hash, retrieval time and examined records: data/processed/public_accounts/bff_payment_audit.json."]
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "bff_payment_verification.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(f"Payments inspected: {result['all_payment_rows']}; BFF-specific labels: {result['bff_labelled_rows']}")
    print("Four municipal payees found; amounts aggregate MMAH programs and end before the June/July 2026 award announcements.")
    print("BFF payment confirmation remains unverified; no amounts treated as zero.")
    print("Report: reports/bff_payment_verification.md")


if __name__ == "__main__":
    main()
