import 'dart:async';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Plays the siren for a critical alarm.
///
/// Two details matter here:
///  * the audio context declares an **alarm** usage, so Android routes it past
///    the media stream and ducks other audio rather than queueing behind it;
///  * volume ramps up over the first few seconds, so a false alarm at 3 a.m.
///    is startling rather than heart-stopping, while a real one still gets
///    loud enough to wake someone.
class AlarmAudio {
  AlarmAudio({AudioPlayer? player}) : _player = player ?? AudioPlayer();

  /// Bundled siren: a 4-second two-tone wail built to loop seamlessly.
  /// Replace `assets/audio/alarm_siren.wav` to change it — and replace
  /// `android/app/src/main/res/raw/alarm_siren.wav` to match, since the
  /// notification channel plays the raw resource rather than the asset.
  static const _sirenAsset = 'audio/alarm_siren.wav';

  static const _rampSteps = <double>[0.35, 0.55, 0.75, 1.0];
  static const _rampInterval = Duration(seconds: 2);

  final AudioPlayer _player;

  bool _isPlaying = false;
  bool _stopRequested = false;

  bool get isPlaying => _isPlaying;

  /// Starts the looping siren with a volume ramp.
  Future<void> startSiren({bool vibrate = true}) async {
    if (_isPlaying) return;
    _isPlaying = true;
    _stopRequested = false;

    try {
      await _player.setAudioContext(_alarmContext());
      await _player.setReleaseMode(ReleaseMode.loop);
      await _player.setVolume(_rampSteps.first);
      await _player.play(AssetSource(_sirenAsset));
    } catch (error) {
      // Audio can fail (no asset, audio focus denied, emulator without audio).
      // The alarm must still be visible and felt, so we carry on to vibration
      // rather than surfacing an error over a safety alert.
      debugPrint('AlarmAudio: siren failed to start — $error');
    }

    if (vibrate) {
      unawaited(_vibrateLoop());
    }
    unawaited(_rampVolume());
  }

  Future<void> _rampVolume() async {
    for (final level in _rampSteps.skip(1)) {
      await Future<void>.delayed(_rampInterval);
      if (_stopRequested || !_isPlaying) return;
      try {
        await _player.setVolume(level);
      } catch (_) {
        return;
      }
    }
  }

  /// Repeating haptic burst for as long as the siren runs.
  Future<void> _vibrateLoop() async {
    while (_isPlaying && !_stopRequested) {
      await HapticFeedback.heavyImpact();
      await Future<void>.delayed(const Duration(milliseconds: 180));
      if (!_isPlaying || _stopRequested) return;
      await HapticFeedback.heavyImpact();
      await Future<void>.delayed(const Duration(milliseconds: 1200));
    }
  }

  /// Short confirmation tone used by the "Test alarm" button, so the user can
  /// check their volume without a 90-second siren.
  Future<void> playTestTone({Duration duration = const Duration(seconds: 4)}) async {
    await startSiren(vibrate: true);
    await Future<void>.delayed(duration);
    await stop();
  }

  Future<void> stop() async {
    _stopRequested = true;
    _isPlaying = false;
    try {
      await _player.stop();
    } catch (_) {
      // Already stopped or never started.
    }
  }

  Future<void> dispose() async {
    await stop();
    await _player.dispose();
  }

  /// Declares the siren as alarm-usage audio on both platforms.
  static AudioContext _alarmContext() {
    return AudioContext(
      android: const AudioContextAndroid(
        isSpeakerphoneOn: true,
        stayAwake: true,
        contentType: AndroidContentType.sonification,
        usageType: AndroidUsageType.alarm,
        audioFocus: AndroidAudioFocus.gainTransientMayDuck,
      ),
      iOS: AudioContextIOS(
        category: AVAudioSessionCategory.playback,
        options: const {
          AVAudioSessionOptions.duckOthers,
          AVAudioSessionOptions.defaultToSpeaker,
        },
      ),
    );
  }
}
