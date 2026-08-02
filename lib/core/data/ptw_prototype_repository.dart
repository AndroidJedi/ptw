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

  static const snapshotKey = 'ptw.prototype.snapshot.v2';

  final SharedPreferencesAsync _preferences;

  @override
  Future<PtwPrototypeSnapshot?> load() async {
    final raw = await _preferences.getString(snapshotKey);
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
  Future<void> reset() => _preferences.remove(snapshotKey);
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
