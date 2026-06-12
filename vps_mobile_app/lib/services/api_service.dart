import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  /// Submit check-in form parameters to the FastAPI backend API
  static Future<Map<String, dynamic>> submitCheckin({
    required String apiUrl, // e.g. https://vps-attendance-1.onrender.com
    required String employeeCode,
    required double latitude,
    required double longitude,
    required String deviceFingerprint,
  }) async {
    // Sanitize API URL
    final String baseUrl = apiUrl.endsWith('/') 
        ? apiUrl.substring(0, apiUrl.length - 1) 
        : apiUrl;
    final Uri requestUri = Uri.parse('$baseUrl/api/attendance');

    try {
      // Construct form-data fields matching main.py parameters
      final http.MultipartRequest request = http.MultipartRequest('POST', requestUri)
        ..fields['employee_code'] = employeeCode
        ..fields['token'] = 'static_bypass' // Token is bypassed in database Static Mode config
        ..fields['latitude'] = latitude.toString()
        ..fields['longitude'] = longitude.toString()
        ..fields['device_fingerprint'] = deviceFingerprint;

      // Send request with timeout limits
      final http.StreamedResponse streamedResponse = await request.send()
          .timeout(const Duration(seconds: 15));
      final http.Response response = await http.Response.fromStream(streamedResponse);

      final Map<String, dynamic> responseData = jsonDecode(response.body);

      if (response.statusCode == 200 || response.statusCode == 201) {
        return {
          "success": true,
          "teacher_name": responseData["teacher_name"] ?? "Teacher",
          "check_in_time": responseData["check_in_time"] ?? "--",
          "status": responseData["status"] ?? "Present",
          "distance_meters": responseData["distance_meters"] ?? 0.0
        };
      } else {
        // Return structured API validation exception details
        final String errorMsg = responseData["detail"] ?? "Server validation rejected check-in.";
        return {
          "success": false,
          "error": errorMsg
        };
      }
    } catch (e) {
      return {
        "success": false,
        "error": "Failed to connect to school server. Please verify your internet or URL setting."
      };
    }
  }
}
