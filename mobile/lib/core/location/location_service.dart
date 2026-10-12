import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Outcome of asking for location access, so the UI can explain what to do
/// next rather than silently failing.
enum LocationPermissionState {
  granted,
  grantedWhileInUse,
  denied,
  deniedForever,
  servicesDisabled,
}

extension LocationPermissionStateX on LocationPermissionState {
  bool get isUsable =>
      this == LocationPermissionState.granted ||
      this == LocationPermissionState.grantedWhileInUse;

  String get message => switch (this) {
        LocationPermissionState.granted =>
          'Location access granted, including in the background.',
        LocationPermissionState.grantedWhileInUse =>
          'Location works while the app is open. Allow "all the time" for '
              'alarms when the app is closed.',
        LocationPermissionState.denied =>
          'Location permission was declined. Alarms will fall back to your '
              'registered neighbourhood.',
        LocationPermissionState.deniedForever =>
          'Location is blocked for this app. Enable it in system settings to '
              'get alarms for incidents near you.',
        LocationPermissionState.servicesDisabled =>
          'Location services are switched off on this device.',
      };
}

/// Wraps geolocator, and caches the last known position where **both**
/// isolates can read it — the background poller needs a position but must not
/// wait on a GPS fix while the phone is asleep.
class LocationService {
  LocationService();

  static const _latKey = 'nhw.location.lat';
  static const _lonKey = 'nhw.location.lon';
  static const _atKey = 'nhw.location.at';

  Future<LocationPermissionState> checkPermission() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      return LocationPermissionState.servicesDisabled;
    }
    return _map(await Geolocator.checkPermission());
  }

  /// Requests permission, showing the OS prompt. Call this only after the user
  /// has seen an in-app rationale — iOS gives you exactly one chance.
  Future<LocationPermissionState> requestPermission() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      return LocationPermissionState.servicesDisabled;
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    return _map(permission);
  }

  Future<void> openSystemSettings() => Geolocator.openAppSettings();

  Future<void> openLocationSettings() => Geolocator.openLocationSettings();

  /// Best-effort current position, falling back to the cached one.
  ///
  /// [accuracy] defaults to medium: the alarm compares against a radius
  /// measured in kilometres, so metre-level GPS is a waste of battery.
  Future<Position?> currentPosition({
    LocationAccuracy accuracy = LocationAccuracy.medium,
    Duration timeout = const Duration(seconds: 12),
  }) async {
    try {
      final state = await checkPermission();
      if (!state.isUsable) return await lastKnown();

      final position = await Geolocator.getCurrentPosition(
        locationSettings: LocationSettings(accuracy: accuracy, timeLimit: timeout),
      );
      await cachePosition(position.latitude, position.longitude);
      return position;
    } catch (error) {
      debugPrint('LocationService: current position failed — $error');
      return lastKnown();
    }
  }

  /// A position stream for the map and for SOS pings.
  Stream<Position> positionStream({
    LocationAccuracy accuracy = LocationAccuracy.high,
    int distanceFilterMetres = 25,
  }) {
    return Geolocator.getPositionStream(
      locationSettings: LocationSettings(
        accuracy: accuracy,
        distanceFilter: distanceFilterMetres,
      ),
    ).map((position) {
      unawaited(cachePosition(position.latitude, position.longitude));
      return position;
    });
  }

  // ── Cross-isolate cache ───────────────────────────────────────────────────

  Future<void> cachePosition(double latitude, double longitude) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_latKey, latitude);
    await prefs.setDouble(_lonKey, longitude);
    await prefs.setString(_atKey, DateTime.now().toIso8601String());
  }

  /// Cached coordinates, or null if we have never had a fix.
  Future<({double latitude, double longitude, DateTime? at})?> cachedPosition() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.reload();
    final lat = prefs.getDouble(_latKey);
    final lon = prefs.getDouble(_lonKey);
    if (lat == null || lon == null) return null;
    return (
      latitude: lat,
      longitude: lon,
      at: DateTime.tryParse(prefs.getString(_atKey) ?? ''),
    );
  }

  Future<Position?> lastKnown() async {
    try {
      return await Geolocator.getLastKnownPosition();
    } catch (_) {
      return null;
    }
  }

  static LocationPermissionState _map(LocationPermission permission) {
    return switch (permission) {
      LocationPermission.always => LocationPermissionState.granted,
      LocationPermission.whileInUse => LocationPermissionState.grantedWhileInUse,
      LocationPermission.deniedForever => LocationPermissionState.deniedForever,
      _ => LocationPermissionState.denied,
    };
  }
}
