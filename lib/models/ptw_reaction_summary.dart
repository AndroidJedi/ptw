final class PtwReactionSummary {
  const PtwReactionSummary({required this.believe, required this.doubt});

  final int believe;
  final int doubt;

  int get total => believe + doubt;

  double get believeFraction => total == 0 ? 0 : believe / total;

  double get doubtFraction => total == 0 ? 0 : doubt / total;
}
