import 'package:flutter/material.dart';

class AppColors {
  // ── Brand palette — deep teal + warm coral accent ──────
  static const primary = Color(0xFF00796B); // teal 700
  static const primaryDark = Color(0xFF004D40); // teal 900
  static const primaryLight = Color(0xFF4DB6AC); // teal 300
  static const accent = Color(0xFFFF6F61); // coral
  static const accentDark = Color(0xFFE55A4E);

  // ── Semantic ────────────────────────────────────────────
  static const danger = Color(0xFFE53935);
  static const warning = Color(0xFFFFA000);
  static const success = Color(0xFF2E7D32);
  static const info = Color(0xFF0277BD);

  // ── Backgrounds ─────────────────────────────────────────
  static const background = Color(0xFFF0F4F3); // very light teal tint
  static const cardBg = Colors.white;
  static const surfaceLight = Color(0xFFE8F5E9);

  // ── Text ────────────────────────────────────────────────
  static const textPrimary = Color(0xFF1A2E2B);
  static const textSecondary = Color(0xFF5F7974);
  static const textHint = Color(0xFFAABBB8);

  // ── Borders / dividers ───────────────────────────────────
  static const divider = Color(0xFFDDE8E6);

  // ── Gradient helpers ─────────────────────────────────────
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF00796B), Color(0xFF004D40)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient cardGradient = LinearGradient(
    colors: [Color(0xFF00897B), Color(0xFF00695C)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient accentGradient = LinearGradient(
    colors: [Color(0xFFFF6F61), Color(0xFFE55A4E)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}

class AppStrings {
  static const appName = 'DIACARE-AI';
  static const loginTitle = 'Masuk ke Akun Anda';
  static const registerTitle = 'Daftar Akun Baru';
}
