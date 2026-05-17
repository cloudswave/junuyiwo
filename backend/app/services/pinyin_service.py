"""
Pinyin annotation service using pypinyin for accurate polyphone-aware pinyin.
"""
import re
import jieba
from pypinyin import lazy_pinyin, Style


def get_pinyin(char: str) -> str:
    """Get pinyin for a single Chinese character."""
    result = lazy_pinyin(char, style=Style.TONE)
    return result[0] if result else ""


def annotate_text(text: str) -> list[dict]:
    """
    Annotate Chinese text with pinyin + word boundaries.
    Returns a list of paragraphs, each paragraph is a list of {char, pinyin, word_len} dicts.
    word_len > 0 indicates the start of a multi-char word, giving its length.
    Non-Chinese characters get empty pinyin.
    """
    # Strip existing "汉字(pinyin)" patterns from AI-generated text
    text = re.sub(r'[一-鿿]\([a-zA-Z]+\)', lambda m: m.group(0)[0], text)

    paragraphs = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        # jieba word segmentation for this line
        words = list(jieba.cut(line))

        # Build char-index → word reference
        # For each CJK word (len>1), mark its start char with word_len
        char_pos = 0
        word_marks: dict[int, int] = {}  # char_pos → word_len (only for multi-char words)
        for w in words:
            w_len = len(w)
            if w_len >= 2 and '一' <= w[0] <= '鿿':
                word_marks[char_pos] = w_len
            char_pos += w_len

        chars = list(line)
        chinese_chars = [c for c in chars if '一' <= c <= '鿿']
        chinese_pinyin = lazy_pinyin(chinese_chars, style=Style.TONE)

        py_idx = 0
        tokens = []
        for i, c in enumerate(chars):
            if '一' <= c <= '鿿':
                wl = word_marks.get(i, 0)
                tokens.append({"char": c, "pinyin": chinese_pinyin[py_idx], "word_len": wl})
                py_idx += 1
            elif c in '，。！？、；：""''（）《》…—\n\r':
                tokens.append({"char": c, "pinyin": "", "word_len": 0})
            elif c.isspace() or c in '· 　':
                pass  # skip soft space
            else:
                tokens.append({"char": c, "pinyin": "", "word_len": 0})
        if tokens:
            paragraphs.append(tokens)

    return paragraphs


def annotate_article(article_content: str) -> dict:
    """
    Take article content (which may contain AI-generated pinyin),
    strip inaccurate pinyin, re-annotate with pypinyin, and return structured data.
    """
    paragraphs = annotate_text(article_content)
    return {
        "paragraphs": paragraphs,
        "total_chars": sum(len([t for t in p if t["pinyin"]]) for p in paragraphs),
    }


def annotate_characters(characters: list[str]) -> list[dict]:
    """Annotate a list of characters with their pinyin."""
    result = []
    pinyins = lazy_pinyin(characters, style=Style.TONE)
    for char, py in zip(characters, pinyins):
        result.append({"character": char, "pinyin": py})
    return result
