import 'dart:convert';
import 'dart:io';
import 'package:device_info_plus/device_info_plus';

class DeviceService {
  /// Fetch a unique persistent hardware ID and package it as base64 JSON
  static Future<String> getDeviceFingerprint() async {
    final DeviceInfoPlugin deviceInfo = DeviceInfoPlugin();
    String uuid = "unknown_device";
    String model = "unknown";
    String osVersion = "unknown";

    try {
      if (Platform.isAndroid) {
        final AndroidDeviceInfo androidInfo = await deviceInfo.androidInfo;
        uuid = androidInfo.id; // Unique Android hardware ID
        model = androidInfo.model;
        osVersion = "Android ${androidInfo.version.release}";
      } else if (Platform.isIOS) {
        final IosDeviceInfo iosInfo = await deviceInfo.iosInfo;
        uuid = iosInfo.identifierForVendor ?? "unknown_ios_id";
        model = iosInfo.model;
        osVersion = "iOS ${iosInfo.systemVersion}";
      }
    } catch (e) {
      uuid = "device_err_${e.toString().hashCode}";
      model = "ErrorFetch";
    }

    // Match the JSON schema expected by get_device_uuid in main.py
    final Map<String, String> fingerprintMap = {
      "uuid": uuid,
      "ua": "NativeMobileApp ($model; $osVersion)",
      "screen": "AppView"
    };

    // Convert to JSON and encode in base64
    final String jsonStr = jsonEncode(fingerprintMap);
    return base64Encode(utf8.encode(jsonStr));
  }
}
