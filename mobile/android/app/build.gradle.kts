plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Firebase Cloud Messaging is applied only when its configuration file is
// present, so the app still builds and runs without a Firebase project — the
// alarm falls back to polling. See docs/FIREBASE_SETUP.md.
//
// Applying it unconditionally would fail the build with "File
// google-services.json is missing" on every machine that has not set Firebase
// up, which would make push a hard dependency of a feature designed to work
// without it.
val googleServicesConfig = file("google-services.json")
if (googleServicesConfig.exists()) {
    apply(plugin = "com.google.gms.google-services")
    logger.lifecycle("Firebase: google-services.json found — push enabled.")
} else {
    logger.lifecycle(
        "Firebase: no google-services.json — building without push. " +
            "Alarms will run on polling only. See docs/FIREBASE_SETUP.md."
    )
}

android {
    namespace = "za.co.neighbourhoodwatch.nhw_mobile"
    // permission_handler_android requires compileSdk >= 37; flutter.compileSdkVersion
    // resolves to 36 with AGP 9.1, so we pin explicitly.
    compileSdk = 37
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        // flutter_local_notifications uses java.time APIs that require desugaring
        // on Android < 26.
        isCoreLibraryDesugaringEnabled = true
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "za.co.neighbourhoodwatch.nhw_mobile"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}
