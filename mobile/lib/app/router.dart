import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/alarm/ui/alarm_history_screen.dart';
import '../features/alarm/ui/alarm_screen.dart';
import '../features/alarm/ui/alarm_settings_screen.dart';
import '../features/auth/ui/forgot_password_screen.dart';
import '../features/auth/ui/login_screen.dart';
import '../features/auth/ui/otp_screen.dart';
import '../features/auth/ui/register_screen.dart';
import '../features/auth/ui/splash_screen.dart';
import '../features/incidents/ui/incident_detail_screen.dart';
import '../features/incidents/ui/report_incident_screen.dart';
import '../features/profile/ui/emergency_contacts_screen.dart';
import '../features/profile/ui/profile_screen.dart';
import '../features/shell/home_shell.dart';
import 'providers.dart';

class Routes {
  const Routes._();

  static const splash = '/';
  static const login = '/login';
  static const register = '/register';
  static const otp = '/otp';
  static const forgotPassword = '/forgot-password';

  static const feed = '/feed';
  static const map = '/map';
  static const alerts = '/alerts';
  static const profile = '/profile';

  static const report = '/report';
  static const incident = '/incident';
  static const alarm = '/alarm';
  static const alarmSettings = '/settings/alarm';
  static const alarmHistory = '/alerts/history';
  static const emergencyContacts = '/profile/emergency-contacts';

  static String incidentDetail(String id) => '$incident/$id';
}

/// Rebuilds the router's redirect logic whenever auth state changes.
final routerProvider = Provider<GoRouter>((ref) {
  final navigatorKey = GlobalKey<NavigatorState>();

  return GoRouter(
    navigatorKey: navigatorKey,
    initialLocation: Routes.splash,
    debugLogDiagnostics: false,
    refreshListenable: _AuthListenable(ref),
    redirect: (context, state) {
      final auth = ref.read(authControllerProvider);
      final location = state.matchedLocation;

      const publicRoutes = {
        Routes.login,
        Routes.register,
        Routes.otp,
        Routes.forgotPassword,
      };

      // Session restoration in flight — hold on the splash.
      if (auth is AuthUnknown) {
        return location == Routes.splash ? null : Routes.splash;
      }

      if (auth is AuthSignedOut) {
        return publicRoutes.contains(location) ? null : Routes.login;
      }

      // Signed in: bounce away from the splash and the auth screens.
      if (location == Routes.splash || publicRoutes.contains(location)) {
        return Routes.feed;
      }
      return null;
    },
    routes: [
      GoRoute(
        path: Routes.splash,
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(
        path: Routes.login,
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: Routes.register,
        builder: (context, state) => const RegisterScreen(),
      ),
      GoRoute(
        path: Routes.otp,
        builder: (context, state) {
          final extra = state.extra as Map<String, dynamic>? ?? const {};
          return OtpScreen(
            email: extra['email'] as String? ?? '',
            purpose: extra['purpose'] as String? ?? 'registration',
          );
        },
      ),
      GoRoute(
        path: Routes.forgotPassword,
        builder: (context, state) => const ForgotPasswordScreen(),
      ),

      // The bottom-navigation shell.
      ShellRoute(
        builder: (context, state, child) => HomeShell(child: child),
        routes: [
          GoRoute(
            path: Routes.feed,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: FeedTab(),
            ),
          ),
          GoRoute(
            path: Routes.map,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: MapTab(),
            ),
          ),
          GoRoute(
            path: Routes.alerts,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: AlertsTab(),
            ),
          ),
          GoRoute(
            path: Routes.profile,
            pageBuilder: (context, state) => const NoTransitionPage(
              child: ProfileScreen(),
            ),
          ),
        ],
      ),

      GoRoute(
        path: Routes.report,
        builder: (context, state) => const ReportIncidentScreen(),
      ),
      GoRoute(
        path: '${Routes.incident}/:id',
        builder: (context, state) => IncidentDetailScreen(
          incidentId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '${Routes.alarm}/:id',
        builder: (context, state) => AlarmScreen(
          incidentId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: Routes.alarmSettings,
        builder: (context, state) => const AlarmSettingsScreen(),
      ),
      GoRoute(
        path: Routes.alarmHistory,
        builder: (context, state) => const AlarmHistoryScreen(),
      ),
      GoRoute(
        path: Routes.emergencyContacts,
        builder: (context, state) => const EmergencyContactsScreen(),
      ),
    ],
  );
});

/// Bridges Riverpod's auth state onto go_router's [Listenable] refresh hook.
class _AuthListenable extends ChangeNotifier {
  _AuthListenable(Ref ref) {
    ref.listen(authControllerProvider, (_, _) => notifyListeners());
  }
}
