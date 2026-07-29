import unicodedata

from app.market.synonyms import SYNONYMS
from app.market.stopwords import STOPWORDS
from app.market.tokenizer import tokenizer


class Normalizer:

    def normalize(self, text):

        text = text.lower()

        text = unicodedata.normalize(
            "NFKD",
            text
        ).encode(
            "ascii",
            "ignore"
        ).decode()

        tokens = tokenizer.tokenize(text)

        normalized = []

        for token in tokens:

            if token in STOPWORDS:
                continue

            token = SYNONYMS.get(
                token,
                token
            )

            normalized.append(token)

        return " ".join(normalized)


normalizer = Normalizer()