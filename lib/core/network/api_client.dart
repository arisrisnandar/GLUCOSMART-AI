//api_client
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'api_endpoints.dart';

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;
  ApiClient._internal() {
    _init(); // Langsung init di constructor
  }

  final _storage = const FlutterSecureStorage();
  late Dio _dio; // Hapus 'final' agar bisa direinit jika perlu

  Dio get dio => _dio;

  void _init() {
    _dio = Dio(
      BaseOptions(
        baseUrl: ApiEndpoints.baseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
        headers: {
          // 'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true',
        },
      ),
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _storage.read(key: 'access_token');
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (error, handler) {
          handler.next(error);
        },
      ),
    );
  }

  // Tetap ada init() untuk dipanggil dari main.dart (tidak akan error)
  void init() {
    // Sudah diinit di constructor, tidak perlu reinit
    // Tapi update baseUrl jika berubah
    _dio.options.baseUrl = ApiEndpoints.baseUrl;
  }

  Future<void> saveToken(String token) async {
    await _storage.write(key: 'access_token', value: token);
  }

  Future<void> saveUserInfo({
    required int userId,
    required String role,
    required String name,
  }) async {
    await _storage.write(key: 'user_id', value: userId.toString());
    await _storage.write(key: 'role', value: role);
    await _storage.write(key: 'name', value: name);
  }

  Future<String?> getToken() => _storage.read(key: 'access_token');
  Future<String?> getRole() => _storage.read(key: 'role');
  Future<String?> getName() => _storage.read(key: 'name');
  Future<int?> getUserId() async {
    final id = await _storage.read(key: 'user_id');
    return id != null ? int.tryParse(id) : null;
  }

  Future<void> logout() async {
    await _storage.deleteAll();
  }
}
