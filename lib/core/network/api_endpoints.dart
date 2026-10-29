class ApiEndpoints {
  //static const String baseUrl = 'http://10.0.2.2:8000'; // Android emulator -> localhost
  // static const String baseUrl = 'http://localhost:8000'; // iOS simulator
  // static const String baseUrl = 'http://YOUR_SERVER_IP:8000'; // Real device
  static const String baseUrl =
      'https://gawk-mourner-dance.ngrok-free.dev'; // Ngrok URL for testing

  // Auth
  static const String register = '/auth/register';
  static const String login = '/auth/login';
  static const String me = '/auth/me';
  static const String changePassword = '/auth/change-password';

  // Patients
  static const String myProfile = '/patients/me';
  static const String listPatients = '/patients/';
  static String patientDetail(int id) => '/patients/$id';
  static String patientMode(int id) => '/patients/$id/mode';

  // Health
  static const String createHealth = '/health/';
  static const String myHealth = '/health/my';
  static String patientHealth(int patientId) => '/health/patient/$patientId';

  // Prediction
  static String runPrediction(int recordId) => '/prediction/run/$recordId';
  static const String myPredictions = '/prediction/my';
  static String patientPredictions(int patientId) =>
      '/prediction/patient/$patientId';
  static const String highRiskPatients = '/prediction/high-risk';

  // Prescriptions
  static const String createPrescription = '/prescriptions/';
  static const String myPrescriptions = '/prescriptions/my';
  static const String pendingPrescriptions = '/prescriptions/pending';
  static String prescriptionDetail(int id) => '/prescriptions/$id';
  static String verifyPrescription(int id) => '/prescriptions/$id/verify';
  static const String todaySchedules = '/prescriptions/schedules/today';
  static String markTaken(int scheduleId) =>
      '/prescriptions/schedules/$scheduleId/take';

  // Notifications
  static const String notifications = '/notifications/';
  static const String unreadCount = '/notifications/unread-count';
  static const String readAll = '/notifications/read-all';
  static String readNotif(int id) => '/notifications/$id/read';
  static const String fcmToken = '/notifications/fcm-token';

  // Reports / PDF
  static const String myReport = '/reports/my';
  static String patientReport(int id) => '/reports/patient/$id';

  // Doctors
  static const String doctorDashboard = '/doctors/dashboard';
  static const String doctorPatients = '/doctors/patients';

  // Admin
  static const String adminUsers = '/admin/users';
  static String toggleUserActive(int id) => '/admin/users/$id/toggle-active';
  static const String adminMedications = '/admin/medications';
  static String adminMedication(int id) => '/admin/medications/$id';
  static const String adminEducation = '/admin/education';
  static const String adminSummary = '/admin/reports/summary';
  static const String pendingApprovals = '/admin/approvals';
  static const String pendingApprovalsCount = '/admin/approvals/count';
  static String approveUser(int id) => '/admin/approvals/$id/approve';
  static String rejectUser(int id) => '/admin/approvals/$id/reject';

  // ── Therapy Plans ───────────────────────────────────
  static const String createTherapyPlan = '/therapy_plans/';
  static const String myTherapyPlan = '/therapy_plans/my';
  static String therapyPlanByPatient(int id) => '/therapy_plans/patient/$id';

  // ── Doctor Medications ──────────────────────────────
  static const String doctorMedications = '/doctors/medications';

  // ── Education ───────────────────────────────────────
  static const String educationList = '/education/';
  static const String educationCategories = '/education/categories';
  static String educationDetail(int id) => '/education/$id';
  static const String educationSeed = '/education/seed/init';

  // Lab Records ← BARU
  static const String createLabRecord = '/lab/';
  static const String myLabRecords = '/lab/my';
  static const String myLatestLab = '/lab/my/latest';
  static String patientLabRecords(int id) => '/lab/patient/$id';
  static String deleteLabRecord(int id) => '/lab/$id';

  // Compliance ← BARU
  static const String myCompliance = '/prescriptions/compliance/my';
  static String patientCompliance(int id) =>
      '/prescriptions/compliance/patient/$id';

  // Assessments ← BARU
  static const String submitAssessment = '/assessment/';
  static const String myAssessments = '/assessment/my';
  static const String myLatestAssessment = '/assessment/my/latest';
  static String patientAssessments(int id) => '/assessment/patient/$id';

  // Chat / Consultation
  static const String createSession = '/consultation/sessions/';
  static const String mySessions = '/consultation/sessions/my';
  static const String allSessions = '/consultation/sessions/';
  static String sessionDetail(int id) => '/consultation/sessions/$id';
  static String sessionMessages(int id) =>
      '/consultation/sessions/$id/messages';
  static String sendMessage(int id) => '/consultation/sessions/$id/messages';
  static String closeSession(int id) => '/consultation/sessions/$id/close';
  static String takeSession(int id) => '/consultation/sessions/$id/take';
  static String reopenSession(int id) => '/consultation/sessions/$id/reopen';
  static String deleteSession(int id) => '/consultation/sessions/$id';
  static String editMessage(int sid, int mid) =>
      '/consultation/sessions/$sid/messages/$mid';
  static String deleteMessage(int sid, int mid) =>
      '/consultation/sessions/$sid/messages/$mid';

  // Diet
  static const String foodDatabase = '/diet/foods/';
  static const String addDietEntry = '/diet/entries/';
  static const String todayEntries = '/diet/entries/today';
  static const String dietEntries = '/diet/entries/';
  static const String todayDietSummary = '/diet/summary/today';
  static const String dietHistory = '/diet/history/';
  static String deleteDietEntry(int id) => '/diet/entries/$id';

  static const String educationNewsFeed = '/education/news/feed';
  static const String educationNewsSources = '/education/news/sources';
}
