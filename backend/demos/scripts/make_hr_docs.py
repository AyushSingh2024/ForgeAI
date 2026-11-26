"""Generate the synthetic HR policy PDFs for the fictional company "Brightfield Labs" (no real organisation).

Run from backend/:  python demos/scripts/make_hr_docs.py      (needs the dev extra: pip install -e ".[dev]")
Topics overlap on purpose (travel during leave, remote work and expenses) so multi-document cases exist, and some
obvious gaps are left (no relocation policy, no salary bands) so the groundability guard has something to flag.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pdf_util import write_pdf  # noqa: E402

ORG = "Brightfield Labs (fictional)"
OUT = Path(__file__).resolve().parents[1] / "hr_policy" / "docs"

DOCS = {
    "leave_policy": ("Leave Policy (version 3.1)", """
## 1. Annual leave
1.1 Full-time employees receive 25 working days of paid annual leave per calendar year.
1.2 Part-time employees receive annual leave pro rata to their contracted hours.
1.3 Annual leave accrues monthly at 2.08 days per month of service.
1.4 Up to 5 unused days may be carried over into the next year. Carried-over days expire on 31 March.
1.5 Leave requests of more than 10 consecutive working days must be submitted at least 4 weeks in advance.
1.6 During the first 3 months (probation), employees may take at most 5 days of annual leave.

## 2. Sick leave
2.1 Employees must notify their manager before 10:00 on the first day of absence.
2.2 Absences of up to 3 consecutive days can be self-certified.
2.3 From the 4th consecutive day, a medical certificate is required.
2.4 Employees receive full pay for up to 20 sick days per rolling 12 months, then 50 percent pay for a further 40 days.

## 3. Parental leave
3.1 Birthing parents receive 20 weeks of parental leave at full pay.
3.2 Non-birthing and adoptive parents receive 12 weeks of parental leave at full pay.
3.3 Parental leave can be taken in up to 3 blocks within 18 months of the birth or adoption.
3.4 Employees must give at least 8 weeks notice of the planned start date.

## 4. Other leave
4.1 Bereavement leave: 5 days for a partner, child or parent; 2 days for other close relatives.
4.2 Moving house: 1 day of paid leave once per calendar year.
4.3 Volunteering: 2 paid days per year for registered charities, approved by the manager.
4.4 Unpaid leave of up to 3 months may be requested after 2 years of service.

## 5. Travel during leave
5.1 Employees who travel abroad during annual leave and fall ill must follow the sick leave rules in section 2;
the days of illness are then not counted as annual leave if a medical certificate is provided.
"""),
    "travel_expenses": ("Travel and Expenses Policy (version 2.4)", """
## 1. Approval
1.1 All business travel must be approved in advance by the employee's manager.
1.2 Trips outside Europe also need approval from the department director.
1.3 Expenses above 500 EUR per item require a second approver.

## 2. Transport
2.1 Train is the default for journeys under 5 hours.
2.2 Economy class is used for flights under 6 hours; premium economy is allowed for flights of 6 hours or more.
2.3 Private car use is reimbursed at 0.30 EUR per kilometre.
2.4 Taxis are reimbursed when public transport is unavailable or after 22:00.

## 3. Accommodation
3.1 Hotel limits per night: Tier A cities (London, Paris, New York, Zurich) 220 EUR; Tier B cities 150 EUR; all other places 110 EUR.
3.2 Bookings must be made through the company travel portal.

## 4. Per diem
4.1 The daily allowance for meals is 60 EUR in Tier A cities, 45 EUR in Tier B cities and 35 EUR elsewhere.
4.2 If a meal is provided (for example by a conference), the per diem is reduced by 30 percent for that day.
4.3 Alcohol is not reimbursed.

## 5. Claims
5.1 Expense claims must be submitted within 30 days of the end of the trip.
5.2 Original receipts or clear photos are required for every item above 10 EUR.
5.3 Claims submitted after 90 days are not reimbursed.

## 6. Home office equipment
6.1 Remote workers may claim a one-off home office allowance; see the Remote Work Policy section 3.
"""),
    "remote_work": ("Remote Work Policy (version 1.6)", """
## 1. Eligibility
1.1 Employees who have completed probation may work remotely up to 3 days per week.
1.2 Fully remote contracts require director approval and are reviewed every 12 months.
1.3 Remote work from another country is allowed for at most 20 working days per calendar year.

## 2. Working hours
2.1 Core hours are 10:00 to 15:00 local office time; employees must be reachable during core hours.
2.2 Employees must record remote days in the HR portal by Friday of each week.

## 3. Equipment
3.1 The company provides a laptop, a monitor and a headset.
3.2 Remote workers receive a one-off home office allowance of 400 EUR for a desk and chair, claimable through the expenses process within 6 months of starting remote work.
3.3 Internet costs are reimbursed up to 25 EUR per month for employees on a fully remote contract.

## 4. Security
4.1 Company data may only be accessed over the company VPN.
4.2 Working from public places requires a privacy screen filter, which IT provides on request.
4.3 Lost or stolen equipment must be reported to IT within 24 hours.
"""),
    "code_of_conduct": ("Code of Conduct (version 5.0)", """
## 1. Respect at work
1.1 Harassment, discrimination and bullying are not tolerated in any form.
1.2 Concerns can be raised with a manager, with HR, or anonymously through the Speak Up line.

## 2. Gifts and hospitality
2.1 Employees may accept gifts with a value of up to 50 EUR from business partners.
2.2 Gifts above 50 EUR must be declared in the gifts register within 5 working days and are usually returned.
2.3 Cash gifts are never allowed.

## 3. Conflicts of interest
3.1 Employees must declare any outside job, directorship or financial interest in a supplier or competitor.
3.2 Declarations are made to HR and reviewed by the compliance officer within 10 working days.

## 4. Confidentiality
4.1 Confidential information must not be shared outside the company without a signed non-disclosure agreement.
4.2 The duty of confidentiality continues for 2 years after employment ends.

## 5. Breaches
5.1 Breaches of this code may lead to disciplinary action up to and including dismissal.
5.2 Retaliation against anyone who raises a concern in good faith is itself a breach of this code.
"""),
    "benefits_overview": ("Benefits Overview 2026", """
## 1. Health
1.1 The company pays 80 percent of the premium for the group health insurance plan; employees pay 20 percent.
1.2 Dental cover is included for employees and optional for family members at their own cost.

## 2. Learning
2.1 Each employee has a learning budget of 1,200 EUR per calendar year.
2.2 Unused learning budget does not carry over to the next year.
2.3 Courses over 600 EUR need manager approval.

## 3. Wellbeing
3.1 A wellness allowance of 300 EUR per year can be used for gym memberships or sports clubs.
3.2 Employees have access to 6 free confidential counselling sessions per year through the Employee Assistance Programme.

## 4. Pension
4.1 The company contributes 6 percent of the base salary to the pension plan when the employee contributes at least 3 percent.

## 5. Commuting
5.1 Public transport passes are reimbursed up to 100 EUR per month.
5.2 Employees who cycle to work can lease a bike through the bike scheme.
"""),
}


def main() -> None:
    for name, (title, body) in DOCS.items():
        write_pdf(OUT / f"{name}.pdf", title, body, ORG)
        print("wrote", OUT / f"{name}.pdf")
    readme = OUT / "README.md"
    if readme.exists() and "delete this readme" in readme.read_text(encoding="utf-8").lower():
        readme.unlink()


if __name__ == "__main__":
    main()
