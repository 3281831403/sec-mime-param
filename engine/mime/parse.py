"""MIME Content-Type parameter parsing.

The implementations below fix the ten parsing defects in the order given in
the task description; the defect number is noted next to each fix.
"""

# RFC 2045 token characters (parameter names and media-type pieces).
_TOKEN_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "!#$%&'*+-.^_`|~"
)
# Media types are tokens joined by a slash.
_TYPE_CHARS = _TOKEN_CHARS | frozenset("/")


# Defect 1: the main type must be normalized to lowercase so case variants
# such as Text/HTML and text/HTML are treated as the same kind.
def split_type(text: str) -> str:
    """Return the media type before the first semicolon, lowercased."""
    media_type, _, _ = text.partition(";")
    return media_type.strip().lower()


# Defect 3: semicolons inside double quotes belong to the value and must not
# be used as parameter separators; empty fragments are dropped.
def tokenize_params(text: str) -> list:
    """Split a header into parameter tokens, honoring quoted semicolons."""
    segments = []
    current = []
    in_quotes = False
    escaped = False
    for ch in text:
        if in_quotes:
            current.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                # Defect 4 (tokenizing side): an escaped quote must not
                # close the quoted string.
                escaped = True
            elif ch == '"':
                in_quotes = False
        elif ch == '"':
            in_quotes = True
            current.append(ch)
        elif ch == ";":
            segments.append("".join(current))
            current = []
        else:
            current.append(ch)
    segments.append("".join(current))

    # The segment before the first semicolon is the media type, not a
    # parameter; when there is no semicolon it is the only segment.
    segments = segments[1:]
    return [token.strip() for token in segments if token.strip()]


# Defect 4: backslash escapes are decoded inside quoted values, so an
# escaped quote cannot terminate the value early.
# Defect 5: a value that opens a quote but never closes it is an error
# rather than being silently truncated at end of string.
def unquote_value(value: str) -> str:
    """Remove surrounding quotes and decode backslash escapes."""
    if not value or value[0] != '"':
        # Unquoted values pass through untouched.
        return value

    i = 1
    closed = False
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            # Skip the escaped character so an escaped quote cannot close.
            i += 2
            continue
        if ch == '"':
            closed = True
            break
        i += 1
    if not closed:
        raise ValueError("unclosed quote")

    inner = value[1:i]
    decoded = []
    j = 0
    while j < len(inner):
        ch = inner[j]
        if ch == "\\" and j + 1 < len(inner):
            # Backslash quotes the next character: \\" -> ", \\\\ -> \\.
            decoded.append(inner[j + 1])
            j += 2
        else:
            decoded.append(ch)
            j += 1
    return "".join(decoded)


# Defect 2: parameter names are lowercased before lookup.
# Defect 6: duplicate names keep the first occurrence.
# Defect 7: an empty value after '=' is kept as an empty string.
def parse_params(tokens: list) -> dict:
    """Parse parameter tokens into a dictionary with lowercase names."""
    params = {}
    for token in tokens:
        name, separator, raw_value = token.partition("=")
        if not separator:
            raise ValueError(f"parameter without '=': {token!r}")
        name = name.strip().lower()
        if name not in params:
            # First occurrence wins; later duplicates are ignored.
            params[name] = unquote_value(raw_value)
    return params


# Defect 8: name*0, name*1, ... segments are ordered by number and joined;
# the numbering must start at 0 with no gaps.
def parse_continutation(tokens: list) -> dict:
    """Join numbered continuation parameters, rejecting gaps."""
    groups: dict = {}
    for token in tokens:
        name, separator, raw_value = token.partition("=")
        if not separator:
            raise ValueError(f"parameter without '=': {token!r}")
        base, star, suffix = name.strip().partition("*")
        if not star or not suffix.isdigit():
            raise ValueError(f"not a continuation parameter: {token!r}")
        groups.setdefault(base, {})[int(suffix)] = unquote_value(raw_value)

    joined = {}
    for base, parts in groups.items():
        indexes = sorted(parts)
        if indexes != list(range(len(indexes))):
            raise ValueError(f"gap in continuation numbering for {base!r}")
        joined[base] = "".join(parts[index] for index in indexes)
    return joined


# Defect 9: the default charset comes from the policy for the exact
# (case-insensitive) media type; unknown types raise instead of getting a
# single shared fallback value.
def default_charset(media_type: str, policy) -> str:
    """Return the policy charset for a media type."""
    key = media_type.lower()
    try:
        return policy[key]
    except KeyError:
        raise ValueError(f"no default charset for media type {media_type!r}")


def validate(text: str) -> list[str]:
    """Return a list of problems found in a Content-Type header."""
    problems = []

    media_type, _, _ = text.partition(";")
    media_type = media_type.strip()
    if not media_type:
        problems.append("empty type")
    elif any(ch not in _TYPE_CHARS for ch in media_type):
        problems.append("illegal character")

    for token in tokenize_params(text):
        param_name = token.split("=", 1)[0].strip()
        if any(ch not in _TOKEN_CHARS for ch in param_name):
            problems.append("illegal character")

    # Defect 5 (validation side): an unescaped opening quote with no
    # matching closing quote is reported, never swallowed.
    in_quotes = False
    escaped = False
    for ch in text:
        if in_quotes:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_quotes = False
        elif ch == '"':
            in_quotes = True
    if in_quotes:
        problems.append("unclosed quote")

    return problems


# Defect 10: every header is parsed independently with a fresh parameter
# dict, so later items never inherit parameters from earlier ones.
def mime_batch(texts, policy) -> dict:
    """Parse several Content-Type headers independently."""
    result = {}
    for text in texts:
        params = parse_params(tokenize_params(text))
        media_type = split_type(text)
        if "charset" in params:
            charset = params["charset"]
        else:
            charset = default_charset(media_type, policy)
        result[text] = {
            "media_type": media_type,
            "params": params,
            "charset": charset,
        }
    return result
