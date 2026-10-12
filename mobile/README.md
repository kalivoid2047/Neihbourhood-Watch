# Neighbourhood Watch — mobile app

Flutter client for the Neighbourhood Watch platform. Companion to the Django API in `../backend` and the React dashboard in `../frontend`.

Three things it does that the web dashboard cannot:

1. **Report from the scene** — camera, GPS, map pin.
2. **Raise SOS** — panic button with live location (Phase 6, not yet built).
3. **Sound a proximity alarm** — if an incident is reported in your area, the phone alarms, even backgrounded or locked.

## Running it

```bash
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

`10.0.2.2` is how the Android emulator reaches `localhost` on the host machine. On a physical device, use your machine's LAN address (`http://192.168.1.50:8000`) and make sure Django is listening on it:

```bash
python manage.py runserver 0.0.0.0:8000
```

Add that address to `DJANGO_ALLOWED_HOSTS` in the backend `.env` or requests will be rejected with a 400.

### Build-time configuration

| Define | Default | Purpose |
|---|---|---|
| `API_BASE_URL` | `http://10.0.2.2:8000` | Backend origin, no trailing slash |
| `ENVIRONMENT` | `dev` | Shown in Settings, used for crash-report tagging |
| `PUSH_ENABLED` | `true` | Set `false` to build without Firebase; alarms fall back to polling |

```bash
flutter run \
  --dart-define=API_BASE_URL=https://api.example.co.za \
  --dart-define=ENVIRONMENT=prod
```

### Checks

```bash
flutter analyze   # must be clean
flutter test      # alarm rule matrix, 31 tests
```

## How the alarm works

The design assumption is that **any single delivery path will fail**, so there are three, all funnelling into the same rule engine and deduplicated by incident UUID:

| Path | Latency | Requires |
|---|---|---|
| FCM push | ~1 s | Firebase configured (see `../docs/FIREBASE_SETUP.md`) |
| Foreground poll | ≤ 60 s | App open |
| Background poll | ~15 min | Nothing — Android's floor for periodic work |

Each observed incident goes through `AlarmRules.evaluate()`, which returns one of **alarm** (siren + full-screen), **notifySilently** (tray notification), or **ignore**. It fires the siren only when *all* of these hold:

1. Not seen before.
2. Alarms enabled.
3. Within the user's radius (default 5 km, adjustable 250 m – 20 km), **or** in their neighbourhood.
4. Reported within the last 6 hours.
5. Category not muted.
6. Severity at or above the user's threshold (default: Important).
7. Not in quiet hours, not snoozed, not inside the 90-second cooldown.

Rules 6 and 7 downgrade to a silent notification rather than dropping the incident, so nothing is lost — it just does not make noise. **`red` (Critical) incidents override quiet hours and snooze**, which is the single most important line in the file: a safety app that can be silenced through a genuine emergency is not a safety app.

`AlarmRules` is a pure function — no clock of its own, no I/O, no plugins. Everything it needs is passed in, which is why the whole matrix is unit-testable without a device. Anything you change in the alarm's behaviour belongs there, with a test.

### Layout

```
lib/
  app/           router, providers (dependency graph)
  core/          api client, storage, location, notifications, push, theme
  features/
    alarm/       ← the feature; rules, engine, store, audio, background poller
    auth/        login, register, OTP, password reset
    incidents/   feed, detail, report wizard
    map/         flutter_map + OSM tiles, alarm radius, heatmap
    alerts/      alert inbox and alarm history
    profile/     profile, emergency contacts
    shell/       bottom navigation, alarm interception
  shared/        common widgets and formatters
```

### Two isolates, one source of truth

The background poller runs in a **separate isolate** with no access to the widget tree or the provider graph. It rebuilds what it needs from disk: secure storage for the refresh token, `SharedPreferences` for alarm settings and the seen-incident set. That is why `AlarmStore` is built on `SharedPreferences` rather than in-memory state, and why `HomeShell` calls `reload()` when the app resumes — the background isolate writes behind the UI's back.

An alarm raised while the app is closed parks its incident id as a "pending alarm"; the UI picks it up on resume or when the notification is tapped.

## Permissions

| Permission | Why | Without it |
|---|---|---|
| Location (while in use) | Distance from incidents; reporting | Falls back to your registered neighbourhood |
| Location (always) | Background alarm checks | Alarms only while the app is open |
| Notifications | All alerts | No alarms at all |
| Full-screen intent (Android 14+) | Lights up a locked phone | Heads-up notification only; still audible |
| Camera / microphone | Evidence | Reports without attachments |

Each is requested at the point of use, after an in-app explanation. iOS gives you exactly one chance at the OS prompt, so never trigger it cold.

## Troubleshooting the first build

The first `flutter build apk` downloads the Android Gradle Plugin, the Android
SDK tooling and the Firebase libraries — several hundred megabytes. On a slow or
unreliable connection this fails in a **misleading** way:

```
Could not download sdk-common-31.11.1.jar ... Read timed out
> 'kotlin-android' plugin requires one of the Android Gradle plugins.
```

That second error looks like a Gradle misconfiguration. It is not — it is a
cascade from the first. The real failure is always the `Read timed out` line
further up.

`android/gradle.properties` raises Gradle's network timeouts to three minutes
each for this reason. If it still fails, **just run it again**: Gradle keeps
whatever it already downloaded, so each attempt gets further than the last.

## Known gaps

Phases 0–4 of `../docs/MOBILE_APP_ROADMAP.md` are built. Not yet:

- **SOS** (Phase 6) — the backend endpoints exist and are documented; the UI is not built.
- **Offline queue** (Phase 7) — reports currently require connectivity. The backend's `/api/sync/push/` contract is ready for it.
- **Coordinator tools** (Phase 8) — verify and status transitions are wired on the incident detail screen; the verification-request queue is not.
- **iOS Critical Alerts** — needs Apple's entitlement; see the Firebase guide.
- **Tests** cover the alarm rules thoroughly and nothing else. Widget and integration tests are Phase 9 work.

## Replacing the siren

`assets/audio/alarm_siren.wav` is a generated 4-second two-tone wail that loops seamlessly. To change it, replace **both**:

- `assets/audio/alarm_siren.wav` — what the app plays
- `android/app/src/main/res/raw/alarm_siren.wav` — what the notification channel plays

Android caches notification-channel sounds at channel creation. After changing the raw resource, uninstall and reinstall the app, or the old sound persists.
