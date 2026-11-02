"""Support Vector Machine (SVM) classifier for toxic comment detection."""
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline


class ToxicSVM:
    """Wrapper for Linear Support Vector Classification with balanced class weights."""

    def __init__(self, C=1.0, class_weight='balanced', max_iter=10000, random_state=42):
        self.C = C
        self.class_weight = class_weight
        self.max_iter = max_iter
        self.random_state = random_state
        self.classifier = LinearSVC(
            C=C,
            class_weight=class_weight,
            max_iter=max_iter,
            random_state=random_state
        )

    def fit(self, X, y):
        return self.classifier.fit(X, y)

    def predict(self, X):
        return self.classifier.predict(X)

    def decision_function(self, X):
        return self.classifier.decision_function(X)


def create_svm_classifier(C=1.0, class_weight='balanced', max_iter=10000, random_state=42):
    """Create a configured LinearSVC classifier instance."""
    return LinearSVC(
        C=C,
        class_weight=class_weight,
        max_iter=max_iter,
        random_state=random_state
    )


def build_svm_pipeline(vectorizer, C=1.0, class_weight='balanced', max_iter=10000, random_state=42):
    """Create an end-to-end Pipeline combining text/icon vectorizer with LinearSVC."""
    return Pipeline([
        ('vectorizer', vectorizer),
        ('classifier', LinearSVC(
            C=C,
            class_weight=class_weight,
            max_iter=max_iter,
            random_state=random_state
        ))
    ])

