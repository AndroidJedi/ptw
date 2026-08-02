abstract final class PtwFormatters {
  static const _months = <String>[
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];

  static String deadline(DateTime value) =>
      'by ${_months[value.month - 1]} ${value.day}, ${value.year}';

  static String relative(DateTime value, {DateTime? now}) {
    final difference = (now ?? DateTime.now()).difference(value);
    if (difference.inMinutes < 1) return 'Just now';
    if (difference.inHours < 1) return '${difference.inMinutes}m';
    if (difference.inDays < 1) return '${difference.inHours}h';
    if (difference.inDays < 7) return '${difference.inDays}d';
    return '${_months[value.month - 1]} ${value.day}';
  }
}
