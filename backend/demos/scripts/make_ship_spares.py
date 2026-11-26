"""Generate the synthetic ship-spares corpus: inventory CSV, suppliers CSV, 3 supplier-terms PDFs in different
layouts, and maintenance notes. Fixed seed, fictional suppliers (example.com emails), no real companies.

Run from backend/:  python demos/scripts/make_ship_spares.py
"""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pdf_util import write_pdf  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "ship_spares" / "docs"
ORG = "Fleet engineering demo (fictional)"

EQUIPMENT = {
    "Main engine": ("ME", ["fuel injector", "exhaust valve spindle", "piston ring set", "cylinder liner O-ring",
                           "fuel pump plunger", "starting air valve"]),
    "Auxiliary engine": ("AE", ["fuel injector nozzle", "turbocharger bearing", "cooling water pump seal",
                                "lube oil filter element", "thermostat element"]),
    "Fuel oil purifier": ("FP", ["bowl gasket", "disc stack", "gravity disc", "vertical shaft bearing"]),
    "Ballast pump": ("BP", ["mechanical seal", "impeller", "wear ring", "shaft sleeve"]),
    "Air compressor": ("AC", ["suction valve", "delivery valve", "piston ring", "unloader valve"]),
    "Boiler": ("BL", ["burner nozzle", "ignition electrode", "flame scanner", "gauge glass"]),
}
SUPPLIERS = [
    ("S01", "Ostrava Marine Parts", "Czechia", "Hamburg", "sales@ostrava-marine.example.com"),
    ("S02", "Bluewake Supply", "Netherlands", "Rotterdam", "orders@bluewake.example.com"),
    ("S03", "Kestrel Engineering", "Singapore", "Singapore", "parts@kestrel-eng.example.com"),
    ("S04", "Harrowgate Marine", "United Kingdom", "Southampton", "desk@harrowgate.example.com"),
    ("S05", "Nordkapp Technical", "Norway", "Bergen", "post@nordkapp-tech.example.com"),
    ("S06", "Mistral Navale", "Italy", "Genoa", "ricambi@mistral-navale.example.com"),
    ("S07", "Pacific Rim Spares", "South Korea", "Busan", "spares@pacrim.example.com"),
    ("S08", "Gulf Anchor Trading", "United Arab Emirates", "Jebel Ali", "trade@gulfanchor.example.com"),
]
LOCATIONS = ["ER store A", "ER store B", "Spare room deck 2", "Purifier room", "Workshop locker"]


def inventory(rng: random.Random) -> list[dict]:
    rows = []
    n = 0
    while len(rows) < 300:
        equip = rng.choice(list(EQUIPMENT))
        code, parts = EQUIPMENT[equip]
        part = rng.choice(parts)
        n += 1
        min_stock = rng.choice([1, 2, 2, 3, 4, 6])
        qty = max(0, min_stock + rng.choice([-2, -1, 0, 1, 2, 3, 5]))
        price = round(rng.uniform(15, 2400) * (3 if "liner" in part or "turbo" in part else 1), 2)
        rows.append({
            "part_no": f"{code}-{rng.choice(['6S50', '7L32', 'MAB', 'NS', 'TC'])}-{n:04d}",
            "description": part, "equipment": equip, "maker_ref": f"MR{rng.randint(100000, 999999)}",
            "qty_on_board": qty, "min_stock": min_stock, "location": rng.choice(LOCATIONS),
            "unit_price_usd": price, "supplier_id": rng.choice(SUPPLIERS)[0]})
    return rows


TERMS_A = """
## 1. Scope
These terms apply to all spare parts supplied by Ostrava Marine Parts (S01) and Bluewake Supply (S02), which
trade under a joint framework agreement.

## 2. Lead times
| part family            | S01 lead time | S02 lead time |
| fuel injection parts   | 10 days       | 7 days        |
| valves and spindles    | 21 days       | 14 days       |
| seals and gaskets      | 5 days        | 4 days        |
| bearings               | 15 days       | 12 days       |
Lead times are counted in calendar days from order confirmation to delivery at the named port.

## 3. Minimum order quantity
The minimum order value is 250 USD per order. Seals and gaskets are sold in packs of 5.

## 4. Warranty
All parts carry a 12-month warranty from delivery, or 6,000 running hours, whichever comes first.
Warranty claims must be filed within 30 days of discovering the defect, with photos and the part number.

## 5. Delivery ports
S01 delivers to Hamburg and Rotterdam. S02 delivers to Rotterdam, Antwerp and Le Havre.
Urgent delivery (48 hours) is available for an extra charge of 15 percent of the order value.
"""

TERMS_B = """
## Supplier: Kestrel Engineering (S03)
Kestrel Engineering supplies purifier and pump parts from its warehouse in Singapore. Standard delivery to
Singapore port takes 3 days for items in stock and 25 days for items that must be ordered from the maker.
Deliveries to Busan and Hong Kong add 4 days. Every order above 5,000 USD receives a 5 percent discount.
Kestrel gives an 18-month warranty on all purifier parts and a 12-month warranty on pump parts. Returns of
unused parts are accepted within 60 days with a 10 percent restocking fee. Kestrel does not supply main engine
parts.

## Supplier: Pacific Rim Spares (S07)
Pacific Rim Spares supplies auxiliary engine and air compressor parts. Lead time is 9 days to Busan and 14 days
to Singapore. The minimum order value is 400 USD. Warranty is 12 months from delivery.
"""

TERMS_C = """
## Harrowgate Marine (S04) - Price list conditions
1. Prices in the inventory are valid until 30 June 2026. After that date a price revision of up to 8 percent
   may apply; the buyer is informed at least 30 days before.
2. Boiler parts: lead time 12 days to Southampton, 18 days to any other European port.
3. Compressor valves: lead time 8 days. Minimum order 2 units per part number.
4. Warranty: 12 months. Burner nozzles and ignition electrodes are consumables and have no warranty.

## Nordkapp Technical (S05) - Delivery terms
1. Delivery to Bergen in 6 days and to Hamburg in 9 days for all part families.
2. Orders placed before 12:00 Norwegian time are dispatched the same day.
3. Special offer: 10 percent off ballast pump seals, valid until 31 December 2025 (expired offers are not honoured).
4. Warranty: 24 months on ballast pump parts, 12 months on everything else.
"""

NOTES = """# Maintenance and reorder notes (fictional fleet)

## Critical spares
The following parts are critical and must never fall below minimum stock: main engine fuel injectors, exhaust
valve spindles, starting air valves, boiler flame scanners and ballast pump mechanical seals. If a critical
part is at or below minimum stock, a reorder must be raised the same day.

## Reorder rule
For non-critical parts, reorder when qty_on_board is below min_stock. Order enough to reach min_stock plus 2.

## Approval
The chief engineer raises requisitions; purchases above 2,000 USD are approved by the technical superintendent
ashore. The assistant must not approve purchases.

## Safety
Work on high-pressure fuel systems and boilers follows the vessel's permit-to-work procedure. Repair
instructions must come from the maker's manual, not from this assistant.
"""


def main() -> None:
    rng = random.Random(42)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = inventory(rng)
    with (OUT / "spares_inventory.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with (OUT / "suppliers.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["supplier_id", "name", "country", "main_port", "contact_email"])
        w.writerows(SUPPLIERS)
    write_pdf(OUT / "supplier_terms_A.pdf", "Framework terms S01 and S02", TERMS_A, ORG)
    write_pdf(OUT / "supplier_terms_B.pdf", "Supplier conditions Asia", TERMS_B, ORG)
    write_pdf(OUT / "supplier_terms_C.pdf", "Price list and delivery terms Europe", TERMS_C, ORG)
    (OUT / "maintenance_notes.md").write_text(NOTES, encoding="utf-8")
    below = sum(1 for r in rows if r["qty_on_board"] < r["min_stock"])
    print(f"wrote {len(rows)} inventory rows ({below} below min stock) and supplier docs to {OUT}")
    readme = OUT / "README.md"
    if readme.exists() and "delete this readme" in readme.read_text(encoding="utf-8").lower():
        readme.unlink()


if __name__ == "__main__":
    main()
