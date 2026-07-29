from difflib import SequenceMatcher


class SimilarityEngine:
    """
    Calcula similaridade entre textos.
    """

    def score(self, text_a, text_b):

        return SequenceMatcher(

            None,

            text_a,

            text_b

        ).ratio()


similarity_engine = SimilarityEngine()