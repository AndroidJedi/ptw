import 'dart:io';

import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';

import '../../models/ptw_image_ref.dart';

abstract interface class PtwMediaService {
  Future<void> initialize();

  Future<PtwImageRef?> pickProjectImage();

  Future<PtwImageRef?> recoverLostProjectImage();

  String resolveFilePath(PtwImageRef image);
}

/// Imports selected gallery files into durable application-owned storage.
final class LocalPtwMediaService implements PtwMediaService {
  LocalPtwMediaService({ImagePicker? picker})
    : _picker = picker ?? ImagePicker();

  final ImagePicker _picker;
  Directory? _documents;
  Directory? _mediaDirectory;

  @override
  Future<void> initialize() async {
    _documents = await getApplicationDocumentsDirectory();
    _mediaDirectory = Directory('${_documents!.path}/ptw_media');
    await _mediaDirectory!.create(recursive: true);
  }

  @override
  Future<PtwImageRef?> pickProjectImage() async {
    final selected = await _picker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 1800,
      imageQuality: 90,
    );
    return selected == null ? null : _persist(selected);
  }

  @override
  Future<PtwImageRef?> recoverLostProjectImage() async {
    try {
      final response = await _picker.retrieveLostData();
      final files = response.files;
      if (files == null || files.isEmpty) return null;
      return _persist(files.first);
    } on Exception {
      return null;
    }
  }

  Future<PtwImageRef> _persist(XFile selected) async {
    if (_documents == null || _mediaDirectory == null) await initialize();
    final dot = selected.path.lastIndexOf('.');
    final candidate = dot < 0 ? '' : selected.path.substring(dot).toLowerCase();
    final extension =
        RegExp(r'^\.[a-z0-9]{1,5}$').hasMatch(candidate) ? candidate : '.jpg';
    final name = 'project_${DateTime.now().microsecondsSinceEpoch}$extension';
    await File(selected.path).copy('${_mediaDirectory!.path}/$name');
    return PtwImageRef.file('ptw_media/$name');
  }

  @override
  String resolveFilePath(PtwImageRef image) {
    if (image.source != PtwImageSource.file || _documents == null) {
      return image.path;
    }
    return '${_documents!.path}/${image.path}';
  }
}
