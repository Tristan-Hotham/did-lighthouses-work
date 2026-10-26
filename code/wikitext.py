"""Small helpers for turning Wikipedia wikitext into plain text.

No external parser is used, so every rule is visible here.
"""
import re

SHIP_PREFIX = {
    "SS", "HMS", "USS", "SMU", "GS", "MV", "SV", "PS", "HMT", "SMS", "RMS", "HMCS", "ORP", "HDMS",
    "USCGC", "HMAS", "HMNZS", "HMY", "TSS", "RMS", "USAT", "USNS", "FS", "HNLMS", "HNoMS", "HSwMS",
    "ARA", "KD", "INS", "MS", "NS", "SY", "HMSAS", "HMIS", "HMHS", "LÉ", "HMQS", "HMVS", "USRC",
    "HMSO", "HMBS", "HMRC", "HMPS", "RFA", "SMY", "HSMS", "TS", "SSS", "MY",
}

_COUNTRY_CODES = {
    "UKGBI": "United Kingdom", "UK": "United Kingdom", "GBR": "United Kingdom",
    "Kingdom of Great Britain": "Great Britain", "USA": "United States", "US": "United States",
    "Kingdom of Ireland": "Ireland", "United Kingdom of Great Britain and Ireland": "United Kingdom",
}


def country(name):
    name = name.strip()
    return _COUNTRY_CODES.get(name, name)


def split_params(body):
    """Split a template body on top-level pipes (not inside {{ }} or [[ ]])."""
    parts, depth_t, depth_l, cur, i = [], 0, 0, [], 0
    while i < len(body):
        two = body[i:i + 2]
        if two == "{{":
            depth_t += 1; cur.append(two); i += 2; continue
        if two == "}}":
            depth_t -= 1; cur.append(two); i += 2; continue
        if two == "[[":
            depth_l += 1; cur.append(two); i += 2; continue
        if two == "]]":
            depth_l -= 1; cur.append(two); i += 2; continue
        ch = body[i]
        if ch == "|" and depth_t == 0 and depth_l == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts


def _template_text(inner):
    """Plain-text rendering of one innermost template (no nested braces)."""
    parts = [p.strip() for p in inner.split("|")]
    name = parts[0].strip()
    lname = name.lower()
    pos = [p for p in parts[1:] if "=" not in p]
    if name in SHIP_PREFIX or name.upper() in SHIP_PREFIX:
        return (name + " " + pos[0]) if pos else name
    if lname in ("ship", "shipindex"):
        return " ".join(pos[:2])
    if lname in ("sclass", "sclass2", "sclass-"):
        return (pos[0] + " class") if pos else ""
    if lname in ("flag", "flagcountry", "flagu", "flagdeco", "flag country"):
        return country(pos[0]) if pos else ""
    if lname == "flagicon":
        return ""
    if lname in ("convert", "cvt"):
        return " ".join(pos[:2])
    if lname in ("lang", "langx", "transl", "transliteration"):
        return pos[-1] if pos else ""
    if lname.startswith("lang-"):
        return pos[0] if pos else ""
    if lname in ("nowrap", "nobr", "not a typo", "proper name", "small", "sic", "nwr", "visible anchor"):
        return pos[0] if pos else ""
    if lname in ("ill", "interlanguage link", "interlanguage link multi"):
        lt = [p.split("=", 1)[1] for p in parts[1:] if p.replace(" ", "").startswith("lt=")]
        return lt[0] if lt else (pos[0] if pos else "")
    if lname in ("nbsp", "snd", "spaced ndash", "ndash", "mdash"):
        return " "
    if lname in ("'", "' "):
        return "'"
    if lname in ("grt", "nrt", "dwt"):
        return (pos[0] + " " + name.upper()) if pos else name.upper()
    return ""


def plain(text):
    """Convert a snippet of wikitext to plain text."""
    t = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    t = re.sub(r"<ref[^>]*/\s*>", "", t, flags=re.S | re.I)
    t = re.sub(r"<ref[^>]*>.*?</ref\s*>", "", t, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    # innermost templates first, repeatedly
    for _ in range(12):
        new = re.sub(r"\{\{([^{}]*)\}\}", lambda m: _template_text(m.group(1)), t)
        if new == t:
            break
        t = new
    t = re.sub(r"\[\[(?:File|Image):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", "", t, flags=re.I)
    t = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[\[:?[a-z]{2,3}:([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[\[([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", t)
    t = re.sub(r"\[https?://\S+\]", "", t)
    t = t.replace("'''", "").replace("''", "")
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&ndash;", "-").replace("&mdash;", ",")
    # never carry long dashes into our derived text
    t = t.replace("—", ", ").replace("–", "-")
    t = re.sub(r"\(\s*\)", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([,.;:])", r"\1", t)
    return t


def extract_templates(text, start_pat):
    """Yield (start, end, body) for every balanced template beginning with start_pat."""
    for m in re.finditer(start_pat, text):
        i = m.start()
        depth, j = 0, i
        n = len(text)
        while j < n:
            if text.startswith("{{", j):
                depth += 1; j += 2; continue
            if text.startswith("}}", j):
                depth -= 1; j += 2
                if depth == 0:
                    break
                continue
            j += 1
        yield i, j, text[i + 2:j - 2]
