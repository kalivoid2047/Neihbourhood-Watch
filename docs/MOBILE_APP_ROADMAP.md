# Neighbourhood Watch — Flutter Mobile App Roadmap

**Status:** v2 · 2026-09-23 — Phases 0–4 built, Phase 5 backend built
**Target:** Android 8+ (API 26) and iOS 14+, Flutter 3.47 / Dart 3.13 (installed locally)
**Backend:** existing Django REST API at `/api/` (JWT via `rest_framework_simplejwt`)
**Code:** `mobile/` (app) · `docs/FIREBASE_SETUP.md` (push setup) · `mobile/README.md` (developer guide)

## Progress at a glance

| Phase | Status |
|---|---|
| 0 — Foundation | ✅ Built |
| 1 — Auth and profile | ✅ Built |
| 2 — Incidents | ✅ Built |
| 3 — Map and geolocation | ✅ Built |
| 4 — Alarm engine | ✅ Built (31 unit tests) |
| 5 — Push delivery | ✅ Backend built; app wired. Needs a Firebase project to activate |
| 6 — SOS | ⬜ Not started |
| 7 — Offline and sync | ⬜ Not started |
| 8 — Coordinator tools | ◐ Verify / status transitions built; verification queue not |
| 9 — Hardening and release | ⬜ Not started |

All three gaps listed in §2 below have been closed. The alarm works today on
polling alone; adding Firebase reduces its latency from ~15 minutes to ~1 second
when the app is backgrounded.

---

## 1. Purpose

A resident-facing companion app to the existing web dashboard. It does three things the web app cannot do well:

1. **Report incidents from the scene** — camera, GPS, offline queue.
2. **Raise SOS** — one-button panic with continuous location pings.
3. **Sound a proximity alarm** — if an incident is logged in the user's area, the phone audibly alarms, even when the app is backgrounded or the screen is locked.

The alarm is the differentiating feature and drives most of the architectural decisions below (background execution, push delivery, geofencing, audio focus).

---

## 2. What the backend already gives us

| Capability | Endpoint | Notes |
|---|---|---|
| Register / login / refresh / logout | `POST /api/auth/{register,login,refresh,logout}` | Login returns `{user, tokens:{access, refresh}}` |
| OTP verification | `POST /api/auth/{request-otp,verify-otp}` | Needed for the registration flow |
| Password reset | `POST /api/auth/{forgot-password,reset-password}` | |
| Profile | `GET/PATCH /api/users/me` | Carries `latitude`/`longitude`, `role`, `verification_status` |
| Emergency contacts | `GET/POST /api/me/emergency-contacts` | Feeds the SOS SMS fan-out |
| Incidents CRUD | `/api/incidents/` | Create fields: title, description, category, severity, lat, lon, address, occurred_at, metadata |
| **Nearby incidents** | `GET /api/incidents/nearby/?latitude=&longitude=&radius_m=` | Radius 1–50 000 m, returns `distance_m` — **this is the alarm's polling source** |
| Heatmap | `GET /api/incidents/heatmap/?neighborhood_id=\|bounds=&days=` | Map overlay |
| Media upload | `POST /api/incidents/{id}/upload_media/` | multipart, ≤100 MB, MIME-sniffed |
| Verify / assign / transition | `POST /api/incidents/{id}/{verify,assign,transition_status}` | Coordinator / block-captain roles only |
| SOS | `POST /api/sos/`, `POST /api/sos/{id}/{ping,resolve,cancel}`, `GET /api/sos/active/` | |
| Neighborhoods | `/api/neighborhoods/` | Has `centroid_*` and `alert_radius_m` (default 5 000 m) |
| Notifications | `GET /api/me/notifications/`, `POST /api/notifications/{id}/read/` | Dashboard channel already works end to end |
| Notification prefs | `GET/PATCH /api/me/notification-preferences/` | `push_enabled`, `sms_enabled`, `incident_alerts`, `sos_alerts` |
| Offline sync | `POST /api/sync/push/`, `GET /api/sync/queue/` | Batch mutation replay with per-item conflict results |

### Gaps the mobile app forced us to close — all now done

| Gap | Impact | Resolution |
|---|---|---|
| No device-token registration endpoint | The `DeviceToken` model existed but nothing wrote to it — the app could not register for push | ✅ `POST/DELETE /api/me/device-tokens` (`apps/accounts/views.py`), idempotent, reclaims tokens across users and reactivates soft-deleted rows. 8 tests |
| `PushProvider` was a stub | It checked a token row existed, then marked the notification "sent" without calling FCM — **no push ever reached a phone**, and a misconfigured server looked healthy | ✅ Real FCM HTTP v1 sender (`apps/notifications/fcm.py`), per-device delivery, automatic pruning of `UNREGISTERED` tokens, honest failure when unconfigured |
| `dispatch_incident_alert` targeted by **membership only** | Someone 200 m from an incident got nothing if registered to the adjacent neighbourhood; a member 40 km away was alarmed | ✅ Audience is now the union of neighbourhood members and residents within `alert_radius_m`, bounding-box pre-filtered then haversine-checked. Reporter excluded. 6 tests |
| Push payload had no alarm metadata | The client could not decide alarm vs. silent | ✅ Data-only payload carrying `kind`, `incident_id`, `severity`, `lat`, `lon`, `occurred_at`. The client treats it as a *hint* and re-fetches over its authenticated session, so a forged push cannot raise a siren |
| Alerts dispatched on **verify**, not on create | Critical incidents stayed silent until a coordinator acted | ✅ `INCIDENT_ALERT_ON_CREATE_SEVERITIES`, defaulting to `red`. Critical reports alert immediately and the app badges them "not verified yet"; everything else still waits for verification. Set to empty to restore the old behaviour |

Until Phase 5 lands, the alarm runs on **client-side polling of `/api/incidents/nearby/`**, which needs no backend change at all. Push then becomes the low-latency path; polling stays as the fallback and the offline-tolerant safety net.

---

## 3. Technical architecture

```
mobile/
  lib/
    main.dart
    app/             router (go_router), theme, bootstrap, DI overrides
    core/
      api/           Dio client, JWT interceptor + refresh queue, error mapping
      storage/       flutter_secure_storage (tokens), Drift DB (cache + outbox)
      location/      geolocator wrapper, permission flow, position stream
      notifications/ flutter_local_notifications, FCM handler, channels
      alarm/         AlarmEngine, rule set, siren player, full-screen intent
    features/
      auth/          login, register, OTP, forgot password
      incidents/     feed, detail, report wizard, media capture
      map/           flutter_map + markers + heatmap
      sos/           panic button, live ping loop, active-SOS banner
      alerts/        notification inbox, alarm history, acknowledge
      settings/      alarm radius, quiet hours, severity threshold, prefs
      profile/       profile, emergency contacts, neighbourhood
    shared/          widgets, formatters, result types
```

**Choices and why:**

- **State:** `flutter_riverpod` — compile-safe DI, easy to fake in tests, a good fit for the stream-heavy alarm engine.
- **Routing:** `go_router` with auth-state redirects and deep links from notifications (`nhw://incident/<id>`).
- **Network:** `dio` plus an interceptor that refreshes once on 401 and replays the original request.
- **Local DB:** `drift` (SQLite) — caches incidents for the offline map and feed, and holds the **outbox** table mirroring the backend's `/api/sync/push/` contract.
- **Maps:** `flutter_map` + OSM tiles — matches the web app's Leaflet/OSM choice, no API key, no Play Services dependency.
- **Location:** `geolocator` in the foreground; `workmanager` (Android) / BGTaskScheduler (iOS) for the background poll.
- **Push:** `firebase_messaging` with **data-only** messages, so the client decides whether to alarm (a `notification` payload would be rendered by the OS, bypassing our rules).
- **Audio:** `audioplayers` with an `AudioContext` set to alarm usage, so the siren plays over other audio and, where the OS permits, over silent mode.
- **Secure storage:** `flutter_secure_storage` (Keystore/Keychain) for the refresh token; the access token stays in memory.

---

## 4. The alarm feature in detail

### Trigger rule

An alarm fires when **all** of these hold:

1. A new incident is observed — via push or a nearby-poll — whose UUID is not in the seen/acknowledged store.
2. Its distance from the user's last known location is within the **alarm radius** (user setting, defaulting to the neighbourhood's `alert_radius_m` of 5 000 m, adjustable 250 m – 20 km), **or** it falls inside the user's primary neighbourhood.
3. Its severity meets the user's **alarm threshold** (default: `red` and `yellow` alarm audibly; `blue` and `green` post a silent notification).
4. `incident_alerts` is enabled in notification preferences.
5. It is outside **quiet hours** — with one deliberate override: `red` (Critical) always alarms, quiet hours or not, and so do neighbours' SOS alerts.

### Alarm behaviour by severity

| Severity | Sound | Screen | Vibration | Dismissal |
|---|---|---|---|---|
| `red` Critical | Looping siren, escalating volume, ignores silent mode where permitted | Full-screen intent over the lock screen | Long repeating pattern | Explicit "Acknowledge" — no swipe-away |
| `yellow` Important | 15 s alert tone | Heads-up notification | Short pattern | Swipe or tap |
| `blue` / `green` | Silent by default | Standard notification | None | Standard |

### Delivery paths (defence in depth)

1. **FCM data message** — sub-second when the device is online. Android: a high-priority data message wakes the app, whose handler raises a full-screen-intent local notification. iOS: needs the **Critical Alerts** entitlement (Apple approval — see Risks), otherwise a time-sensitive notification.
2. **Foreground poll** — while the app is open, poll `/api/incidents/nearby/` every 60 s with the current position.
3. **Background poll** — a `workmanager` periodic task (Android floor: 15 min; iOS: best-effort background refresh), catching anything push missed, deduped against the seen-incident table.

### Android specifics

- A dedicated `NotificationChannel` `nhw_alarm_critical` at `IMPORTANCE_HIGH`, custom sound, DND bypass requested.
- `USE_FULL_SCREEN_INTENT` permission — Android 14 requires a justified declaration, which the public-safety use case supports.
- A foreground service (`FOREGROUND_SERVICE_LOCATION`) while an SOS is active, so pings survive backgrounding.
- No `SCHEDULE_EXACT_ALARM`: the alarm is event-driven rather than time-driven, which keeps Play Store review simple.

### iOS specifics

- Request the Critical Alerts entitlement, justified by the public-safety use case. If denied: `interruptionLevel: .timeSensitive` plus an in-app looping siren when foregrounded, and say plainly in the UI that locked-screen audio may be limited.
- Background modes: `remote-notification`, `fetch`, and `location` (SOS only).

### Anti-annoyance guardrails

- Per-incident dedupe by UUID, persisted across restarts.
- Cooldown: at most one audible alarm per 90 s; further incidents batch into a single notification.
- "Snooze alarms for 1 h / until tomorrow", with `red` still breaking through.
- The backend already caps notifications at 20 per user per hour (`NOTIFICATION_RATE_LIMIT_MAX`).
- A "Test alarm" button in Settings, so users can verify audio before they need it.

---

## 5. Delivery phases

Effort is in developer-days for one developer; each phase is independently shippable.

### Phase 0 — Foundation (2 d)
Scaffold the `mobile/` Flutter project, flavors (dev/staging/prod) with `--dart-define` base URLs, a theme matching the web app, Riverpod + go_router wiring, lint rules, and a CI job running `flutter analyze` and `flutter test`.
**Done when:** the app builds on Android and iOS and shows a themed splash routing to login.

### Phase 1 — Auth and profile (3 d)
Login, register with the OTP step, forgot/reset password, secure token storage, silent refresh with request replay, logout with refresh-token blacklisting, profile view/edit, emergency-contacts CRUD, role-aware UI gating.
**Done when:** a resident can register, verify OTP, log in, survive an app restart, and see their profile; expired access tokens refresh transparently.

### Phase 2 — Incidents (4 d)
Incident feed with filters (category, severity, status) and pagination, detail view with media gallery, a report wizard (category → description → severity → location with map pin and reverse geocode → photo/video/audio capture → submit), media upload with progress, and a "my reports" list.
**Done when:** an incident reported on the phone appears on the web dashboard with its media attached.

### Phase 3 — Map and geolocation (3 d)
`flutter_map` with OSM tiles, severity-coloured markers, clustering, "incidents near me" via `/api/incidents/nearby/`, a heatmap overlay from `/api/incidents/heatmap/`, neighbourhood boundary polygons from `boundary_geojson`, and permission onboarding (when-in-use → always, with rationale screens).
**Done when:** the map shows the same incidents as the web Leaflet map, centred on the user.

### Phase 4 — **Alarm engine** (5 d) ← headline feature
The `AlarmEngine` service implementing §4's rules, the seen-incident store, foreground poller, `workmanager` background poller, local notification channels, the full-screen alarm screen with siren, escalation and acknowledge, alarm history, and the settings surface (radius slider, severity threshold, quiet hours, snooze, test alarm).
**Done when:** with the app killed, an incident created inside the user's radius produces an audible alarm on a physical Android device within one background-poll interval, and acknowledging it marks the notification read via `POST /api/notifications/{id}/read/`.

### Phase 5 — Push delivery + backend closure (4 d, ~2 d of it backend)
Backend: `POST/DELETE /api/me/device-tokens`, a real FCM HTTP v1 sender with token pruning, radius-based targeting in `dispatch_incident_alert`, the structured alarm payload, and create-time dispatch for `red` severity.
Mobile: Firebase config for both platforms, token registration and refresh lifecycle, background and terminated message handlers routed into `AlarmEngine`, deep links into incident detail.
**Done when:** creating a critical incident on the web dashboard alarms a nearby phone in under 5 seconds with the app terminated.

### Phase 6 — SOS (3 d)
A panic button with hold-to-activate and a 3 s cancel window, a foreground-service ping loop (`POST /api/sos/{id}/ping`), optional audio recording, a persistent active-SOS banner, resolve/cancel, and receiving neighbours' SOS alerts as always-audible alarms.
**Done when:** an SOS raised on the phone streams pings visible on the web dashboard and notifies the user's emergency contacts.

### Phase 7 — Offline and sync (3 d)
A Drift cache for incidents, neighbourhoods and notifications; an outbox for reports and media captured offline; connectivity-aware replay through `POST /api/sync/push/`; conflict surfacing from `GET /api/sync/queue/`; an offline map-tile cache for the home neighbourhood; and an offline indicator.
**Done when:** a report filed in airplane mode uploads automatically on reconnect, and a conflict is shown to the user rather than silently dropped.

### Phase 8 — Coordinator tools (2 d, optional)
Verify / assign / status-transition actions for the `block_captain`, `coordinator` and `police_officer` roles, the verification-request queue, and the neighbourhood risk summary.
**Done when:** a coordinator can verify an incident from the phone, triggering the existing alert fan-out.

### Phase 9 — Hardening and release (4 d)
Certificate pinning, a root/jailbreak advisory, a no-secrets-in-logs audit, an accessibility pass (screen reader on the alarm screen, 4.5:1 contrast), localisation scaffolding (en + af + zu), battery-drain profiling of the poller, crash reporting, store listings, a privacy policy covering background location, and Play Store data-safety plus App Store review notes for the alarm.
**Done when:** internal-track builds are live on both stores.

**Total: ~33 developer-days.** Phases 0–4 (~17 d) deliver a usable app with a working alarm on polling alone, before any backend change is required.

---

## 6. Decisions

1. **Alarm on report, or only on verified reports?** — *Implemented as proposed, and reversible.* `red` severity alerts on creation with an "unverified" badge in the app; everything else waits for a coordinator. Controlled by `INCIDENT_ALERT_ON_CREATE_SEVERITIES` (default `red`); set it empty to require verification for everything. **This remains a community-policy call** — the default is a judgement that a life-safety report should not wait on a volunteer's availability, not a technical constraint.
2. **iOS Critical Alerts** — *Still open, and Apple's to grant.* The app requests the entitlement and degrades to time-sensitive notifications if it is not granted. Someone needs to file the request: <https://developer.apple.com/contact/request/notifications-critical-alerts-entitlement/>
3. **Radius vs. neighbourhood membership** — *Resolved: the union of both*, with the radius user-adjustable in the app (250 m – 20 km) and the server-side radius taken from `Neighborhood.alert_radius_m`.
4. **Firebase** — *Adopted, as the fast path only.* The alarm's correctness never depends on it: polling is the fallback, and `PushService` fails soft when Firebase is absent. Replacing FCM with self-hosted ntfy/UnifiedPush would touch `apps/notifications/fcm.py` and `core/notifications/push_service.dart` and nothing else.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| Aggressive OEM battery management (Xiaomi, Huawei, Samsung) kills background pollers | High-priority FCM data messages as the primary path; an in-app prompt to whitelist the app; honest UI copy about background limits |
| iOS background execution is not guaranteed | Push-first design, a foreground poller while open, clear user messaging |
| Alarm fatigue in a busy neighbourhood | Severity thresholds, cooldown, snooze, per-category mutes, the existing backend rate limit |
| False or malicious reports triggering mass alarms | Verify-gating for non-critical severities, reporter reputation (future), the audit log already in place |
| Battery drain from location polling | Coarse location for the poller, a distance filter, adaptive intervals, a foreground service only during SOS |
| Store rejection over full-screen intent or background location | Documented public-safety justification; both are declared, in-scope uses |

---

## 8. Testing strategy

- **Unit:** the alarm rule matrix (distance × severity × quiet hours × snooze × dedupe), token refresh, outbox replay, conflict handling.
- **Widget:** report-wizard validation, alarm screen states, offline banners.
- **Integration:** mocked Dio against recorded API fixtures; Drift migrations.
- **Manual device matrix:** one low-end Android (Go edition), one recent Android, one iPhone — with the alarm verified foregrounded, backgrounded, terminated, screen-locked, and with DND on.
