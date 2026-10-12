import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';

/// Shown while the stored refresh token is exchanged for a session, so a
/// returning user never sees the login screen flash past.
class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 88,
              height: 88,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppColors.primary500, AppColors.accent500],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(26),
              ),
              child: const Icon(
                Icons.shield_outlined,
                size: 46,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              'Neighbourhood Watch',
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Looking out for each other',
              style: TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 40),
            const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(strokeWidth: 2.2),
            ),
          ],
        ),
      ),
    );
  }
}
