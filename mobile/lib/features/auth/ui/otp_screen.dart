import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../app/router.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';

/// One-time code entry, used after registration and for login challenges.
class OtpScreen extends ConsumerStatefulWidget {
  const OtpScreen({super.key, required this.email, this.purpose = 'registration'});

  final String email;
  final String purpose;

  @override
  ConsumerState<OtpScreen> createState() => _OtpScreenState();
}

class _OtpScreenState extends ConsumerState<OtpScreen> {
  final _code = TextEditingController();

  bool _submitting = false;
  String? _error;

  /// Seconds until the user may request another code.
  int _resendIn = 60;
  Timer? _resendTimer;

  @override
  void initState() {
    super.initState();
    _startResendCountdown();
  }

  @override
  void dispose() {
    _resendTimer?.cancel();
    _code.dispose();
    super.dispose();
  }

  void _startResendCountdown() {
    _resendTimer?.cancel();
    setState(() => _resendIn = 60);
    _resendTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) return timer.cancel();
      setState(() => _resendIn--);
      if (_resendIn <= 0) timer.cancel();
    });
  }

  Future<void> _verify() async {
    final code = _code.text.trim();
    if (code.length < 4) {
      setState(() => _error = 'Enter the code we sent you');
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final user = await ref.read(authRepositoryProvider).verifyOtp(
            email: widget.email,
            code: code,
            purpose: widget.purpose,
          );

      if (!mounted) return;

      if (user != null) {
        // The backend issued tokens along with the verification.
        await ref.read(authControllerProvider.notifier).completeSignIn(user);
        return;
      }

      // Verified, but no session — send them to sign in.
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Verified. You can now sign in.')),
      );
      context.go(Routes.login);
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Could not verify that code. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _resend() async {
    try {
      await ref.read(authRepositoryProvider).requestOtp(
            email: widget.email,
            purpose: widget.purpose,
          );
      if (!mounted) return;
      _startResendCountdown();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('We sent you a new code.')),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Verify your email')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Icon(
                  Icons.mark_email_unread_outlined,
                  size: 56,
                  color: AppColors.primary400,
                ),
                const SizedBox(height: 20),
                Text(
                  'Enter the code we sent to\n${widget.email}',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 16,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 28),

                TextField(
                  controller: _code,
                  keyboardType: TextInputType.number,
                  textAlign: TextAlign.center,
                  maxLength: 6,
                  autofocus: true,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  style: const TextStyle(
                    fontSize: 28,
                    letterSpacing: 12,
                    fontWeight: FontWeight.w700,
                  ),
                  decoration: InputDecoration(
                    counterText: '',
                    hintText: '000000',
                    errorText: _error,
                  ),
                  onSubmitted: (_) => _verify(),
                ),
                const SizedBox(height: 20),

                FilledButton(
                  onPressed: _submitting ? null : _verify,
                  child: _submitting
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.2,
                            color: AppColors.ink950,
                          ),
                        )
                      : const Text('Verify'),
                ),
                const SizedBox(height: 12),

                TextButton(
                  onPressed: _resendIn > 0 ? null : _resend,
                  child: Text(
                    _resendIn > 0
                        ? 'Resend code in ${_resendIn}s'
                        : 'Resend code',
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
