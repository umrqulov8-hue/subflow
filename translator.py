import re
import deepl
from deep_translator import GoogleTranslator

DEEPL_KEY = "bb3594bb-7228-42e8-892a-6c2b2b85c92e:fx"
deepl_translator = deepl.Translator(DEEPL_KEY)

LANG_MAP = {
    'auto': None,
    'en': 'EN',
    'ru': 'RU',
    'uz': 'UZ',
    'tr': 'TR',
    'de': 'DE',
    'fr': 'FR',
    'es': 'ES',
    'ar': 'AR',
    'zh': 'ZH',
    'ko': 'KO',
}

def translate_text(text: str, source: str = "auto", target: str = "uz") -> str:
    try:
        deepl_target = LANG_MAP.get(target, target.upper())
        if deepl_target and deepl_target != source.upper():
            result = deepl_translator.translate_text(text, target_lang=deepl_target)
            return str(result)
    except Exception:
        pass

    return GoogleTranslator(source=source if source != "auto" else "auto", target=target).translate(text)


def translate_srt(content: str, source: str = "auto", target: str = "uz") -> str:
    lines = content.split("\n")
    result = []
    for line in lines:
        if re.match(r"^\d+$", line.strip()):
            result.append(line)
        elif "-->" in line:
            result.append(line)
        elif line.strip() == "":
            result.append("")
        else:
            result.append(translate_text(line.strip(), source, target))
    return "\n".join(result)


def translate_ass(content: str, source: str = "auto", target: str = "uz") -> str:
    lines = content.split("\n")
    result = []
    for line in lines:
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            if len(parts) == 10:
                parts[9] = translate_text(parts[9], source, target)
                result.append(",".join(parts))
            else:
                result.append(line)
        else:
            result.append(line)
    return "\n".join(result)
