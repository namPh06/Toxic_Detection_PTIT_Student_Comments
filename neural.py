"""Small CPU TextCNN; vocabulary and embeddings are learned on train only."""
from collections import Counter

import torch
from torch import nn

MAX_LENGTH = 128


class TextCNN(nn.Module):
    def __init__(self, vocabulary_size):
        super().__init__()
        self.embedding = nn.Embedding(vocabulary_size, 64, padding_idx=0)
        self.convs = nn.ModuleList(nn.Conv1d(64, 48, kernel) for kernel in (2, 3, 4))
        self.dropout = nn.Dropout(0.3)
        self.output = nn.Linear(144, 2)

    def forward(self, tokens):
        embedded = self.embedding(tokens).transpose(1, 2)
        features = torch.cat([torch.relu(conv(embedded)).amax(dim=2) for conv in self.convs], dim=1)
        return self.output(self.dropout(features))


def encode(texts, vocabulary):
    # shortcut: truncate at 128 tokens, revisit with length-distribution analysis for longer comments.
    encoded = torch.zeros((len(texts), MAX_LENGTH), dtype=torch.long)
    for i, text in enumerate(texts):
        ids = [vocabulary.get(t, 1) for t in text.split()[:MAX_LENGTH]]
        encoded[i, :len(ids)] = torch.tensor(ids, dtype=torch.long)
    return encoded


def train_cnn(train_text, train_y, val_text, val_y, notify, epochs=12):
    from sklearn.metrics import f1_score
    torch.manual_seed(42)
    torch.set_num_threads(2)
    vocabulary = {word: i + 2 for i, (word, _) in enumerate(Counter(' '.join(train_text).split()).most_common(20000))}
    model = TextCNN(len(vocabulary) + 2)
    train_x, val_x = encode(train_text, vocabulary), encode(val_text, vocabulary)
    labels = torch.tensor(train_y, dtype=torch.long)
    counts = torch.bincount(labels, minlength=2).float()
    loss_fn = nn.CrossEntropyLoss(weight=len(labels) / (2 * counts))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    best_score, best_state, best_epoch, history = -1, None, 0, []
    for epoch in range(epochs):
        model.train()
        total = 0.0
        for indexes in torch.randperm(len(train_x)).split(32):
            optimizer.zero_grad()
            loss = loss_fn(model(train_x[indexes]), labels[indexes])
            loss.backward()
            optimizer.step()
            total += loss.item() * len(indexes)
        predictions = predict_cnn(model, val_x)
        score = f1_score(val_y, predictions, average='macro', zero_division=0)
        history.append(dict(epoch=epoch + 1, loss=total / len(labels), val_f1_macro=float(score)))
        notify(f'TextCNN: epoch {epoch + 1}/{epochs}, validation macro-F1 = {score:.3f}')
        if score > best_score:
            best_score, best_epoch = score, epoch + 1
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    model.eval()
    return model, vocabulary, history, best_epoch


def predict_cnn(model, encoded):
    model.eval()
    with torch.no_grad():
        return torch.cat([model(batch).argmax(dim=1) for batch in encoded.split(64)]).tolist()
