import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../app/router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets.dart';
import '../../incidents/data/incident.dart';

/// The full-screen alarm.
///
/// Design rules, in priority order:
///  1. Legible in one glance, at arm's length, in the dark, half asleep.
///  2. Impossible to dismiss by accident — no back button, no swipe, one
///     deliberate button.
///  3. Says *what* and *how far*, because that is what decides what you do next.
class AlarmScreen extends ConsumerStatefulWidget {
  const AlarmScreen({super.key, required this.incidentId});

  final String incidentId;

  @override
  ConsumerState<AlarmScreen> createState() => _AlarmScreenState();
}

class _AlarmScreenState extends ConsumerState<AlarmScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse;
  Timer? _elapsedTimer;
  Duration _elapsed = Duration.zero;

  @override
  void initState() {
    super.initState();

    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);

    _elapsedTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _elapsed += const Duration(seconds: 1));
    });

    // Keep the screen awake and bright while an alarm is up.
    unawaited(SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky));

    // The engine hands the siren to the UI when the UI is present, so start it
    // here and stop it on acknowledge.
    unawaited(ref.read(alarmEngineProvider).startSiren());
  }

  @override
  void dispose() {
    _elapsedTimer?.cancel();
    _pulse.dispose();
    unawaited(SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge));
    // Belt and braces: never leave the siren running behind a closed screen.
    unawaited(ref.read(alarmEngineProvider).stopSiren());
    super.dispose();
  }

  Future<void> _acknowledge({bool openDetails = false}) async {
    await ref.read(alarmEngineProvider).acknowledge(widget.incidentId);
    ref.read(alarmHistoryRefreshProvider.notifier).bump();

    if (!mounted) return;

    if (openDetails) {
      context.pushReplacement(Routes.incidentDetail(widget.incidentId));
    } else if (context.canPop()) {
      context.pop();
    } else {
      context.go(Routes.feed);
    }
  }

  @override
  Widget build(BuildContext context) {
    final incidentAsync = ref.watch(incidentDetailProvider(widget.incidentId));

    return PopScope(
      // The whole point of an alarm is that you have to deal with it.
      canPop: false,
      child: Scaffold(
        backgroundColor: AppColors.ink950,
        body: SafeArea(
          child: incidentAsync.when(
            loading: () => const LoadingState(message: 'Loading alert…'),
            error: (error, _) => _UnknownIncidentBody(
              onAcknowledge: () => _acknowledge(),
            ),
            data: (incident) => _AlarmBody(
              incident: incident,
              elapsed: _elapsed,
              pulse: _pulse,
              onAcknowledge: () => _acknowledge(),
              onViewDetails: () => _acknowledge(openDetails: true),
            ),
          ),
        ),
      ),
    );
  }
}

class _AlarmBody extends StatelessWidget {
  const _AlarmBody({
    required this.incident,
    required this.elapsed,
    required this.pulse,
    required this.onAcknowledge,
    required this.onViewDetails,
  });

  final Incident incident;
  final Duration elapsed;
  final AnimationController pulse;
  final VoidCallback onAcknowledge;
  final VoidCallback onViewDetails;

  @override
  Widget build(BuildContext context) {
    final colour = incident.severity.color;

    return AnimatedBuilder(
      animation: pulse,
      builder: (context, child) {
        return DecoratedBox(
          decoration: BoxDecoration(
            gradient: RadialGradient(
              center: Alignment.topCenter,
              radius: 1.4,
              colors: [
                colour.withValues(alpha: 0.10 + pulse.value * 0.22),
                AppColors.ink950,
              ],
            ),
          ),
          child: child,
        );
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
        child: Column(
          children: [
            const Spacer(flex: 1),

            // Pulsing severity badge.
            AnimatedBuilder(
              animation: pulse,
              builder: (context, _) => Transform.scale(
                scale: 1 + pulse.value * 0.12,
                child: Container(
                  width: 128,
                  height: 128,
                  decoration: BoxDecoration(
                    color: colour.withValues(alpha: 0.18),
                    shape: BoxShape.circle,
                    border: Border.all(color: colour, width: 3),
                    boxShadow: [
                      BoxShadow(
                        color: colour.withValues(alpha: 0.4 * pulse.value),
                        blurRadius: 40,
                        spreadRadius: 8,
                      ),
                    ],
                  ),
                  child: Icon(
                    incident.severity == IncidentSeverity.red
                        ? Icons.warning_amber_rounded
                        : incident.category.icon,
                    size: 64,
                    color: colour,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 28),

            Text(
              incident.severity == IncidentSeverity.red
                  ? 'CRITICAL ALERT'
                  : 'INCIDENT NEARBY',
              style: TextStyle(
                color: colour,
                fontSize: 15,
                fontWeight: FontWeight.w800,
                letterSpacing: 2.4,
              ),
            ),
            const SizedBox(height: 14),

            Text(
              incident.title,
              textAlign: TextAlign.center,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 30,
                fontWeight: FontWeight.w700,
                height: 1.2,
              ),
            ),
            const SizedBox(height: 18),

            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                TagChip(
                  label: incident.category.label,
                  color: Colors.white70,
                  icon: incident.category.icon,
                ),
                if (incident.distanceLabel != null)
                  TagChip(
                    label: '${incident.distanceLabel} away',
                    color: colour,
                    icon: Icons.near_me_rounded,
                  ),
                TagChip(
                  label: formatRelative(incident.occurredAt),
                  color: Colors.white70,
                  icon: Icons.schedule_rounded,
                ),
              ],
            ),

            if (incident.address.isNotEmpty) ...[
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.place_outlined, size: 16, color: Colors.white60),
                  const SizedBox(width: 6),
                  Flexible(
                    child: Text(
                      incident.address,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white70, fontSize: 15),
                    ),
                  ),
                ],
              ),
            ],

            if (!incident.isVerified) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: AppColors.warning400.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: AppColors.warning400.withValues(alpha: 0.4),
                  ),
                ),
                child: const Text(
                  'Reported by a resident — not yet verified by a coordinator.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.warning400, fontSize: 13),
                ),
              ),
            ],

            const Spacer(flex: 2),

            Text(
              'Alarm sounding for ${_formatElapsed(elapsed)}',
              style: const TextStyle(color: Colors.white38, fontSize: 13),
            ),
            const SizedBox(height: 12),

            FilledButton(
              onPressed: onAcknowledge,
              style: FilledButton.styleFrom(
                backgroundColor: Colors.white,
                foregroundColor: AppColors.ink950,
                minimumSize: const Size.fromHeight(62),
                textStyle: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              child: const Text('I am safe — silence alarm'),
            ),
            const SizedBox(height: 10),

            OutlinedButton(
              onPressed: onViewDetails,
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white,
                side: const BorderSide(color: Colors.white24),
                minimumSize: const Size.fromHeight(52),
              ),
              child: const Text('See what happened'),
            ),
          ],
        ),
      ),
    );
  }

  static String _formatElapsed(Duration elapsed) {
    final minutes = elapsed.inMinutes;
    final seconds = elapsed.inSeconds % 60;
    return minutes > 0 ? '${minutes}m ${seconds}s' : '${seconds}s';
  }
}

/// Fallback when the incident behind an alarm cannot be loaded — offline, or
/// it was deleted. The alarm still has to be silenceable.
class _UnknownIncidentBody extends StatelessWidget {
  const _UnknownIncidentBody({required this.onAcknowledge});

  final VoidCallback onAcknowledge;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.warning_amber_rounded,
            size: 84,
            color: AppColors.danger500,
          ),
          const SizedBox(height: 20),
          const Text(
            'Incident alert',
            style: TextStyle(
              color: Colors.white,
              fontSize: 26,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            'An incident was reported near you, but the details could not be '
            'loaded. Check the feed once you are back online.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.white70, height: 1.4),
          ),
          const SizedBox(height: 36),
          FilledButton(
            onPressed: onAcknowledge,
            style: FilledButton.styleFrom(
              backgroundColor: Colors.white,
              foregroundColor: AppColors.ink950,
              minimumSize: const Size.fromHeight(60),
            ),
            child: const Text('Silence alarm'),
          ),
        ],
      ),
    );
  }
}
