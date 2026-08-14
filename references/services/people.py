import re

INSTITUTION_PREFIXES = ("instituição:", "instituicao:", "organização:", "organizacao:")


def parse_person(value: str) -> dict:
    value = re.sub(r"\s+", " ", (value or "").strip(" ;"))
    if not value:
        return {}

    lowered = value.casefold()
    for prefix in INSTITUTION_PREFIXES:
        if lowered.startswith(prefix):
            return {"literal": value.split(":", 1)[1].strip()}

    if value.startswith("{") and value.endswith("}"):
        return {"literal": value[1:-1].strip()}

    if "," in value:
        family, given = [part.strip() for part in value.split(",", 1)]
        return {"family": family, "given": given}

    particles = {"da", "das", "de", "do", "dos", "e", "van", "von", "del", "della"}
    parts = value.split()
    if len(parts) == 1:
        return {"family": parts[0], "given": ""}

    family_parts = [parts[-1]]
    index = len(parts) - 2
    while index >= 0 and parts[index].casefold() in particles:
        family_parts.insert(0, parts[index])
        index -= 1
    return {"family": " ".join(family_parts), "given": " ".join(parts[: index + 1])}


def parse_people(value) -> list[dict]:
    if not value:
        return []
    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            return [person for person in value if person]
        parts = value
    else:
        normalized = str(value).replace(" and ", ";").replace(" & ", ";")
        parts = re.split(r"[;\n]+", normalized)
    return [person for item in parts if (person := parse_person(str(item)))]


def people_to_input(people: list[dict]) -> str:
    lines = []
    for person in people or []:
        if person.get("literal"):
            lines.append(f"Instituição: {person['literal']}")
        else:
            lines.append(
                ", ".join(
                    filter(None, [person.get("family", ""), person.get("given", "")])
                )
            )
    return "\n".join(lines)


def initials(given: str, spaced: bool = False) -> str:
    letters = [
        part[0].upper() + "." for part in re.findall(r"[\wÀ-ÿ]+", given or "") if part
    ]
    return (" " if spaced else "").join(letters)
