pluginManagement {
    val flutterSdkPath =
        run {
            val properties = java.util.Properties()
            file("local.properties").inputStream().use { properties.load(it) }
            val flutterSdkPath = properties.getProperty("flutter.sdk")
            require(flutterSdkPath != null) { "flutter.sdk not set in local.properties" }
            flutterSdkPath
        }

    includeBuild("$flutterSdkPath/packages/flutter_tools/gradle")

    repositories {
        google()
        mavenCentral()
        // repo1.maven.org is Maven Central's alternate hostname — the JVM
        // resolves repo.maven.apache.org unreliably on this machine so we
        // list the mirror explicitly as a fallback.
        maven { url = uri("https://repo1.maven.org/maven2/") }
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://repo1.maven.org/maven2/") }
    }
}

plugins {
    id("dev.flutter.flutter-plugin-loader") version "1.0.0"
    id("com.android.application") version "9.1.0" apply false
    id("org.jetbrains.kotlin.android") version "2.4.0" apply false
    // Reads android/app/google-services.json and generates the Firebase
    // configuration the SDK looks for at runtime. Declared here, applied in
    // app/build.gradle.kts. Flutter does not add this for you.
    id("com.google.gms.google-services") version "4.4.2" apply false
}

include(":app")
