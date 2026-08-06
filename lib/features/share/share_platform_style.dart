import 'package:flutter/material.dart';

import '../../core/theme/ptw_colors.dart';
import 'share_models.dart';

abstract final class SharePlatformStyle {
  static IconData icon(SharePlatform platform) => switch (platform) {
    SharePlatform.instagramStories ||
    SharePlatform.instagramFeed => Icons.camera_alt_rounded,
    SharePlatform.tiktok => Icons.music_note_rounded,
    SharePlatform.linkedin => Icons.work_rounded,
    SharePlatform.x => Icons.close_rounded,
  };

  static Color color(SharePlatform platform) => switch (platform) {
    SharePlatform.instagramStories ||
    SharePlatform.instagramFeed => PtwColors.instagram,
    SharePlatform.tiktok => PtwColors.tiktok,
    SharePlatform.linkedin => PtwColors.electricBlue,
    SharePlatform.x => PtwColors.ink,
  };
}
