import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../app/router.dart';
import '../../core/theme/app_theme.dart';

export '../alerts/ui/alerts_tab.dart' show AlertsTab;
export '../incidents/ui/feed_tab.dart' show FeedTab;
export '../map/ui/map_tab.dart' show MapTab;

/// Bottom-navigation scaffold, plus two app-wide responsibilities:
///
///  * watching for a fired alarm and throwing the full-screen alarm over
///    whatever the user was doing;
///  * re-checking on resume for an alarm raised while the app was closed.
class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell>
    with WidgetsBindingObserver {
  bool _showingAlarm = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _checkPendingAlarm());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) return;

    // The background isolate may have alarmed while we were away, and its
    // writes are invisible to our in-memory state until we re-read.
    _checkPendingAlarm();
    ref.read(alarmEngineProvider).startForegroundPolling();
    ref.read(alarmHistoryRefreshProvider.notifier).bump();
  }

  Future<void> _checkPendingAlarm() async {
    if (_showingAlarm) return;

    final incident = await ref.read(alarmEngineProvider).takePendingAlarm();
    if (incident == null || !mounted) return;

    _openAlarm(incident.id);
  }

  void _openAlarm(String incidentId) {
    if (_showingAlarm) return;
    _showingAlarm = true;
    context.push('${Routes.alarm}/$incidentId').then((_) {
      _showingAlarm = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    // An alarm firing while the app is open goes straight to the alarm screen.
    ref.listen(activeAlarmProvider, (previous, next) {
      final alarm = next.value;
      if (alarm != null) _openAlarm(alarm.incident.id);
    });

    final location = GoRouterState.of(context).matchedLocation;
    final index = _indexFor(location);

    return Scaffold(
      body: widget.child,
      floatingActionButton: index == 0 || index == 1
          ? FloatingActionButton.extended(
              onPressed: () => context.push(Routes.report),
              backgroundColor: AppColors.primary500,
              foregroundColor: AppColors.ink950,
              icon: const Icon(Icons.add_alert_outlined),
              label: const Text('Report'),
            )
          : null,
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => context.go(_routeFor(value)),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.list_alt_outlined),
            selectedIcon: Icon(Icons.list_alt_rounded),
            label: 'Feed',
          ),
          NavigationDestination(
            icon: Icon(Icons.map_outlined),
            selectedIcon: Icon(Icons.map_rounded),
            label: 'Map',
          ),
          NavigationDestination(
            icon: Icon(Icons.notifications_outlined),
            selectedIcon: Icon(Icons.notifications_rounded),
            label: 'Alerts',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline_rounded),
            selectedIcon: Icon(Icons.person_rounded),
            label: 'Profile',
          ),
        ],
      ),
    );
  }

  static int _indexFor(String location) {
    if (location.startsWith(Routes.map)) return 1;
    if (location.startsWith(Routes.alerts)) return 2;
    if (location.startsWith(Routes.profile)) return 3;
    return 0;
  }

  static String _routeFor(int index) => switch (index) {
        1 => Routes.map,
        2 => Routes.alerts,
        3 => Routes.profile,
        _ => Routes.feed,
      };
}
