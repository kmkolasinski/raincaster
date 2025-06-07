# Raincaster

Raincaster is a mobile application built with Kivy and KivyMD for weather forecasting and
rain prediction.

## Features

- Rain radar
- Modern UI with KivyMD

## Installation

1. **Install dependencies:**
   - Ensure you have Python 3.7+ installed.
   - Install Kivy and KivyMD:
     ```bash
     pip install ."[dev,android]"
     ```
   - Install Buildozer (for Android builds):
     ```bash
     pip install buildozer
     ```

2. **(Optional) Set up Android SDK/NDK:**
   - Follow [Kivy's Android packaging guide](https://kivy.org/doc/stable/guide/packaging-android.html#packaging-android) if building for Android.

## Build & Run Commands

- **List connected Android devices:**
  ```bash
  adb devices
  ```

- **Clean previous builds:**
  ```bash
  buildozer appclean
  buildozer -v android clean
  ```

- **Build, deploy, and run (debug):**
  ```bash
  buildozer android debug deploy run logcat
  buildozer android debug deploy run
  ```

- **Build, deploy, and run (release):**
  ```bash
  BUILDOZER_ALLOW_ORG_TEST_DOMAIN=1 buildozer android release deploy run
  ```

## Resources

- [Kivy Android Packaging Guide](https://kivy.org/doc/stable/guide/packaging-android.html#packaging-android)
- [KivyMD DropDownMenu Documentation](https://github.com/kivymd/KivyMD/wiki/Components-DropDownMenu)
