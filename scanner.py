import os
import imagehash
from PIL import Image
from datetime import datetime

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif', '.tiff', '.tif'}


def scan_folder(folder_path):
    """Percorre a pasta recursivamente e retorna lista de caminhos de imagens."""
    folder_path = os.path.normpath(folder_path)
    image_paths = []
    for root, _, files in os.walk(folder_path):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                image_paths.append(os.path.join(root, filename))
    return image_paths


def get_image_metadata(filepath):
    """Retorna metadados de uma imagem."""
    stat = os.stat(filepath)
    size_bytes = stat.st_size
    modified = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')

    try:
        with Image.open(filepath) as img:
            width, height = img.size
    except Exception:
        width, height = 0, 0

    if size_bytes >= 1_048_576:
        size_str = f"{size_bytes / 1_048_576:.1f} MB"
    else:
        size_str = f"{size_bytes / 1024:.0f} KB"

    return {
        'path': filepath,
        'filename': os.path.basename(filepath),
        'size_bytes': size_bytes,
        'size': size_str,
        'width': width,
        'height': height,
        'resolution': f"{width}x{height}",
        'modified': modified,
    }


def compute_hashes(image_paths):
    """Calcula o hash perceptual (pHash) de cada imagem."""
    results = []
    for path in image_paths:
        try:
            with Image.open(path) as img:
                phash = imagehash.phash(img)
            results.append((path, phash))
        except Exception:
            continue
    return results


def find_similar_groups(hashed_images, threshold=10):
    """Agrupa imagens similares com base na distância de Hamming."""
    used = set()
    groups = []

    for i, (path_a, hash_a) in enumerate(hashed_images):
        if i in used:
            continue
        group = [path_a]
        used.add(i)

        for j, (path_b, hash_b) in enumerate(hashed_images):
            if j in used:
                continue
            if hash_a - hash_b <= threshold:
                group.append(path_b)
                used.add(j)

        if len(group) > 1:
            groups.append(group)

    return groups


def scan_and_find_duplicates(folder_path, threshold=10):
    """Pipeline completo: scan -> hash -> agrupar -> metadados."""
    image_paths = scan_folder(folder_path)
    hashed = compute_hashes(image_paths)
    groups = find_similar_groups(hashed, threshold)

    result = []
    for group_paths in groups:
        group_data = [get_image_metadata(p) for p in group_paths]
        group_data.sort(key=lambda x: x['size_bytes'], reverse=True)
        result.append(group_data)

    return result, len(image_paths)
