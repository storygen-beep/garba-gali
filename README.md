# Garba Gali

Booking tool for a Navratri lehenga rental store: what is free on which night,
who has what, what comes back each morning, and the money owed.

- `index.html` — the whole page (markup + styles)
- `app.js` — behaviour: availability grid, bookings, backup and restore
- `vendor/supabase.js` — Supabase browser client, vendored so the page has no CDN dependency
- `supabase/migrations/` — database tables and the row-level security rules

## How access works

Anyone can open the page, but the data needs a sign-in. Reads and writes are allowed
only for accounts listed in the `staff` table, enforced by row-level security — so the
public `anon` key in this repo grants nothing on its own.

To add a member of staff: create the user in Supabase Auth, then insert their user id
into `public.staff`.

## Rules the app enforces

- Rent is per night; the deposit is per lehenga and refundable.
- A booking holds its nights only once an advance is paid (Status becomes Confirmed).
- A lehenga is due back by 10 AM the morning after its last night, and can go out again
  that same evening.
- Two confirmed bookings overlapping on one lehenga are flagged as a clash.
