# Firebase Cloud Messaging — setup guide

**Who this is for:** someone setting up push notifications for the Neighbourhood Watch mobile app for the first time. No prior Firebase experience assumed.

---

## What Firebase is doing here (and what it is not)

Firebase Cloud Messaging (FCM) is a **message-delivery service**. Its one job is to wake a phone that is asleep and hand it a small message. That is all we use it for.

It is **not** a database, and it does not replace anything in this project:

| Concern | Handled by | Not by |
|---|---|---|
| Storing incidents, users, neighbourhoods | Your Django database (PostgreSQL / SQLite) | Firebase |
| Deciding who gets alerted | `NotificationDispatchService` in `backend/apps/notifications/services.py` | Firebase |
| Deciding whether the phone makes a noise | `AlarmRules` in `mobile/lib/features/alarm/data/alarm_rules.dart` | Firebase |
| Waking a sleeping phone within a second | FCM | — |

**The app works without any of this.** With no Firebase configuration at all, the alarm still runs on polling: every 60 seconds while the app is open, and roughly every 15 minutes while it is closed. Firebase closes that 15-minute gap down to about a second. That is the whole benefit, and it is a real one for a safety app — but a failed Firebase setup degrades latency rather than breaking alarms.

Messages we send are **data-only**, which means the OS does not display them itself. The app receives the data, applies the user's alarm rules (radius, severity, quiet hours), and only then decides whether to sound a siren. That is deliberate: it stops a push from bypassing a user's settings.

---

## Part 1 — Create the Firebase project

1. Go to <https://console.firebase.google.com> and sign in with a Google account. Use an account the organisation controls, not a personal one — whoever owns this account controls push for the app.
2. Click **Create a project**.
3. Name it something like `neighbourhood-watch`. Note the **project ID** it generates underneath (for example `neighbourhood-watch-4a1c7`) — you will need it later, and it is not always the same as the name.
4. Google Analytics is optional and not used by this app. Declining is fine.
5. Wait for provisioning, then click **Continue**.

---

## Part 2 — Register the Android app

1. In the project, click the **Android** icon (or **Add app → Android**).
2. **Android package name** — this must match exactly, or push will silently never arrive:

   ```
   za.co.neighbourhoodwatch.nhw_mobile
   ```

   Confirm it against `mobile/android/app/build.gradle.kts` (`applicationId`) if you ever change it.
3. App nickname and debug signing certificate can be left blank for now. (The SHA-1 is only needed for Google Sign-In and Dynamic Links, neither of which this app uses.)
4. Click **Register app**, then **Download `google-services.json`**.
5. Put that file at exactly:

   ```
   mobile/android/app/google-services.json
   ```

6. Skip the SDK instructions Firebase shows you — the Gradle wiring in Part 4 covers it.

> **Do not commit `google-services.json` to a public repository.** It is not a secret in the password sense, but it identifies your project and invites abuse. `mobile/.gitignore` already excludes it.

---

## Part 3 — Register the iOS app (skip if Android-only for now)

1. **Add app → iOS**.
2. **Bundle ID**: `za.co.neighbourhoodwatch.nhwMobile` — check it against Xcode (`Runner → General → Bundle Identifier`), as Flutter's iOS bundle id does not always match the Android package name.
3. Download **`GoogleService-Info.plist`**.
4. Open `mobile/ios/Runner.xcworkspace` in Xcode and drag the file into the `Runner` folder, ticking **Copy items if needed** and the **Runner** target. Dropping it into the folder on disk without adding it to the Xcode target is the single commonest iOS push mistake — the file must appear in **Build Phases → Copy Bundle Resources**.
5. Push on iOS additionally requires an **APNs key** from the Apple Developer portal:
   - Apple Developer → **Certificates, Identifiers & Profiles → Keys → +**
   - Enable **Apple Push Notifications service (APNs)**, create it, download the `.p8` file (**you can only download it once**).
   - In Firebase: **Project settings → Cloud Messaging → APNs Authentication Key → Upload**, providing the `.p8`, its **Key ID**, and your **Team ID**.
6. While in Xcode, add these capabilities to the Runner target (**Signing & Capabilities → + Capability**):
   - **Push Notifications**
   - **Background Modes** → tick *Remote notifications* and *Background fetch*
7. Also drag `mobile/assets/audio/alarm_siren.wav` into the Runner target, so iOS can play it as a notification sound. iOS plays sounds from the app bundle, not from Flutter assets.

### About iOS Critical Alerts

A normal iOS notification will **not** play a sound when the phone is in silent mode or Do Not Disturb. For a genuine emergency alarm you need Apple's **Critical Alerts** entitlement, which must be requested and approved:

<https://developer.apple.com/contact/request/notifications-critical-alerts-entitlement/>

Justify it with the public-safety use case. If it is declined, the app falls back to time-sensitive notifications automatically — no code change needed — but be honest with users that a locked, silenced iPhone may not make a noise.

---

## Part 4 — The Android Gradle plugin (already wired up)

Flutter does not add this for you, so it has been done already:

- `mobile/android/settings.gradle.kts` declares `com.google.gms.google-services` version 4.4.2.
- `mobile/android/app/build.gradle.kts` applies it **only when `google-services.json` exists**.

That condition is deliberate. Applying the plugin unconditionally fails the build with *"File google-services.json is missing"* on any machine without Firebase set up, which would make push a hard dependency of a feature designed to work without it. Instead, the build prints which mode it is in:

```
Firebase: no google-services.json — building without push.
Firebase: google-services.json found — push enabled.
```

So once you drop the file into `mobile/android/app/`, just rebuild:

```bash
cd mobile && flutter build apk --debug
```

Watch for the "push enabled" line. If you still see "building without push", the file is in the wrong directory — it belongs in `android/app/`, not `android/`.

---

## Part 5 — Give the backend a service-account key

The Django server needs permission to ask FCM to deliver messages.

1. Firebase console → gear icon → **Project settings → Service accounts**.
2. Click **Generate new private key**, then confirm. A JSON file downloads.
3. **This file is a credential.** Anyone holding it can send push notifications to every user of your app. Store it the way you store database passwords: never in git, never in a chat message, readable only by the service user.
4. Put it somewhere the Django process can read, for example `/etc/nhw/fcm-service-account.json` with `chmod 600`.
5. Install the two Python libraries the sender needs. They are already pinned in `requirements/base.txt`:

   ```bash
   pip install -r requirements/base.txt
   ```

6. Set three variables:

   ```
   FCM_ENABLED=true
   FCM_PROJECT_ID=neighbourhood-watch-4a1c7
   FCM_CREDENTIALS_FILE=/etc/nhw/fcm-service-account.json
   ```

   `FCM_PROJECT_ID` is the **project ID** from Part 1 — visible any time under **Project settings → General**.

### ⚠️ Where those variables actually have to go

**This project does not read `.env` when you run `manage.py` directly.** `config/settings/base.py` calls `os.getenv()`, and nothing loads the file. `.env` reaches the app only through `docker-compose.yml`, which passes it with `env_file:`.

So it depends on how you run the server:

| How you run it | What to do |
|---|---|
| `docker compose up` | Put them in `.env`. Already wired via `env_file:` — nothing more to do |
| `python manage.py runserver` on Windows | Set them in the shell first (below), or they are silently ignored |
| Production (systemd, Heroku, Kubernetes) | Set them the way that platform sets environment variables — `k8s/configmap.yaml` for the Kubernetes manifests here |

For a local Windows run, in the same PowerShell session:

```powershell
$env:FCM_ENABLED = "true"
$env:FCM_PROJECT_ID = "neighbourhood-watch-4a1c7"
$env:FCM_CREDENTIALS_FILE = "C:\secure\fcm-service-account.json"
python backend\manage.py runserver
```

These last only for that terminal window. If push works in one terminal and not another, this is why.

---

## Part 6 — Check that it works

There is a command that checks every link in the chain and tells you which one is broken:

```bash
cd backend && python manage.py check_push
```

It reports each setting separately, actually authenticates against Google (a well-formed key for the wrong project passes every other check and still fails here), and lists the devices that have registered. Run it after each part below.

**1. The backend thinks FCM is configured.** `check_push` should show four ticks and "Authenticated with Google successfully".

A cross on `FCM_PROJECT_ID` or `FCM_CREDENTIALS_FILE` when you *have* set them in `.env` almost always means the variables are not reaching the process — see the warning in Part 5.

**2. The phone registers a token.** Sign in on the device, then run `check_push` again. It should now list an active Android or iOS device.

"No active device tokens" means the app never reached `POST /api/me/device-tokens`. Check the device log for lines starting `PushService:` — the app prints the reason it gave up and carries on polling.

**3. A test push reaches the phone.**

```bash
cd backend && python manage.py check_push --send-to you@example.com
```

"Accepted by FCM" means Google took the message, not that the phone displayed it. The test push carries `kind=test`, so the app logs it and deliberately does **not** sound a siren.

**4. An alarm actually arrives.** Create a `red`-severity incident on the web dashboard, near the test device's registered coordinates. With the app **fully closed**, the phone should alarm within a few seconds.

If it does not, walk down this list:

| Symptom | Likely cause |
|---|---|
| No token row at all | App cannot reach the backend, or the user is not signed in |
| Token exists, nothing arrives | Package name mismatch between Firebase and the app |
| `Notification.status == 'failed'`, error `FCM is not configured` | Backend env vars (Part 5) |
| Error `UNREGISTERED` | Stale token; the app reinstalled. The backend deactivates these automatically |
| Arrives but silent | User's alarm settings — check severity threshold, radius, quiet hours, snooze in the app's Alarm settings screen |
| Works in debug, not in release | Android: missing the Gradle plugin (Part 4). iOS: missing APNs key |
| Android: arrives late, only when the screen wakes | OEM battery optimisation. Whitelist the app in the phone's battery settings |

**5. Confirm the fallback still works.** Turn `FCM_ENABLED=false`, restart the server, create an incident and wait. The phone should still alarm on its next poll. If it does not, the problem is in the alarm engine, not in Firebase.

---

## Costs

FCM is free with no message quota for this kind of use. The service-account key and the Firebase project cost nothing. You are not enabling any billable Google Cloud service by following this guide.

---

## What to do if you would rather not use Google

The app is built so push is optional. Two alternatives, in order of effort:

- **Do nothing.** Leave `FCM_ENABLED=false`. Alarms work on polling alone, up to ~15 minutes late when the app is backgrounded. For many neighbourhoods this is genuinely acceptable.
- **Self-host with [ntfy](https://ntfy.sh) / UnifiedPush.** Android-only, but no Google dependency and it runs on your own server. It would replace `apps/notifications/fcm.py` and the `PushService` class in the app; the alarm rules and everything else stay untouched — which is exactly why that seam exists.
