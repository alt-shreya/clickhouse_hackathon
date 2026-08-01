# Known-issues log validation

1. **K1 — iOS WebKit OTP autofill regression.** On recent iOS builds the payment OTP
   field fails to autofill, and some users abandon at the pay step. Payment-heavy
   geos (Gulf card users) are most exposed. Watch `pay_now_clicked → purchase_completed`
   for iOS.  
   **Finding:** *leave blank (not yet validated)*

2. **K2 — Passport scan model update (Apr 2026).** The on-device passport model was
   updated in early April. Some Android devices report more capture failures since;
   being monitored.  
   **Finding:** *yes it was 7–9%, increased to 13–20%*

3. **K3 — MRZ OCR weaker on non-Latin passports.** Passports with non-Latin
   machine-readable zones need more capture retries.  
   **Finding:** *11% almost same as latin*

4. **K4 — Schengen summer slot scarcity (Apr–Jun).** Appointment slots for Schengen
   destinations are scarce in summer; expect seasonal softness, not a bug.  
   **Finding:** *doesn't seem like it*

5. **K5 — WhatsApp nudge launch (Feb 2026).** A WhatsApp re-engagement nudge went
   live in February; it can lift returns to the funnel for previously-dropped users.  
   **Finding:** *slightly improved, but document upload to pay reduced relatively*

6. **K6 — SUMMER20 coupon campaign.** A `SUMMER20` promo ran in Q2; expect elevated
   `coupon_applied` and lower realised `value`.  
   **Finding:** *Jan to Jun 5–6% of purchases*

7. **K7 — App 7.45 rollout.** App version 7.45.x rolled out mid-quarter; minor
   funnel-timing shifts around the rollout are expected.  
   **Finding:** *almost same*