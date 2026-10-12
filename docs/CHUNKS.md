# Chunk inventory

| doc | clause | kind | tokens | tags | first 80 chars |
|-----|--------|------|--------|------|----------------|
| RW-POL-01 | 1.1 | clause | 52 |  | The customer must be at least 18 years old and hold a valid driving licence for  |
| RW-POL-01 | 1.2 | clause | 49 |  | Each customer may hold one RideWise account, registered with a mobile number and |
| RW-POL-01 | 2.1 | table | 117 | cancellation,kyc | Every account goes through KYC (Know Your Customer) verification of the driving  |
| RW-POL-01 | 2.2 | clause | 75 | refund,cancellation,kyc | If KYC is still pending at the scheduled pickup time, or is rejected, RideWise c |
| RW-POL-01 | 3.1 | clause | 76 |  | Vehicles are picked up from and returned to the same RideWise hub. RideWise oper |
| RW-POL-01 | 3.2 | clause | 67 |  | The rental period runs from the scheduled pickup time to the scheduled return ti |
| RW-POL-01 | 3.3 | clause | 55 | late_fee,damage,ev_charging | A return after the scheduled return time is a late return and is charged under t |
| RW-POL-01 | 4.1 | clause | 98 | ev_charging,rental_charge | Each vehicle has an hourly rate and a daily rate (per 24 hours). The rental char |
| RW-POL-01 | 4.2 | example | 99 | ev_charging,rental_charge | Worked examples (vehicle with an hourly rate of ₹80 and a daily rate of ₹700): B |
| RW-POL-01 | 4.3 | clause | 63 | refund,gst,ev_charging,rental_charge | GST at 18% is added to rental charges, penalties and fees. When a refund is issu |
| RW-POL-01 | 4.4 | clause | 72 | ev_charging,rental_charge | The full rental charge is paid when the booking is made. Payment may be complete |
| RW-POL-01 | 5.1 | clause | 78 | refund,deposit | A refundable security deposit may be collected when the booking is made: Vehicle |
| RW-POL-01 | 5.2 | clause | 72 | deposit,gst,ev_charging,rental_charge | The deposit is not a rental charge, carries no GST, and is returned to the origi |
| RW-POL-01 | 5.3 | clause | 55 | deposit | Deposit returns are processed directly by the payment gateway and are not shown  |
| RW-POL-01 | 6.1 | clause | 83 | late_fee,grace,damage,tiers | Customers are placed in one of three tiers (STANDARD, SILVER or GOLD) based on t |
| RW-POL-01 | 7.1 | clause | 69 | cancellation,no_show | A booking is a no-show when the customer neither picks up the vehicle within 60  |
| RW-POL-01 | 7.2 | clause | 48 | refund,no_show,ev_charging,rental_charge | The rental charge for a no-show is not refunded. No additional fee is charged fo |
| RW-POL-01 | 8.1 | clause | 52 |  | The customer must ride safely, follow traffic laws, wear a helmet and not lend t |
| RW-POL-01 | 8.2 | clause | 45 |  | The customer is responsible for traffic fines incurred during the rental period. |
| RW-POL-01 | 8.3 | clause | 52 | late_fee,damage,ev_charging | Damage found at return is assessed by hub staff and charged under the Late Retur |
| RW-POL-01 | 9. | clause | 52 |  | Contact RideWise Support: support@ridewise.example · +91 80 4000 1234 (7:00 AM t |
| RW-POL-01 | Authorised Signatory | clause | 49 |  | Authorised signatory Head of Customer Operations, RideWise Mobility Pvt. Ltd. |
| RW-POL-02 | Scope | clause | 101 | cancellation | Scope. This version applies to bookings made before 1 July 2026, 00:00 IST. Book |
| RW-POL-02 | 1.1 | table | 123 | refund,cancellation,ev_charging,rental_charge | The customer can cancel a booking in the RideWise app at any time before the sch |
| RW-POL-02 | 1.2 | clause | 67 | refund,gst,ev_charging,rental_charge | The refund percentage is applied to the rental charge actually paid. GST on the  |
| RW-POL-02 | 2.1 | clause | 74 | refund,cancellation,kyc | If RideWise cancels a booking for any reason (for example vehicle unavailability |
| RW-POL-02 | 3.1 | clause | 59 | refund,cancellation,no_show | A no-show (see Rental Agreement clause 7) is not a cancellation. No refund is gi |
| RW-POL-02 | 4.1 | clause | 68 | refund,cancellation | Refunds are initiated within 3 working days of the cancellation and credited to  |
| RW-POL-02 | 4.2 | clause | 59 | refund,cancellation,deposit | Security deposits are returned in full on cancellation and are not subject to th |
| RW-POL-02 | 5. | example | 98 | refund,cancellation,gst,ev_charging,rental_charge | Example Example Booking made 10 May 2026, 18:00 IST (Version 1 applies) Schedule |
| RW-POL-03 | Scope | clause | 90 | cancellation | Scope. This version replaces Version 1 for all bookings made on or after 1 July  |
| RW-POL-03 | Why It Changed | clause | 85 | refund,cancellation,ev_charging,rental_charge | Why it changed. Version 2 introduces a wider full-refund window and a new partia |
| RW-POL-03 | 1.1 | clause | 74 | refund,cancellation | The refund depends on how long before the scheduled pickup time the booking is c |
| RW-POL-03 | 1.2 | clause | 68 | refund,gst,ev_charging,rental_charge | The refund percentage is applied to the rental charge actually paid. GST on the  |
| RW-POL-03 | 2.1 | clause | 56 | refund,cancellation | Unchanged from Version 1: a booking cancelled by RideWise is always refunded 100 |
| RW-POL-03 | 3.1 | clause | 50 | refund,no_show | Unchanged from Version 1: no refund is given for a no-show. |
| RW-POL-03 | 4.1 | clause | 83 | refund,cancellation,deposit | Refunds are initiated within 3 working days of the cancellation and credited to  |
| RW-POL-04 | 1.1 | clause | 48 | late_fee | Lateness is measured from the scheduled return time to the actual return time. |
| RW-POL-04 | 1.2 | clause | 72 | late_fee,ev_charging,rental_charge | Each late hour, or part of an hour, is charged at 1.5 times the vehicle's hourly |
| RW-POL-04 | 1.3 | clause | 91 | late_fee,grace,ev_charging | Customers in some tiers receive a grace period before a late fee applies. Grace  |
| RW-POL-04 | 1.4 | example | 82 | late_fee,grace,ev_charging,rental_charge | Late fee examples (vehicle hourly rate ₹100, customer with no grace period): Ret |
| RW-POL-04 | 1.5 | table | 246 | late_fee,rental_charge | Late fee per hour by vehicle model. The table below lists each model's hourly ra |
| RW-POL-04 | 2. | clause | 61 | battery,ev_charging | EV low-battery charging fee Battery level at return (EV scooter, EV bike) Fee Be |
| RW-POL-04 | 2.1 | clause | 45 | late_fee | This fee is in addition to any late return fee on the same rental. |
| RW-POL-04 | 3.1 | clause | 133 | damage,ev_charging | Damage found at return is recorded in a damage report by the customer or by hub  |
| RW-POL-04 | 3.2 | clause | 46 | damage,ev_charging | Lost keys are treated as damage and charged at the cost of replacement. |
| RW-POL-05 | 1. | clause | 148 | battery,ev_charging | Our electric fleet Model Type Battery Typical range* Full charge (home socket) A |
| RW-POL-05 | 2.1 | clause | 47 | battery,ev_charging | Check the battery level on the dashboard at pickup. Every EV leaves the hub with |
| RW-POL-05 | 2.2 | clause | 46 | ev_charging | Plan your trip so that you return with enough charge. Riding in Eco mode gives t |
| RW-POL-05 | 3.1 | clause | 47 | ev_charging | You may charge at any RideWise hub or an approved public charger. Charging at a  |
| RW-POL-05 | 4.1 | clause | 45 | battery | Return the EV to the same hub you picked it up from, with the battery level show |
| RW-POL-05 | FAQ: What happens if the battery runs out dur | faq | 101 | battery,ev_charging | Q. What happens if the battery runs out during my trip? Stop in a safe place and |
| RW-POL-05 | FAQ: Can I charge the EV at home | faq | 62 | ev_charging | Q. Can I charge the EV at home? Yes. Use only the RideWise charging cable suppli |
| RW-POL-05 | FAQ: What if I return the EV with less than 1 | faq | 70 | late_fee,battery,damage,ev_charging | Q. What if I return the EV with less than 10% battery? A flat low-battery chargi |
| RW-POL-05 | FAQ: Does a low-battery return also count as | faq | 65 | late_fee,battery | Q. Does a low-battery return also count as a late return? No. They are separate. |
| RW-POL-05 | FAQ: Who pays for damage to the charging port | faq | 69 | damage,ev_charging | Q. Who pays for damage to the charging port or cable? Damage is assessed by hub  |
| RW-POL-05 | FAQ: My dashboard shows a battery warning lig | faq | 75 | battery | Q. My dashboard shows a battery warning light. What should I do? Stop riding, sw |
| RW-POL-03 | Annexure 1 | table | 262 | cancellation,ev_charging,no_show,refund,rental_charge | ## Annexure 1 — Approved refund schedule (Version 2)  Source: `data/03_Cancellat |
| RW-POL-04 | Annexure A | table | 236 | damage,ev_charging,grace,late_fee,tiers | ## Annexure A — Tier benefits (late return grace period)  Source: `data/04_Late_ |
