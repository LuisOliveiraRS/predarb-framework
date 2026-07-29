import re


class Tokenizer:

    def tokenize(self, text: str):

        text = text.lower()

        return re.findall(r"\w+", text)


tokenizer = Tokenizer()