"""Naive Bayes classifiers for toxic comment detection."""
from sklearn.naive_bayes import MultinomialNB, ComplementNB
from sklearn.pipeline import Pipeline


class ToxicNaiveBayes:
    """Wrapper for Naive Bayes classification with imbalanced-data support."""

    def __init__(self, alpha=1.0, algorithm='complement', fit_prior=True):
        self.alpha = alpha
        self.algorithm = algorithm
        self.fit_prior = fit_prior
        if algorithm == 'complement':
            # ComplementNB is specifically designed for imbalanced text classification (Rennie et al., 2003)
            self.classifier = ComplementNB(alpha=alpha, norm=True)
        else:
            self.classifier = MultinomialNB(alpha=alpha, fit_prior=fit_prior)

    def fit(self, X, y):
        return self.classifier.fit(X, y)

    def predict(self, X):
        return self.classifier.predict(X)

    def predict_proba(self, X):
        return self.classifier.predict_proba(X)


def create_nb_classifier(alpha=1.0, algorithm='complement'):
    """Create a configured Naive Bayes classifier instance (defaults to ComplementNB for imbalanced data)."""
    if algorithm == 'complement':
        return ComplementNB(alpha=alpha, norm=True)
    return MultinomialNB(alpha=alpha)


def build_nb_pipeline(vectorizer, alpha=1.0, algorithm='complement'):
    """Create an end-to-end Pipeline combining text/icon vectorizer with Naive Bayes."""
    clf = create_nb_classifier(alpha=alpha, algorithm=algorithm)
    return Pipeline([
        ('vectorizer', vectorizer),
        ('classifier', clf)
    ])
