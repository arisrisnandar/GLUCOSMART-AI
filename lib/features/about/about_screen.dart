import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';

class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Tentang Aplikasi')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            // =====================================================
            // HEADER
            // =====================================================
            Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  children: [
                    Image.asset('assets/icon/app_icon1.png', height: 90),
                    const SizedBox(height: 16),

                    Text(
                      'Telefarmasi Diabetes',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineMedium
                          ?.copyWith(fontWeight: FontWeight.bold),
                    ),

                    const SizedBox(height: 8),

                    Text(
                      'Versi 1.0.0',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),

                    const SizedBox(height: 12),

                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Text(
                        'Manajemen Diabetes Terpadu',
                        style: TextStyle(
                          color: AppColors.primary,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),

            // =====================================================
            // DESKRIPSI
            // =====================================================
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(
                          Icons.medical_services_outlined,
                          color: AppColors.primary,
                        ),
                        SizedBox(width: 8),
                        Text(
                          'Deskripsi Aplikasi',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 14),

                    Text(
                      'Telefarmasi Diabetes merupakan aplikasi layanan kesehatan digital yang dirancang untuk mendukung pengelolaan Diabetes Mellitus secara terpadu melalui pemantauan kondisi kesehatan, konsultasi tenaga kesehatan, pengelolaan terapi obat, edukasi pasien, serta pemanfaatan teknologi kecerdasan buatan untuk membantu deteksi dan prediksi risiko kesehatan.',
                      style: Theme.of(context).textTheme.bodyMedium,
                      textAlign: TextAlign.justify,
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),

            // =====================================================
            // HKI
            // =====================================================
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.verified_user_outlined, color: Colors.green),
                        SizedBox(width: 8),
                        Text(
                          'Hak Kekayaan Intelektual',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 14),

                    Text(
                      'Aplikasi Telefarmasi Diabetes merupakan karya intelektual yang sedang dalam proses pendaftaran Hak Kekayaan Intelektual (HKI). Seluruh kode program, desain sistem, dokumentasi, serta komponen aplikasi dilindungi sesuai dengan ketentuan peraturan perundang-undangan yang berlaku di Republik Indonesia.',
                      style: Theme.of(context).textTheme.bodyMedium,
                      textAlign: TextAlign.justify,
                    ),

                    const SizedBox(height: 16),

                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.orange.withValues(alpha: 0.08),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: Colors.orange.withValues(alpha: 0.25),
                        ),
                      ),
                      child: const Column(
                        children: [
                          Row(
                            children: [
                              Icon(Icons.badge_outlined, size: 18),
                              SizedBox(width: 8),
                              Text(
                                'Nomor HKI',
                                style: TextStyle(fontWeight: FontWeight.w600),
                              ),
                              Spacer(),
                              Text('Dalam Proses'),
                            ],
                          ),
                          SizedBox(height: 8),
                          Row(
                            children: [
                              Icon(Icons.description_outlined, size: 18),
                              SizedBox(width: 8),
                              Text(
                                'Status',
                                style: TextStyle(fontWeight: FontWeight.w600),
                              ),
                              Spacer(),
                              Text('Pengajuan HKI'),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),

            // =====================================================
            // TIM
            // =====================================================
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.groups_outlined, color: AppColors.primary),
                        SizedBox(width: 8),
                        Text(
                          'Tim Pengembang',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 16),

                    _personTile(
                      Icons.school_outlined,
                      'Risnandar, Ph.D.',
                      'Pembimbing Penelitian',
                    ),

                    const Divider(),

                    _personTile(
                      Icons.computer_outlined,
                      'Feri Ilham Azkia',
                      'Pengembang Sistem',
                    ),

                    const Divider(),

                    _personTile(
                      Icons.school_outlined,
                      'Dr. Eng Munawir, S.Kom., M.T.',
                      'Pembimbing Penelitian',
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),

            // =====================================================
            // INSTITUSI
            // =====================================================
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(
                          Icons.account_balance_outlined,
                          color: AppColors.primary,
                        ),
                        SizedBox(width: 8),
                        Text(
                          'Institusi Pendukung',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 20),

                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        Expanded(
                          child: _logoInstitution(
                            'assets/icon/brin.png',
                            'BRIN',
                          ),
                        ),
                        Expanded(
                          child: _logoInstitution('assets/icon/upi.png', 'UPI'),
                        ),
                        Expanded(
                          child: _logoInstitution(
                            'assets/icon/teknik_komputer.png',
                            'Teknik\nKomputer',
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 20),

                    const Text(
                      'Badan Riset dan Inovasi Nasional (BRIN)',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),

                    SizedBox(height: 4),

                    Text(
                      'Universitas Pendidikan Indonesia',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),

                    SizedBox(height: 4),

                    Text(
                      'Program Studi Teknik Komputer',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // =====================================================
            // FOOTER
            // =====================================================
            Text(
              '© 2026 Telefarmasi Diabetes',
              style: Theme.of(context).textTheme.bodySmall,
            ),

            const SizedBox(height: 4),

            Text(
              'Seluruh Hak Dilindungi',
              style: Theme.of(context).textTheme.bodySmall,
            ),

            const SizedBox(height: 30),
          ],
        ),
      ),
    );
  }

  static Widget _personTile(IconData icon, String name, String role) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: CircleAvatar(
        backgroundColor: AppColors.primary.withValues(alpha: 0.1),
        child: Icon(icon, color: AppColors.primary),
      ),
      title: Text(name, style: const TextStyle(fontWeight: FontWeight.bold)),
      subtitle: Text(role),
    );
  }

  static Widget _logoInstitution(String asset, String title) {
    return Column(
      children: [
        SizedBox(height: 60, child: Image.asset(asset, fit: BoxFit.contain)),
        const SizedBox(height: 8),
        Text(
          title,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}
