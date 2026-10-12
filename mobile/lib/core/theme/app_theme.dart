import 'package:flutter/material.dart';

/// Colour tokens mirrored from the web dashboard's Tailwind config so the two
/// clients read as one product. See `frontend/tailwind.config.js`.
class AppColors {
  const AppColors._();

  // primary (cyan)
  static const primary300 = Color(0xFF67E8F9);
  static const primary400 = Color(0xFF22D3EE);
  static const primary500 = Color(0xFF06B6D4);
  static const primary600 = Color(0xFF0891B2);
  static const primary700 = Color(0xFF0E7490);

  // accent (violet)
  static const accent400 = Color(0xFFA78BFA);
  static const accent500 = Color(0xFF8B5CF6);

  // ink (surfaces)
  static const ink950 = Color(0xFF050816);
  static const ink900 = Color(0xFF080D20);
  static const ink800 = Color(0xFF0D1430);
  static const ink700 = Color(0xFF141C3F);

  // semantic
  static const danger500 = Color(0xFFEF4444);
  static const danger600 = Color(0xFFDC2626);
  static const warning400 = Color(0xFFFBBF24);
  static const warning500 = Color(0xFFF59E0B);
  static const success500 = Color(0xFF22C55E);
  static const info500 = Color(0xFF3B82F6);

  static const textPrimary = Color(0xFFE8ECF8);
  static const textSecondary = Color(0xFF94A3C4);
  static const border = Color(0xFF1E2A50);

  /// Incident severity colours. Keys match `Incident.Severity` on the backend.
  static const severity = <String, Color>{
    'red': danger500,
    'yellow': warning400,
    'blue': info500,
    'green': success500,
  };

  static Color forSeverity(String value) => severity[value] ?? textSecondary;
}

class AppTheme {
  const AppTheme._();

  static ThemeData get dark {
    const scheme = ColorScheme.dark(
      primary: AppColors.primary400,
      onPrimary: AppColors.ink950,
      secondary: AppColors.accent400,
      onSecondary: AppColors.ink950,
      surface: AppColors.ink900,
      onSurface: AppColors.textPrimary,
      error: AppColors.danger500,
      onError: Colors.white,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: AppColors.ink950,
      fontFamily: 'Roboto',
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.ink950,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: AppColors.textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w600,
        ),
        iconTheme: IconThemeData(color: AppColors.textPrimary),
      ),
      cardTheme: CardThemeData(
        color: AppColors.ink800,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppColors.border),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.ink800,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        border: _inputBorder(AppColors.border),
        enabledBorder: _inputBorder(AppColors.border),
        focusedBorder: _inputBorder(AppColors.primary500, width: 1.6),
        errorBorder: _inputBorder(AppColors.danger500),
        focusedErrorBorder: _inputBorder(AppColors.danger500, width: 1.6),
        labelStyle: const TextStyle(color: AppColors.textSecondary),
        hintStyle: const TextStyle(color: AppColors.textSecondary),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.primary500,
          foregroundColor: AppColors.ink950,
          minimumSize: const Size.fromHeight(52),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.primary300,
          minimumSize: const Size.fromHeight(52),
          side: const BorderSide(color: AppColors.border),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: AppColors.primary300),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.ink900,
        surfaceTintColor: Colors.transparent,
        indicatorColor: AppColors.primary700.withValues(alpha: 0.35),
        labelTextStyle: WidgetStatePropertyAll(
          TextStyle(fontSize: 12, color: AppColors.textSecondary),
        ),
      ),
      dividerTheme: const DividerThemeData(color: AppColors.border, space: 1),
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.ink800,
        side: const BorderSide(color: AppColors.border),
        labelStyle: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.ink700,
        contentTextStyle: const TextStyle(color: AppColors.textPrimary),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  static OutlineInputBorder _inputBorder(Color color, {double width = 1}) {
    return OutlineInputBorder(
      borderRadius: BorderRadius.circular(14),
      borderSide: BorderSide(color: color, width: width),
    );
  }
}
