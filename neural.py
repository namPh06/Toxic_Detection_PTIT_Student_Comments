"""Small CPU TextCNN with train-only vocabulary and optional pretrained vectors."""
from collections import Counter
from dataset import word_tokens

import torch
from torch import nn

MAX_LENGTH = 128


def compute_info():
    return (dict(device='cuda', name=torch.cuda.get_device_name(0)) if torch.cuda.is_available()
            else dict(device='cpu', name='CPU'))


class TextCNN(nn.Module):
    def __init__(self, vocabulary_size, embedding_weights=None, trainable=True, embedding_dim=64,
                 filters=48, dropout=0.3):
        super().__init__()
        if embedding_weights is None:
            self.embedding = nn.Embedding(vocabulary_size, embedding_dim, padding_idx=0)
        else:
            weights = torch.as_tensor(embedding_weights, dtype=torch.float32).clone()
            if weights.ndim != 2 or weights.shape[0] != vocabulary_size:
                raise ValueError('Kích thước embedding không khớp từ vựng TextCNN.')
            embedding_dim = weights.shape[1]
            self.embedding = nn.Embedding.from_pretrained(weights, freeze=not trainable, padding_idx=0)
        self.convs = nn.ModuleList(nn.Conv1d(embedding_dim, filters, kernel) for kernel in (2, 3, 4))
        self.dropout = nn.Dropout(dropout)
        self.output = nn.Linear(filters * 3, 2)

    def forward(self, tokens):
        embedded = self.embedding(tokens).transpose(1, 2)
        features = torch.cat([torch.relu(conv(embedded)).amax(dim=2) for conv in self.convs], dim=1)
        return self.output(self.dropout(features))


def encode(texts, vocabulary):
    # shortcut: truncate at 128 tokens, revisit with length-distribution analysis for longer comments.
    encoded = torch.zeros((len(texts), MAX_LENGTH), dtype=torch.long)
    for i, text in enumerate(texts):
        ids = [vocabulary.get(t, 1) for t in word_tokens(text)[:MAX_LENGTH]]
        encoded[i, :len(ids)] = torch.tensor(ids, dtype=torch.long)
    return encoded


def train_cnn(train_text, train_y, val_text, val_y, notify, epochs=12, prepared_embedding=None, config=None):
    from sklearn.metrics import f1_score
    torch.manual_seed(42)
    torch.set_num_threads(2)
    device = torch.device(compute_info()['device'])
    notify(f'TextCNN: huấn luyện trên {device}')
    config = dict(config or {})
    filters, dropout = config.get('filters', 48), config.get('dropout', 0.3)
    if prepared_embedding:
        vocabulary = prepared_embedding['vocabulary']
        model = TextCNN(len(vocabulary) + 2, prepared_embedding['weights'],
                        config.get('trainable', prepared_embedding['metadata']['trainable']),
                        filters=filters, dropout=dropout)
    else:
        vocabulary = {word: i + 2 for i, (word, _) in enumerate(
            Counter(token for text in train_text for token in word_tokens(text)).most_common(20000))}
        model = TextCNN(len(vocabulary) + 2, filters=filters, dropout=dropout)
    train_x, val_x = encode(train_text, vocabulary), encode(val_text, vocabulary)
    model.to(device)
    labels = torch.tensor(train_y, dtype=torch.long, device=device)
    counts = torch.bincount(labels, minlength=2).float()
    loss_fn = nn.CrossEntropyLoss(weight=len(labels) / (2 * counts) if config.get('balanced', True) else None)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.get('learning_rate', 0.001),
                                 weight_decay=config.get('weight_decay', 0.0))
    best_score, best_state, best_epoch, history = -1, None, 0, []
    for epoch in range(epochs):
        model.train()
        total = 0.0
        for indexes in torch.randperm(len(train_x)).split(32):
            optimizer.zero_grad()
            loss = loss_fn(model(train_x[indexes].to(device)), labels[indexes.to(device)])
            loss.backward()
            optimizer.step()
            total += loss.item() * len(indexes)
        predictions = predict_cnn(model, val_x)
        score = f1_score(val_y, predictions, average='macro', zero_division=0)
        history.append(dict(epoch=epoch + 1, loss=total / len(labels), val_f1_macro=float(score)))
        notify(f'TextCNN: epoch {epoch + 1}/{epochs}, validation macro-F1 = {score:.3f}')
        if score > best_score:
            best_score, best_epoch = score, epoch + 1
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        if config.get('patience') and epoch + 1 - best_epoch >= config['patience']:
            break
    model.load_state_dict(best_state)
    model.eval()
    return model, vocabulary, history, best_epoch


def predict_cnn(model, encoded):
    model.eval()
    device = next(model.parameters()).device
    with torch.no_grad():
        return torch.cat([model(batch.to(device)).argmax(dim=1).cpu() for batch in encoded.split(64)]).tolist()


def score_cnn(model, encoded):
    model.eval()
    device = next(model.parameters()).device
    with torch.no_grad():
        return torch.cat([model(batch.to(device)).softmax(dim=1)[:, 1].cpu() for batch in encoded.split(64)]).tolist() if len(encoded) else []
