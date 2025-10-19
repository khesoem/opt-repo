#!/usr/bin/env python3
"""
Detect the Java version for a Maven (mvnw) repository.

Heuristics (in priority order):
1) .mvn/jvm.config      -> --release/--target/--source
2) pom.xml properties   -> maven.compiler.release / maven.compiler.target / maven.compiler.source / java.version
3) pom.xml plugin config-> maven-compiler-plugin <configuration><release|target|source>
4) .java-version        -> e.g., "17.0.8", "temurin-17.0.8", etc.
5) .sdkmanrc            -> line like: java=17.0.8-tem
Fallback default: "24"

Returns a major version string like "17" or "24".
"""

from __future__ import annotations
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Optional, Dict

DEFAULT_JAVA = "24"

# ------------------------ helpers ------------------------

_DIGITS = re.compile(r"\d+")

def _major_from_version_string(s: str) -> Optional[str]:
    """
    Extract the Java *major* version from a string.
    Examples:
      "17" -> "17"
      "17.0.7" -> "17"
      "1.8" -> "8"
      "temurin-17.0.9" -> "17"
      "${java.version}" -> None (caller should expand first)
    """
    if not s:
        return None
    s = s.strip()

    # Old "1.8" style
    if s.startswith("1."):
        # "1.8", "1.7" -> 8, 7
        parts = s.split(".")
        if len(parts) >= 2 and parts[1].isdigit():
            return parts[1]
        # fallback to first digits
    # Generic: take the first integer sequence
    m = _DIGITS.search(s)
    if not m:
        return None
    return m.group(0)


def _read_text_file(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _expand_properties(value: str, props: Dict[str, str]) -> str:
    """
    Expand ${...} placeholders using provided props (one pass).
    """
    if not value:
        return value

    def repl(m):
        key = m.group(1)
        return props.get(key, m.group(0))  # leave unresolved refs as-is

    return re.sub(r"\$\{([^}]+)\}", repl, value)


# ------------------------ jvm.config ------------------------

def _from_jvm_config(repo: Path) -> Optional[str]:
    cfg = repo / ".mvn" / "jvm.config"
    txt = _read_text_file(cfg)
    if not txt:
        return None

    # Look for --release N first, then --target N, then --source N
    # Accept formats like: --release 17, --release=17
    patterns = [
        r"--release(?:\s+|=)(\d+)",
        r"--target(?:\s+|=)(\d+)",
        r"--source(?:\s+|=)(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, txt)
        if m:
            return m.group(1)
    return None


# ------------------------ pom.xml parsing ------------------------

def _strip_ns(elem: ET.Element) -> None:
    """In-place strip XML namespaces for simpler tag access."""
    for e in elem.iter():
        if "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]

def _collect_properties(pom_root: ET.Element) -> Dict[str, str]:
    props: Dict[str, str] = {}
    props_elem = pom_root.find("properties")
    if props_elem is not None:
        for child in list(props_elem):
            # e.g., <java.version>17</java.version>
            tag = child.tag
            text = (child.text or "").strip()
            if tag and text:
                props[tag] = text
    # Common Maven implicit props can exist, but we only handle user-defined ones here.
    # Mirror some common aliases to improve hit rate:
    for alias, keys in {
        "maven.compiler.release": ["maven.compiler.release"],
        "maven.compiler.target":  ["maven.compiler.target"],
        "maven.compiler.source":  ["maven.compiler.source"],
        "java.version":           ["java.version"],
    }.items():
        for k in keys:
            if alias not in props and k in props:
                props[alias] = props[k]
    return props

def _read_pom(repo: Path) -> Optional[ET.Element]:
    pom = repo / "pom.xml"
    if not pom.exists():
        return None
    try:
        root = ET.fromstring(pom.read_text(encoding="utf-8"))
        _strip_ns(root)
        return root
    except Exception:
        return None

def _resolve_from_pom_properties(root: ET.Element) -> Optional[str]:
    props = _collect_properties(root)
    for key in ("maven.compiler.release", "maven.compiler.target", "maven.compiler.source", "java.version"):
        val = props.get(key)
        if not val:
            continue
        expanded = _expand_properties(val, props)
        major = _major_from_version_string(expanded)
        if major:
            return major
    return None

def _resolve_from_maven_compiler_plugin(root: ET.Element) -> Optional[str]:
    build = root.find("build")
    if build is None:
        return None
    plugins_parent = build.find("plugins")
    if plugins_parent is None:
        return None

    # Gather properties for placeholder expansion
    props = _collect_properties(root)

    for plugin in plugins_parent.findall("plugin"):
        aid = (plugin.findtext("artifactId") or "").strip()
        gid = (plugin.findtext("groupId") or "org.apache.maven.plugins").strip()  # default
        if aid == "maven-compiler-plugin" and gid.endswith("maven.plugins"):
            cfg = plugin.find("configuration")
            if cfg is None:
                continue
            for tag in ("release", "target", "source"):
                val = cfg.findtext(tag)
                if val:
                    expanded = _expand_properties(val.strip(), props)
                    major = _major_from_version_string(expanded)
                    if major:
                        return major
    return None


# ------------------------ other version files ------------------------

def _from_java_version_file(repo: Path) -> Optional[str]:
    # jenv/asdf/SDKman sometimes drop a ".java-version" file
    f = repo / ".java-version"
    txt = _read_text_file(f)
    if not txt:
        return None
    # Take first non-empty token
    token = txt.strip().split()[0]
    return _major_from_version_string(token)

def _from_sdkmanrc(repo: Path) -> Optional[str]:
    f = repo / ".sdkmanrc"
    txt = _read_text_file(f)
    if not txt:
        return None
    # Format: java=17.0.8-tem (or similar)
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("java="):
            val = line.split("=", 1)[1].strip()
            return _major_from_version_string(val)
    return None


# ------------------------ public API ------------------------

def get_java_version(repo_path: str | Path) -> str:
    """
    Return the project's Java major version as a string (e.g., "17").
    If undetectable, return the default "24".
    """
    repo = Path(repo_path)

    # 1) .mvn/jvm.config
    v = _from_jvm_config(repo)
    if v:
        return v

    # 2) pom.xml props
    root = _read_pom(repo)
    if root is not None:
        v = _resolve_from_pom_properties(root)
        if v:
            return v

        # 3) maven-compiler-plugin
        v = _resolve_from_maven_compiler_plugin(root)
        if v:
            return v

    # 4) .java-version
    v = _from_java_version_file(repo)
    if v:
        return v

    # 5) .sdkmanrc
    v = _from_sdkmanrc(repo)
    if v:
        return v

    # Fallback
    return DEFAULT_JAVA


# ------------------------ CLI ------------------------

def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(f"Usage: {argv[0]} /path/to/mvnw-repo")
        print(DEFAULT_JAVA)
        return 0
    print(get_java_version(argv[1]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
