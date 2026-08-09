import 'dart:io';

import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';

import '../../models/ptw_image_ref.dart';

enum PtwShareImagePurpose { layer, background, decoration }

typedef PtwGalleryImagePicker =
    Future<XFile?> Function({
      required double maxWidth,
      required double maxHeight,
      required int? imageQuality,
    });

final class PtwMediaException implements Exception {
  const PtwMediaException(this.message);

  final String message;

  @override
  String toString() => message;
}

abstract interface class PtwMediaService {
  Future<void> initialize();

  Future<PtwImageRef?> pickProjectImage();

  Future<PtwImageRef?> pickShareImage(PtwShareImagePurpose purpose);

  Future<PtwImageRef?> recoverLostProjectImage();

  String resolveFilePath(PtwImageRef image);
}

/// Imports selected gallery files into durable application-owned storage.
final class LocalPtwMediaService implements PtwMediaService {
  LocalPtwMediaService({
    ImagePicker? picker,
    PtwGalleryImagePicker? galleryPicker,
    Directory? documentsDirectory,
  }) : _picker = picker ?? ImagePicker(),
       _galleryPicker = galleryPicker {
    _documents = documentsDirectory;
    if (documentsDirectory != null) {
      _mediaDirectory = Directory('${documentsDirectory.path}/ptw_media');
    }
  }

  final ImagePicker _picker;
  final PtwGalleryImagePicker? _galleryPicker;
  static const maximumShareImageBytes = 10 * 1024 * 1024;
  Directory? _documents;
  Directory? _mediaDirectory;

  @override
  Future<void> initialize() async {
    _documents ??= await getApplicationDocumentsDirectory();
    _mediaDirectory ??= Directory('${_documents!.path}/ptw_media');
    await _mediaDirectory!.create(recursive: true);
  }

  @override
  Future<PtwImageRef?> pickProjectImage() async {
    final selected = await _pickFromGallery(
      maxWidth: 1800,
      maxHeight: 1800,
      imageQuality: 90,
    );
    return selected == null ? null : _persist(selected);
  }

  @override
  Future<PtwImageRef?> pickShareImage(PtwShareImagePurpose purpose) async {
    final preserveTransparency = purpose == PtwShareImagePurpose.decoration;
    final selected = await _pickFromGallery(
      maxWidth: 2048,
      maxHeight: 2048,
      imageQuality: preserveTransparency ? null : 90,
    );
    if (selected == null) return null;
    final extension = _extension(selected.path);
    if (!{'.png', '.jpg', '.jpeg', '.webp'}.contains(extension)) {
      throw const PtwMediaException('Choose a PNG, JPEG, or WebP image.');
    }
    final length = await selected.length();
    if (length <= 0) {
      throw const PtwMediaException('That image is empty.');
    }
    if (length > maximumShareImageBytes) {
      throw const PtwMediaException('Choose an image smaller than 10 MB.');
    }
    return _persist(selected, prefix: 'share');
  }

  Future<XFile?> _pickFromGallery({
    required double maxWidth,
    required double maxHeight,
    required int? imageQuality,
  }) {
    final custom = _galleryPicker;
    if (custom != null) {
      return custom(
        maxWidth: maxWidth,
        maxHeight: maxHeight,
        imageQuality: imageQuality,
      );
    }
    return _picker.pickImage(
      source: ImageSource.gallery,
      maxWidth: maxWidth,
      maxHeight: maxHeight,
      imageQuality: imageQuality,
    );
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

  Future<PtwImageRef> _persist(
    XFile selected, {
    String prefix = 'project',
  }) async {
    if (_documents == null || _mediaDirectory == null) await initialize();
    await _mediaDirectory!.create(recursive: true);
    final candidate = _extension(selected.path);
    final extension =
        RegExp(r'^\.[a-z0-9]{1,5}$').hasMatch(candidate) ? candidate : '.jpg';
    final name = '${prefix}_${DateTime.now().microsecondsSinceEpoch}$extension';
    await File(selected.path).copy('${_mediaDirectory!.path}/$name');
    return PtwImageRef.file('ptw_media/$name');
  }

  String _extension(String path) {
    final dot = path.lastIndexOf('.');
    return dot < 0 ? '' : path.substring(dot).toLowerCase();
  }

  @override
  String resolveFilePath(PtwImageRef image) {
    if (image.source != PtwImageSource.file || _documents == null) {
      return image.path;
    }
    return '${_documents!.path}/${image.path}';
  }
}
