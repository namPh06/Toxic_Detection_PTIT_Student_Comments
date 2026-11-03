"""Reproducible ViSoBERT fine-tuning; labels and split selection stay external."""
import html
import json
import re
import time
import unicodedata
from pathlib import Path

from dataset import LABELS, atomic_json

MODEL_ID = 'uitnlp/visobert'


def normalize_input(text):
    # Preserve punctuation, negation, slang and emoji for the pretrained tokenizer.
    text = unicodedata.normalize('NFC', html.unescape(str(text or '')))
    text = re.sub(r'https?://\S+|www\.\S+', ' urltoken ', text)
    text = re.sub(r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b', ' emailtoken ', text)
    return re.sub(r'\s+', ' ', text).strip()


def validate_config(config=None):
    result = dict(epochs=4, max_length=128, batch_size=8, accumulation=2,
                  learning_rate=2e-5, head_learning_rate=5e-4, patience=2, seed=42,
                  cpu_layers=2, balanced=True)
    supplied = config or {}
    if not isinstance(supplied, dict) or set(supplied) - set(result):
        raise ValueError('Cấu hình ViSoBERT không hợp lệ.')
    result.update(supplied)
    for key, low, high in [('epochs', 1, 20), ('max_length', 16, 512), ('batch_size', 1, 64),
                            ('accumulation', 1, 32), ('patience', 1, 20), ('cpu_layers', 1, 12), ('seed', 0, 2**31-1)]:
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError('Cấu hình ViSoBERT không hợp lệ: ' + key)
    for key in ('learning_rate', 'head_learning_rate'):
        if isinstance(result[key], bool) or not isinstance(result[key], (int, float)) or not 0 < result[key] < 1:
            raise ValueError('Tốc độ học ViSoBERT không hợp lệ.')
    if type(result['balanced']) is not bool:
        raise ValueError('Trọng số lớp ViSoBERT không hợp lệ.')
    return result


def download_base(directory, notify=print):
    """Download one pinned revision into the ignored project-local model cache."""
    from huggingface_hub import HfApi, snapshot_download
    directory = Path(directory)
    source = directory / 'source.json'
    if source.exists():
        info = json.loads(source.read_text(encoding='utf-8'))
        if (directory / 'config.json').exists() and any((directory / f).exists() for f in ('model.safetensors', 'pytorch_model.bin')):
            return info
    notify('Đang tải ViSoBERT và khóa revision nguồn…')
    info = HfApi().model_info(MODEL_ID, timeout=30)
    names = {s.rfilename for s in info.siblings}
    weights = 'model.safetensors' if 'model.safetensors' in names else 'pytorch_model.bin'
    snapshot_download(MODEL_ID, revision=info.sha, local_dir=directory,
                      allow_patterns=['config.json', weights, 'tokenizer*', 'special_tokens_map.json',
                                      'sentencepiece.bpe.model', 'added_tokens.json'], max_workers=2)
    metadata = dict(model=MODEL_ID, revision=info.sha, weights=weights)
    atomic_json(source, metadata)
    return metadata


def token_batches(tokenizer, texts, batch_size, max_length):
    for offset in range(0, len(texts), batch_size):
        yield tokenizer([normalize_input(t) for t in texts[offset:offset + batch_size]],
                        padding=True, truncation=True, max_length=max_length, return_tensors='pt')


def score_transformer(model, tokenizer, texts, max_length=128, batch_size=16):
    import torch
    model.eval()
    device = next(model.parameters()).device
    scores = []
    with torch.inference_mode():
        for batch in token_batches(tokenizer, texts, batch_size, max_length):
            logits = model(**{k: v.to(device) for k, v in batch.items()}).logits
            scores.extend(logits.softmax(dim=1)[:, 1].cpu().tolist())
    return scores


def train_transformer(train_text, train_y, val_text, val_y, base_directory, output,
                      notify=print, config=None):
    import numpy as np
    import torch
    from sklearn.metrics import f1_score
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, set_seed

    config = validate_config(config)
    source = download_base(base_directory, notify)
    set_seed(config['seed'])
    torch.set_num_threads(2)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    tokenizer = AutoTokenizer.from_pretrained(base_directory, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        base_directory, local_files_only=True, num_labels=2,
        id2label=dict(enumerate(LABELS)), label2id={label: i for i, label in enumerate(LABELS)})
    if device.type == 'cpu':
        for parameter in model.base_model.parameters():
            parameter.requires_grad = False
        for layer in model.base_model.encoder.layer[-config['cpu_layers']:]:
            for parameter in layer.parameters():
                parameter.requires_grad = True
    model.to(device)
    groups = [dict(params=[p for p in model.base_model.parameters() if p.requires_grad], lr=config['learning_rate']),
              dict(params=model.classifier.parameters(), lr=config['head_learning_rate'])]
    optimizer = torch.optim.AdamW(groups, weight_decay=0.01)
    labels = torch.tensor(train_y, dtype=torch.long, device=device)
    weights = len(labels) / (2 * torch.bincount(labels, minlength=2).float()) if config['balanced'] else None
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)
    encoded = tokenizer([normalize_input(t) for t in train_text], truncation=True, max_length=config['max_length'])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(output)
    best_score, best_epoch, history = -1, 0, []
    started = time.monotonic()
    for epoch in range(config['epochs']):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        chunks = list(torch.randperm(len(labels)).split(config['batch_size']))
        total = 0.0
        for step, indexes in enumerate(chunks):
            records = [{k: v[int(i)] for k, v in encoded.items()} for i in indexes]
            batch = tokenizer.pad(records, padding=True, return_tensors='pt')
            logits = model(**{k: v.to(device) for k, v in batch.items()}).logits
            loss = loss_fn(logits, labels[indexes.to(device)])
            total += loss.item() * len(indexes)
            window_size = min(config['accumulation'], len(chunks) - (step // config['accumulation']) * config['accumulation'])
            (loss / window_size).backward()
            if (step + 1) % config['accumulation'] == 0 or step + 1 == len(chunks):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
            if step % 25 == 0:
                notify(f'ViSoBERT: epoch {epoch+1}/{config["epochs"]}, batch {step+1}/{len(chunks)} ({device.type})')
        scores = score_transformer(model, tokenizer, val_text, config['max_length'])
        score = float(f1_score(val_y, np.asarray(scores) >= 0.5, average='macro', zero_division=0))
        history.append(dict(epoch=epoch+1, loss=total/len(labels), val_f1_macro=score))
        notify(f'ViSoBERT: epoch {epoch+1}, validation macro-F1 = {score:.4f}')
        if score > best_score:
            best_score, best_epoch = score, epoch+1
            model.save_pretrained(output, safe_serialization=True)
        if epoch+1-best_epoch >= config['patience']:
            break
    # Restore the checkpoint chosen without consulting test labels.
    del optimizer, model
    model = AutoModelForSequenceClassification.from_pretrained(output, local_files_only=True).to(device)
    metadata = dict(source=source, config=config, device=device.type, input='raw_unicode_v1',
                    fine_tuning='last_two_encoder_layers_and_head' if device.type == 'cpu' and config['cpu_layers'] == 2 else
                    f'last_{config["cpu_layers"]}_encoder_layers_and_head' if device.type == 'cpu' else 'full_encoder_and_head',
                    best_epoch=best_epoch, history=history, seconds=round(time.monotonic()-started, 3))
    atomic_json(output / 'training.json', metadata)
    return model, tokenizer, metadata


def predict_transformer(directory, texts):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    directory = Path(directory)
    metadata = json.loads((directory / 'training.json').read_text(encoding='utf-8'))
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(directory, local_files_only=True)
    return score_transformer(model, tokenizer, texts, metadata['config']['max_length'])
