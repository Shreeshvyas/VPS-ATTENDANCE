import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:geolocator/geolocator.dart';
import '../services/location_service.dart';
import '../services/device_service.dart';
import '../services/api_service.dart';

class CheckinScreen extends StatefulWidget {
  const CheckinScreen({Key? key}) : super(key: key);

  @override
  State<CheckinScreen> createState() => _CheckinScreenState();
}

class _CheckinScreenState extends State<CheckinScreen> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _codeController = TextEditingController();
  final TextEditingController _urlController = TextEditingController();

  bool _isLoading = false;
  String _statusMessage = "";
  Color _statusColor = Colors.cyan;
  bool _isSettingsVisible = false;

  @override
  void initState() {
    super.initState();
    _loadPreferences();
  }

  // Load saved configurations from SharedPreferences cache
  Future<void> _loadPreferences() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _codeController.text = prefs.getString('saved_employee_code') ?? '';
      // Default to your deployed AWS EC2 subdomain URL
      _urlController.text = prefs.getString('saved_api_url') ?? 'https://attendance.vyaspublicschool.in';
    });
  }

  // Save configurations to SharedPreferences cache
  Future<void> _savePreferences() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('saved_employee_code', _codeController.text);
    await prefs.setString('saved_api_url', _urlController.text);
  }

  // Trigger Geofencing & API submission
  Future<void> _submitAttendance() async {
    if (!_formKey.currentState!.validate()) return;
    
    setState(() {
      _isLoading = true;
      _statusMessage = "Acquiring GPS location coordinates...";
      _statusColor = Colors.cyan;
    });

    try {
      // 1. Fetch GPS location coordinates
      final Position position = await LocationService.getCurrentLocation();
      
      setState(() {
        _statusMessage = "Building device security signature...";
        _statusColor = Colors.indigoAccent;
      });

      // 2. Fetch unique device fingerprint
      final String deviceFingerprint = await DeviceService.getDeviceFingerprint();

      setState(() {
        _statusMessage = "Transmitting to school server...";
        _statusColor = Colors.deepPurpleAccent;
      });

      // 3. Post data to FastAPI backend
      final Map<String, dynamic> result = await ApiService.submitCheckin(
        apiUrl: _urlController.text.trim(),
        employeeCode: _codeController.text.trim(),
        latitude: position.latitude,
        longitude: position.longitude,
        deviceFingerprint: deviceFingerprint,
      );

      setState(() {
        _isLoading = false;
      });

      if (result['success'] == true) {
        // Cache teacher code locally on successful log
        await _savePreferences();
        _showSuccessDialog(result, true);
      } else {
        _showErrorDialog(result['error'] ?? 'Check-in validation rejected.');
      }

    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      _showErrorDialog(e.toString());
    }
  }

  // Trigger Clock-Out & API submission
  Future<void> _submitCheckout() async {
    if (!_formKey.currentState!.validate()) return;
    
    setState(() {
      _isLoading = true;
      _statusMessage = "Acquiring GPS location coordinates...";
      _statusColor = Colors.cyan;
    });

    try {
      // 1. Fetch GPS location coordinates
      final Position position = await LocationService.getCurrentLocation();
      
      setState(() {
        _statusMessage = "Building device security signature...";
        _statusColor = Colors.indigoAccent;
      });

      // 2. Fetch unique device fingerprint
      final String deviceFingerprint = await DeviceService.getDeviceFingerprint();

      setState(() {
        _statusMessage = "Transmitting clock-out request...";
        _statusColor = Colors.deepPurpleAccent;
      });

      // 3. Post data to FastAPI backend
      final Map<String, dynamic> result = await ApiService.submitCheckout(
        apiUrl: _urlController.text.trim(),
        employeeCode: _codeController.text.trim(),
        latitude: position.latitude,
        longitude: position.longitude,
        deviceFingerprint: deviceFingerprint,
      );

      setState(() {
        _isLoading = false;
      });

      if (result['success'] == true) {
        // Cache teacher code locally on successful log
        await _savePreferences();
        _showSuccessDialog(result, false);
      } else {
        _showErrorDialog(result['error'] ?? 'Clock-out validation rejected.');
      }

    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      _showErrorDialog(e.toString());
    }
  }

  void _showSuccessDialog(Map<String, dynamic> data, bool isCheckin) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        backgroundColor: const Color(0xFF1E293B),
        title: Column(
          children: [
            const Icon(Icons.check_circle_rounded, color: Color(0xFF10B981), size: 60),
            const SizedBox(height: 12),
            Text(
              isCheckin ? 'Check-In Successful' : 'Clock-Out Successful',
              style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              data['teacher_name'],
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: Colors.white),
            ),
            const SizedBox(height: 5),
            Text(
              isCheckin ? (data['check_in_time'] ?? '--') : (data['check_out_time'] ?? '--'),
              style: const TextStyle(fontSize: 14, color: const Color(0xFF94A3B8)),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.04),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.white.withOpacity(0.08)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.location_on, size: 14, color: Color(0xFF06B6D4)),
                  const SizedBox(width: 5),
                  Text(
                    'Distance: ${data['distance_meters'].toStringAsFixed(0)}m',
                    style: const TextStyle(fontSize: 12, color: Color(0xFFCBD5E1)),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          Center(
            child: TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('OK', style: TextStyle(color: Color(0xFF6366F1), fontWeight: FontWeight.bold)),
            ),
          ),
        ],
      ),
    );
  }

  void _showErrorDialog(String error) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        backgroundColor: const Color(0xFF1E293B),
        title: Column(
          children: const [
            Icon(Icons.cancel_rounded, color: Color(0xFFEF4444), size: 60),
            SizedBox(height: 12),
            Text(
              'Check-In Failed',
              style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white),
            ),
          ],
        ),
        content: Text(
          error,
          textAlign: TextAlign.center,
          style: const TextStyle(color: Color(0xFFCBD5E1)),
        ),
        actions: [
          Center(
            child: TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('RETRY', style: TextStyle(color: Color(0xFF6366F1), fontWeight: FontWeight.bold)),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            icon: Icon(
              _isSettingsVisible ? Icons.close_rounded : Icons.settings_rounded,
              color: const Color(0xFF64748B),
            ),
            onPressed: () {
              setState(() {
                _isSettingsVisible = !_isSettingsVisible;
              });
            },
          )
        ],
      ),
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const SizedBox(height: 20),
              // App Logo / Icon Header
              ClipRRect(
                borderRadius: BorderRadius.circular(24),
                child: Container(
                  width: 110,
                  height: 110,
                  color: Colors.white,
                  padding: const EdgeInsets.all(6),
                  child: Image.asset(
                    'assets/images/logo.png',
                    fit: BoxFit.contain,
                  ),
                ),
              ),
              const SizedBox(height: 25),
              const Text(
                'VPS Attendance',
                style: TextStyle(
                  fontFamily: 'Outfit',
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(height: 5),
              const Text(
                'Secure Staff Mobile Portal',
                style: TextStyle(
                  fontSize: 14,
                  color: Color(0xFF94A3B8),
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 35),

              // Settings Form Panel
              if (_isSettingsVisible) ...[
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'CONNECTION SETTINGS',
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF06B6D4)),
                        ),
                        const SizedBox(height: 15),
                        TextFormField(
                          controller: _urlController,
                          style: const TextStyle(fontSize: 14),
                          decoration: const InputDecoration(
                            labelText: 'FastAPI Backend URL',
                            prefixIcon: Icon(Icons.link_rounded),
                          ),
                        ),
                        const SizedBox(height: 10),
                        const Text(
                          'Default points to your deployed Render service.',
                          style: TextStyle(fontSize: 11, color: Color(0xFF64748B)),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),
              ],

              // Main Check-In Card
              Form(
                key: _formKey,
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'DAILY CHECK-IN',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF6366F1),
                            letterSpacing: 1.0,
                          ),
                        ),
                        const SizedBox(height: 20),
                        TextFormField(
                          controller: _codeController,
                          keyboardType: TextInputType.number,
                          maxLength: 6,
                          style: const TextStyle(fontSize: 18, letterSpacing: 4.0, fontWeight: FontWeight.bold),
                          validator: (value) {
                            if (value == null || value.length != 6) {
                              return 'Please enter your 6-digit code';
                            }
                            return null;
                          },
                          decoration: const InputDecoration(
                            labelText: 'Employee Code',
                            prefixIcon: Icon(Icons.badge_rounded),
                            counterText: '',
                            hintText: '000000',
                          ),
                        ),
                        const SizedBox(height: 25),
                        
                        if (_isLoading) ...[
                          Center(
                            child: Column(
                              children: [
                                const CircularProgressIndicator(),
                                const SizedBox(height: 15),
                                Text(
                                  _statusMessage,
                                  style: TextStyle(color: _statusColor, fontSize: 13, fontWeight: FontWeight.w600),
                                ),
                              ],
                            ),
                          )
                        ] else ...[
                           ElevatedButton(
                            style: ElevatedButton.styleFrom(
                              minimumSize: const Size.fromHeight(52),
                              backgroundColor: const Color(0xFF6366F1),
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                              elevation: 4,
                            ),
                            onPressed: _submitAttendance,
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: const [
                                Icon(Icons.fingerprint_rounded),
                                SizedBox(width: 10),
                                Text(
                                  'MARK CHECK-IN',
                                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 12),
                          ElevatedButton(
                            style: ElevatedButton.styleFrom(
                              minimumSize: const Size.fromHeight(52),
                              backgroundColor: const Color(0xFFEF4444),
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                              elevation: 4,
                            ),
                            onPressed: _submitCheckout,
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: const [
                                Icon(Icons.logout_rounded),
                                SizedBox(width: 10),
                                Text(
                                  'CLOCK OUT',
                                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 30),
              const Text(
                'Requires GPS and Network access. Attendance logs are bound to your device signature.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 11, color: Color(0xFF64748B)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
