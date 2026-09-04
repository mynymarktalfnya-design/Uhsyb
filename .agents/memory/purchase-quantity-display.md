---
name: Purchase quantity display
description: The consistent business meaning of piece and carton quantities in supplier and purchase reports.
---

Purchase statements must show the purchase unit and its count explicitly: piece purchases use “عدد قطعة”, while carton purchases use “عدد كرتون” and, when the pack size is known, the derived total piece count.

**Why:** Showing only the stored quantity is ambiguous because carton purchase records also retain a piece-equivalent quantity for stock calculations.

**How to apply:** Reuse the shared quantity formatter in supplier statements, daily/monthly purchase reports, and their PDF exports; do not silently label carton quantities as pieces.