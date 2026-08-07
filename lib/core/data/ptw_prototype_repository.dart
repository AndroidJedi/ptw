import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../../models/ptw_prototype_snapshot.dart';

abstract interface class PtwPrototypeRepository {
  Future<PtwPrototypeSnapshot?> load();

  Future<void> save(PtwPrototypeSnapshot snapshot);

  Future<void> reset();
}

/// Prototype-only JSON persistence backed by one versioned preferences value.
final class SharedPreferencesPrototypeRepository
    implements PtwPrototypeRepository {
  SharedPreferencesPrototypeRepository({SharedPreferencesAsync? preferences})
    : _preferences = preferences ?? SharedPreferencesAsync();

  static const snapshotKey = 'ptw.prototype.snapshot.v5';
  static const legacyV4SnapshotKey = 'ptw.prototype.snapshot.v4';
  static const legacyV3SnapshotKey = 'ptw.prototype.snapshot.v3';
  static const legacyV2SnapshotKey = 'ptw.prototype.snapshot.v2';

  final SharedPreferencesAsync _preferences;

  @override
  Future<PtwPrototypeSnapshot?> load() async {
    final raw =
        await _preferences.getString(snapshotKey) ??
        await _preferences.getString(legacyV4SnapshotKey) ??
        await _preferences.getString(legacyV3SnapshotKey) ??
        await _preferences.getString(legacyV2SnapshotKey);
    if (raw == null) return null;
    final json = jsonDecode(raw);
    if (json is! Map<String, dynamic>) {
      throw const FormatException('Prototype snapshot must be a JSON object.');
    }
    return PtwPrototypeSnapshot.fromJson(json);
  }

  @override
  Future<void> save(PtwPrototypeSnapshot snapshot) =>
      _preferences.setString(snapshotKey, jsonEncode(snapshot.toJson()));

  @override
  Future<void> reset() async {
    await _preferences.remove(snapshotKey);
    await _preferences.remove(legacyV4SnapshotKey);
    await _preferences.remove(legacyV3SnapshotKey);
    await _preferences.remove(legacyV2SnapshotKey);
  }
}

/// Deterministic repository used by widget and unit tests.
final class MemoryPrototypeRepository implements PtwPrototypeRepository {
  MemoryPrototypeRepository({PtwPrototypeSnapshot? initial})
    : _snapshot = initial;

  PtwPrototypeSnapshot? _snapshot;

  @override
  Future<PtwPrototypeSnapshot?> load() async => _snapshot;

  @override
  Future<void> save(PtwPrototypeSnapshot snapshot) async {
    _snapshot = PtwPrototypeSnapshot.fromJson(snapshot.toJson());
  }

  @override
  Future<void> reset() async => _snapshot = null;
}
