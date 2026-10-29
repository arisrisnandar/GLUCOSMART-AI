import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/theme/app_theme.dart';
import 'core/services/back_handler.dart';
import 'shared/providers/auth_provider.dart';
import 'features/auth/login_screen.dart';
import 'features/auth/register_screen.dart';
import 'features/dashboard/pasien_dashboard.dart';
import 'features/dashboard/dokter_dashboard.dart';
import 'features/dashboard/apoteker_dashboard.dart';
import 'features/dashboard/admin_dashboard.dart';
import 'features/pasien/health_input/health_input_screen.dart';
import 'features/pasien/prediction/prediction_result_screen.dart';
import 'features/pasien/prediction/prediction_history_screen.dart';
import 'features/pasien/medication/medication_schedule_screen.dart';
import 'features/pasien/education/education_list_screen.dart';
import 'features/pasien/profile/profile_screen.dart';
import 'features/pasien/chart/health_chart_screen.dart';
import 'features/pasien/therapy/therapy_plan_view_screen.dart';
import 'features/dokter/patient_list/patient_list_screen.dart';
import 'features/dokter/patient_detail/patient_detail_screen.dart';
import 'features/dokter/prescription/create_prescription_screen.dart';
import 'features/dokter/therapy_plan/therapy_plan_screen.dart';
import 'features/apoteker/verification/verification_list_screen.dart';
import 'features/apoteker/compliance/compliance_monitor_screen.dart';
import 'features/admin/user_management/user_list_screen.dart';
import 'features/admin/medication_master/medication_list_screen.dart';
import 'features/admin/reports/global_report_screen.dart';
import 'features/dokter/education/dokter_education_screen.dart';
import 'features/dokter/education/dokter_education_form_screen.dart';
import 'features/pasien/lab/lab_input_screen.dart';
import 'features/pasien/lab/lab_history_screen.dart';
import 'features/dokter/compliance/compliance_chart_screen.dart';
import 'features/pasien/assessment/assessment_menu_screen.dart';
import 'features/pasien/assessment/assessment_form_screen.dart';
import 'features/pasien/assessment/assessment_result_screen.dart';
import 'features/pasien/assessment/assessment_history_screen.dart';
import 'features/pasien/chat/consultation_list_screen.dart';
import 'features/pasien/chat/consultation_chat_screen.dart';
import 'features/apoteker/chat/apoteker_chat_list_screen.dart';
import 'features/pasien/diet/diet_screen.dart';
import 'features/pasien/diet/add_food_screen.dart';
import 'features/pasien/diet/diet_history_screen.dart';
import 'features/splash/splash_screen.dart';
import 'features/about/about_screen.dart';

const _dashboardPaths = {
  '/dashboard/pasien',
  '/dashboard/dokter',
  '/dashboard/apoteker',
  '/dashboard/admin',
};

class DiabetesApp extends ConsumerStatefulWidget {
  const DiabetesApp({super.key});

  @override
  ConsumerState<DiabetesApp> createState() => _DiabetesAppState();
}

class _DiabetesAppState extends ConsumerState<DiabetesApp> {
  late final GoRouter _router;

  @override
  void initState() {
    super.initState();
    _router = _buildRouter();
  }

  GoRouter _buildRouter() {
    return GoRouter(
      // ── PERUBAHAN: Mulai dari /splash, bukan /login ─────────────────────
      initialLocation: '/splash',
      redirect: (context, state) async {
        final currentPath = state.matchedLocation;

        // Biarkan splash screen berjalan tanpa redirect
        if (currentPath == '/splash') return null;

        final authState = ref.read(authProvider);
        final isLoggedIn = authState.isLoggedIn;
        final isAuthPage =
            currentPath == '/login' || currentPath == '/register';
        final isPublicPage = isAuthPage || currentPath == '/about';

        if (!isLoggedIn) {
          await ref.read(authProvider.notifier).checkLogin();
          final nowLoggedIn = ref.read(authProvider).isLoggedIn;
          if (!nowLoggedIn && !isPublicPage) return '/login';
          if (nowLoggedIn && isAuthPage) {
            return _dashboardRoute(ref.read(authProvider).role);
          }
        }
        if (isLoggedIn && isAuthPage) {
          return _dashboardRoute(authState.role);
        }
        return null;
      },
      routes: [
        // ── SPLASH ──────────────────────────────────────────────────────
        GoRoute(path: '/splash', builder: (_, __) => const SplashScreen()),

        GoRoute(path: '/', redirect: (_, __) => '/splash'),
        GoRoute(path: '/login', builder: (_, __) => const LoginScreen()),
        GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()),
        GoRoute(path: '/about', builder: (_, __) => const AboutScreen()),

        // ── PASIEN ──────────────────────────────────────────────────────
        GoRoute(
          path: '/dashboard/pasien',
          builder: (_, __) => const PasienDashboard(),
        ),
        GoRoute(
          path: '/health/input',
          builder: (_, __) => const HealthInputScreen(),
        ),
        GoRoute(
          path: '/health/chart',
          builder: (_, __) => const HealthChartScreen(),
        ),
        GoRoute(
          path: '/medication/schedule',
          builder: (_, __) => const MedicationScheduleScreen(),
        ),
        GoRoute(
          path: '/education/list',
          builder: (_, __) => const EducationListScreen(),
        ),
        GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen()),
        GoRoute(
          path: '/prediction/history',
          builder: (_, __) => const PredictionHistoryScreen(),
        ),
        GoRoute(
          path: '/prediction/result/:recordId',
          builder: (_, state) => PredictionResultScreen(
            recordId: int.parse(state.pathParameters['recordId']!),
          ),
        ),
        GoRoute(
          path: '/therapy/my',
          builder: (_, __) => const TherapyPlanViewScreen(),
        ),
        GoRoute(path: '/lab/input', builder: (_, __) => const LabInputScreen()),
        GoRoute(
          path: '/lab/history',
          builder: (_, __) => const LabHistoryScreen(),
        ),
        GoRoute(
          path: '/assessment',
          builder: (_, __) => const AssessmentMenuScreen(),
        ),
        GoRoute(
          path: '/assessment/history',
          builder: (_, __) => const AssessmentHistoryScreen(),
        ),
        GoRoute(
          path: '/assessment/form/:type',
          builder: (_, state) => AssessmentFormScreen(
            assessmentType: state.pathParameters['type']!,
          ),
        ),
        GoRoute(
          path: '/assessment/result',
          builder: (_, state) => AssessmentResultScreen(
            result: state.extra as Map<String, dynamic>,
          ),
        ),
        GoRoute(
          path: '/konsultasi',
          builder: (_, __) => const ConsultationListScreen(),
        ),
        GoRoute(
          path: '/konsultasi/chat/:sessionId',
          builder: (_, state) {
            final sessionId = int.parse(state.pathParameters['sessionId']!);
            return ConsultationChatScreen(sessionId: sessionId);
          },
        ),
        GoRoute(path: '/diet', builder: (_, __) => const DietScreen()),
        GoRoute(path: '/diet/add', builder: (_, __) => const AddFoodScreen()),
        GoRoute(
          path: '/diet/history',
          builder: (_, __) => const DietHistoryScreen(),
        ),

        // ── DOKTER ──────────────────────────────────────────────────────
        GoRoute(
          path: '/dashboard/dokter',
          builder: (_, __) => const DokterDashboard(),
        ),
        GoRoute(
          path: '/dokter/patients',
          builder: (_, __) => const PatientListScreen(),
        ),
        GoRoute(
          path: '/dokter/patients/:patientId',
          builder: (_, state) => PatientDetailScreen(
            patientId: int.parse(state.pathParameters['patientId']!),
          ),
        ),
        GoRoute(
          path: '/dokter/prescription/create/:patientId',
          builder: (_, state) => CreatePrescriptionScreen(
            patientId: int.parse(state.pathParameters['patientId']!),
          ),
        ),
        GoRoute(
          path: '/dokter/therapy/:patientId',
          builder: (_, state) => TherapyPlanScreen(
            patientId: int.parse(state.pathParameters['patientId']!),
          ),
        ),
        GoRoute(
          path: '/dokter/education',
          builder: (_, __) => const DokterEducationScreen(),
        ),
        GoRoute(
          path: '/dokter/education/add',
          builder: (_, __) => const DokterEducationFormScreen(),
        ),
        GoRoute(
          path: '/dokter/education/edit/:id',
          builder: (_, state) => DokterEducationFormScreen(
            existing: state.extra as Map<String, dynamic>?,
          ),
        ),
        GoRoute(
          path: '/compliance',
          builder: (_, __) => const ComplianceChartScreen(),
        ),
        GoRoute(
          path: '/dokter/patients/:patientId/assessment',
          builder: (_, state) => AssessmentHistoryScreen(
            patientId: int.parse(state.pathParameters['patientId']!),
          ),
        ),

        // ── APOTEKER ────────────────────────────────────────────────────
        GoRoute(
          path: '/dashboard/apoteker',
          builder: (_, __) => const ApotekerDashboard(),
        ),
        GoRoute(
          path: '/apoteker/verification',
          builder: (_, __) => const VerificationListScreen(),
        ),
        GoRoute(
          path: '/apoteker/compliance',
          builder: (_, __) => const ComplianceMonitorScreen(),
        ),
        GoRoute(
          path: '/apoteker/chat',
          builder: (_, __) => const ApotekerChatListScreen(),
        ),
        GoRoute(
          path: '/apoteker/chat/:sessionId',
          builder: (_, state) => ConsultationChatScreen(
            sessionId: int.parse(state.pathParameters['sessionId']!),
            isApoteker: true,
          ),
        ),

        // ── ADMIN ───────────────────────────────────────────────────────
        GoRoute(
          path: '/dashboard/admin',
          builder: (_, __) => const AdminDashboard(),
        ),
        GoRoute(
          path: '/admin/users',
          builder: (_, __) => const UserListScreen(),
        ),
        GoRoute(
          path: '/admin/medications',
          builder: (_, __) => const MedicationListScreen(),
        ),
        GoRoute(
          path: '/admin/reports',
          builder: (_, __) => const GlobalReportScreen(),
        ),
      ],
    );
  }

  String _dashboardRoute(String role) {
    switch (role) {
      case 'pasien':
        return '/dashboard/pasien';
      case 'dokter':
        return '/dashboard/dokter';
      case 'apoteker':
        return '/dashboard/apoteker';
      case 'admin':
        return '/dashboard/admin';
      default:
        return '/login';
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Telefarmasi Diabetes',
      theme: AppTheme.lightTheme,
      routerConfig: _router,
      debugShowCheckedModeBanner: false,
      builder: (context, child) {
        return _BackButtonHandler(
          router: _router,
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}

class _BackButtonHandler extends StatelessWidget {
  final GoRouter router;
  final Widget child;

  const _BackButtonHandler({required this.router, required this.child});

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) async {
        if (didPop) return;

        final String location = router.routerDelegate.currentConfiguration.uri
            .toString();

        // Splash tidak bisa di-pop
        if (location == '/splash') return;

        if (_dashboardPaths.contains(location)) {
          await BackHandlerService.showExitDialog(context);
          return;
        }

        if (location == '/login' || location == '/register') {
          SystemNavigator.pop();
          return;
        }

        if (router.canPop()) {
          router.pop();
        } else {
          router.go(_getDashboardByLocation(location));
        }
      },
      child: child,
    );
  }

  String _getDashboardByLocation(String path) {
    if (path.contains('/dokter')) return '/dashboard/dokter';
    if (path.contains('/apoteker')) return '/dashboard/apoteker';
    if (path.contains('/admin')) return '/dashboard/admin';
    return '/dashboard/pasien';
  }
}
