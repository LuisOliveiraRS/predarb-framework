from pathlib import Path


def test_requirements_is_utf8_and_has_no_duplicate_package_names():
    path = Path("requirements.txt")
    text = path.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    package_names = [
        line.split("==", 1)[0].strip().lower()
        for line in lines
    ]

    assert len(package_names) == len(set(package_names))
    assert "\x00" not in text
