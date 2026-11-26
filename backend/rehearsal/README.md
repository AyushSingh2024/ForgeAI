# Rehearsal briefs (generality testing, never demoed)

At review an unseen brief runs unattended, so the factory is rehearsed on very different inputs first.

| folder | what it tests | expected |
|---|---|---|
| `product_manual/` | one prose manual, troubleshooting | no tools |
| `course_handbook/` | deadlines and dates | `current_date` (and `calculator`) |
| `mostly_unsupported/` | a brief asking mostly for things the docs don't contain | the guard flags most asks; the agent refuses them |

Add more when you can: a CSV-only corpus, a 1-page corpus, a non-English document, a scanned PDF.

Run each one from `backend/`:

```
forge build --brief rehearsal/product_manual/brief.txt --docs rehearsal/product_manual/docs --unattended
```

Rule: when a rehearsal fails, fix GENERIC code only. Never add a special case for that brief.
