"""Pretrained Vietnamese Word2Vec, filtered to the training vocabulary."""
import hashlib
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np

from dataset import word_tokens

SOURCE_NAME = 'PhoW2V_words_100dims'
SOURCE_URL = 'https://github.com/datquocnguyen/PhoW2V'
DOWNLOAD_URL = ('https://drive.usercontent.google.com/download?'
                'id=11u9vJTaVBgB7z-eucBqvWJi3bYq4OgIw&export=download&confirm=t')
ARCHIVE_SIZE = 785783878
DEFAULT_PATH = Path(__file__).parent / 'models' / 'word2vec' / (SOURCE_NAME + '.zip')


def ensure_word2vec(notify=lambda message: None):
    """Cache the author's public mirror; failed downloads never replace the cache."""
    if DEFAULT_PATH.is_file() and DEFAULT_PATH.stat().st_size == ARCHIVE_SIZE:
        try:
            with zipfile.ZipFile(DEFAULT_PATH) as archive:
                archive.getinfo('word2vec_vi_words_100dims.txt')
        except (zipfile.BadZipFile, KeyError):
            notify('Tệp PhoW2V trên máy không hợp lệ. Đang tải lại…')
        else:
            notify('Đã có PhoW2V trên máy. Dùng lại tệp đã tải…')
            return DEFAULT_PATH
    DEFAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = DEFAULT_PATH.with_suffix('.zip.tmp')
    try:
        notify('Đang tải PhoW2V: 0 / 786 MB (chỉ tải lần đầu)…')
        received, last_notice = 0, time.monotonic()
        with urllib.request.urlopen(DOWNLOAD_URL, timeout=60) as response, temporary.open('wb') as stream:
            if 'text/html' in response.headers.get('Content-Type', ''):
                raise ValueError('Nguồn tải chưa trả về tệp Word2Vec. Hãy bấm trích xuất lại để thử tải lại.')
            while chunk := response.read(1024 * 1024):
                received += len(chunk)
                if received > ARCHIVE_SIZE:
                    raise ValueError('Tệp tải về lớn hơn phiên bản PhoW2V đã chọn.')
                stream.write(chunk)
                if time.monotonic() - last_notice >= 2:
                    notify(f'Đang tải PhoW2V: {received / 1e6:.0f} / 786 MB ({received / ARCHIVE_SIZE:.0%})…')
                    last_notice = time.monotonic()
        if received != ARCHIVE_SIZE:
            raise ValueError('Tải PhoW2V chưa đầy đủ. Hãy thử lại.')
        notify('Đã tải PhoW2V: 786 / 786 MB (100%). Đang kiểm tra tệp…')
        with zipfile.ZipFile(temporary) as archive:
            archive.getinfo('word2vec_vi_words_100dims.txt')
        temporary.replace(DEFAULT_PATH)
        return DEFAULT_PATH
    except (urllib.error.URLError, TimeoutError) as error:
        raise ValueError('Không tải được PhoW2V. Kiểm tra kết nối Internet rồi bấm trích xuất lại; công cụ sẽ tự tải lại.') from error
    finally:
        temporary.unlink(missing_ok=True)


def lookup_form(token):
    """PhoW2V tone placement; keep the original Underthesea tokens unchanged."""
    token = unicodedata.normalize('NFC', token).lower()
    for old, new in [('òa', 'oà'), ('óa', 'oá'), ('ỏa', 'oả'), ('õa', 'oã'), ('ọa', 'oạ'),
                     ('òe', 'oè'), ('óe', 'oé'), ('ỏe', 'oẻ'), ('õe', 'oẽ'), ('ọe', 'oẹ'),
                     ('ùy', 'uỳ'), ('úy', 'uý'), ('ủy', 'uỷ'), ('ũy', 'uỹ'), ('ụy', 'uỵ')]:
        token = token.replace(old, new)
    return token


def prepare_embeddings(train_texts, path='', trainable=True, notify=lambda message: None):
    """Stream text-format Word2Vec; retain only train words, never learn on test."""
    counts = Counter(token for text in train_texts for token in word_tokens(text))
    vocabulary = {token: index + 2 for index, (token, _) in enumerate(counts.most_common(20000))}
    source = Path(path).expanduser() if path else ensure_word2vec(notify)
    if not source.is_file():
        raise ValueError('Không tìm thấy tệp Word2Vec. Kiểm tra đường dẫn .txt, .vec hoặc .zip.')
    notify('Đang đọc Word2Vec và ghép vector với từ vựng train…')
    wanted = {}
    for token, index in vocabulary.items():
        wanted.setdefault(lookup_form(token), []).append(index)
    digest = hashlib.sha256()
    found = set()

    def read_vectors(stream):
        header = stream.readline()
        digest.update(header)
        try:
            total, dimensions = map(int, header.decode('utf-8-sig').split())
        except (ValueError, UnicodeError) as error:
            raise ValueError('Cần Word2Vec dạng văn bản, dòng đầu gồm số từ và số chiều. Không hỗ trợ .bin.') from error
        if not 1 <= total <= 10000000 or not 1 <= dimensions <= 2048:
            raise ValueError('Kích thước Word2Vec không hợp lệ.')
        weights = np.random.default_rng(42).normal(0, 0.05, (len(vocabulary) + 2, dimensions)).astype(np.float32)
        weights[0] = 0
        read_count = 0
        for line in stream:
            digest.update(line)
            if not line.strip():
                continue
            read_count += 1
            raw_token, separator, raw_values = line.partition(b' ')
            token = lookup_form(raw_token.decode('utf-8'))
            indexes = wanted.get(token)
            if indexes:
                vector = np.fromstring(raw_values.decode('ascii'), sep=' ', dtype=np.float32)
                if not separator or len(vector) != dimensions or not np.isfinite(vector).all():
                    raise ValueError(f'Vector Word2Vec không hợp lệ cho từ {token}.')
                for index in indexes:
                    if index not in found:
                        weights[index] = vector
                        found.add(index)
            if read_count % 100000 == 0:
                notify(f'Đang đọc Word2Vec: {read_count:,} / {total:,} từ…')
        if read_count != total:
            raise ValueError('Tệp Word2Vec không đầy đủ hoặc số từ không khớp dòng đầu.')
        if not found:
            raise ValueError('Không có từ train nào khớp Word2Vec. Kiểm tra ngôn ngữ và cách tách từ của tệp.')
        return weights, dimensions

    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            members = [item for item in archive.infolist() if not item.is_dir() and item.filename.endswith(('.txt', '.vec'))]
            if len(members) != 1:
                raise ValueError('Tệp ZIP cần chứa đúng một tệp vector .txt hoặc .vec.')
            with archive.open(members[0]) as stream:
                weights, dimensions = read_vectors(stream)
    else:
        with source.open('rb') as stream:
            weights, dimensions = read_vectors(stream)
    total_tokens = sum(counts[token] for token in vocabulary)
    matched_tokens = sum(counts[token] for token, index in vocabulary.items() if index in found)
    return dict(vocabulary=vocabulary, weights=weights, matched=sorted(found),
                metadata=dict(source=SOURCE_NAME if not path else source.name,
                              source_url=SOURCE_URL if not path else '', sha256=digest.hexdigest(),
                              dimensions=dimensions, trainable=trainable, vocabulary_size=len(vocabulary),
                              matched_words=len(found), oov_words=len(vocabulary) - len(found),
                              word_coverage=len(found) / len(vocabulary),
                              token_coverage=matched_tokens / total_tokens,
                              vocabulary_limit=20000, max_length=128))
