package com.roofingbusiness.app

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugins.GeneratedPluginRegistrant
import android.os.Build
import android.os.Bundle

class MainActivity: FlutterActivity() {
    private val CHANNEL = "com.roofingbusiness.app/native"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        GeneratedPluginRegistrant.registerWith(flutterEngine)

        // Set up method channel for native functionality
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler {
            call, result ->
            when (call.method) {
                "getDeviceInfo" -> {
                    val deviceInfo = mapOf(
                        "model" to Build.MODEL,
                        "brand" to Build.BRAND,
                        "manufacturer" to Build.MANUFACTURER,
                        "version" to Build.VERSION.RELEASE,
                        "sdkInt" to Build.VERSION.SDK_INT
                    )
                    result.success(deviceInfo)
                }
                "getAndroidVersion" -> {
                    result.success(Build.VERSION.RELEASE)
                }
                else -> {
                    result.notImplemented()
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Handle notification intent
        handleNotificationIntent()
    }

    private fun handleNotificationIntent() {
        // Handle any notification taps that open the app
        val notificationData = intent.extras
        if (notificationData != null) {
            // Process notification data here
            // This can be used to navigate to specific screens when app opens from notification
        }
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        handleNotificationIntent()
    }
}