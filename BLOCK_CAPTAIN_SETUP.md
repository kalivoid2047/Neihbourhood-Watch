# Block Captain Setup

Block captains sign in on the normal login page with their email and password. There is no separate login. Registration always creates a **resident**, so a captain account has to be created or promoted by an administrator using the command below.

## Create a new block captain

Run from the `backend/` directory:

```bash
python manage.py create_block_captain \
  --email captain@example.com \
  --password "S3cure!pass" \
  --full-name "Jane Captain" \
  --phone +263771234567 \
  --national-id 63-123456A21 \
  --neighborhood <neighbourhood-code>
```

All of `--email`, `--password`, `--full-name`, `--phone` and `--national-id` are required when the account does not exist yet.

## Promote an existing account

If the person has already registered, pass only their email:

```bash
python manage.py create_block_captain --email captain@example.com --neighborhood <neighbourhood-code>
```

Add `--password` to reset their password at the same time.

## What the command does

- Sets the account role to **Block Captain**.
- Marks the account as approved and OTP-verified, so no verification step blocks login.
- Makes sure the account is active.
- With `--neighborhood`, adds the captain to that neighbourhood (matched by its `code`) with the captain role, so the neighbourhood's incidents appear on their map. Without it, the captain only sees incidents they reported or that happen near their location.

## Signing in

1. Open the site and go to **Sign in**.
2. Enter the email and password used above.
3. The captain lands on the incidents page. The review/coordinator page is available from the header.

## What a captain can do

- Report incidents and see neighbourhood incidents on the live map.
- Verify incidents and send neighbourhood alerts.
- Monitor SOS sessions in their neighbourhood.

## Live map and SOS alarms

For a captain to see other people's reports and hear SOS alarms:

- They should allow browser location access, or have a home address with coordinates saved. Without either, the server cannot tell they are nearby.
- They should tap or click the page once after opening it, because browsers block audio until then.
- SOS alarms reach users within `SOS_ALERT_RADIUS_M` (default 2 km) of the SOS.

## Troubleshooting

| Problem | Cause / fix |
|---|---|
| `No neighbourhood with code '...'` | The `--neighborhood` value is the neighbourhood's `code` (slug), not its name. Check it in the Django admin. |
| `Creating a new account also needs: ...` | The email isn't registered yet, so supply the missing flags. |
| Login says "Invalid email or password" | Wrong credentials, or the account is inactive. Re-run the command with `--password` to reset. |
| Captain sees an empty map | They haven't joined a neighbourhood and have no location. Re-run with `--neighborhood`, or have them allow location access. |

## Alternative: Django admin

Open `/admin/`, go to **Users**, set **Role** to *Block Captain* and **Verification status** to *Approved*. The command above is easier because it also handles neighbourhood membership.
