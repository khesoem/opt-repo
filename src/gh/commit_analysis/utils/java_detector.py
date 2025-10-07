#!/usr/bin/env python3
import logging
import re
from pathlib import Path
import xml.etree.ElementTree as ET

DEFAULT_JAVA_VERSION = 24

# -------- helpers --------
INT_RE = re.compile(r"\b([1-9][0-9])\b")  # matches 10..99

def first_int(txt):
    if not txt:
        return None
    m = INT_RE.search(str(txt))
    return int(m.group(1)) if m else None

def parse_range(ver):
    """Accepts things like [21,), [17,21], (17,] or '21'. Returns the lower bound."""
    if not ver:
        return None
    m = re.match(r"[\[\(]\s*([0-9]+)", ver.strip())
    if m:
        return int(m.group(1))
    return first_int(ver)

def read_xml(path: Path):
    try:
        return ET.parse(path).getroot()
    except Exception:
        return None

def nsmap(root):
    return {"m": root.tag.split("}")[0].strip("{")} if root is not None and root.tag.startswith("{") else {}

def find(root, path, ns):
    if ns:
        path = "/".join(f"m:{p}" for p in path.split("/"))
        return root.find(path, ns)
    return root.find(path)

def findall(root, path, ns):
    if ns:
        path = "/".join(f"m:{p}" for p in path.split("/"))
        return root.findall(path, ns)
    return root.findall(path)

def text(el):
    return (el.text or "").strip() if el is not None and el.text else None

def load_pom_chain(start: Path):
    """Load current pom and follow <parent><relativePath> (or ../pom.xml by default)."""
    chain = []
    seen = set()
    cur = start
    while cur and cur.exists():
        if cur.resolve() in seen:
            break
        seen.add(cur.resolve())
        root = read_xml(cur)
        if root is None:
            break
        chain.append((cur, root))
        ns = nsmap(root)
        parent = find(root, "parent", ns)
        if parent is None:
            break
        rel = text(find(parent, "relativePath", ns)) or "../pom.xml"
        nxt = (cur.parent / rel).resolve()
        if nxt == cur or not nxt.exists():
            break
        cur = nxt
    return chain  # [ (path, root), child first -> parent last ]

def collect_properties(chain):
    """Merge <properties> from child to parents (child overrides)."""
    props = {}
    for _, root in reversed(chain):  # parents first
        ns = nsmap(root)
        props_el = find(root, "properties", ns)
        if props_el is not None:
            for p in list(props_el):
                if p.tag.endswith("}properties"):  # paranoia
                    continue
                key = p.tag.split("}", 1)[-1]
                val = text(p)
                if val is not None:
                    props.setdefault(key, val)
    # finally child-most overrides
    for _, root in chain:
        ns = nsmap(root)
        props_el = find(root, "properties", ns)
        if props_el is not None:
            for p in list(props_el):
                key = p.tag.split("}", 1)[-1]
                val = text(p)
                if val is not None:
                    props[key] = val
    return props

def resolve_props(val, props, depth=0):
    if val is None:
        return None
    # simple ${prop} substitution (no recursion through parents of parents)
    out = str(val)
    # avoid infinite recursion
    for _ in range(5):
        changed = False
        for m in re.findall(r"\$\{([^}]+)\}", out):
            rep = props.get(m)
            if rep is not None:
                out2 = out.replace("${"+m+"}", str(rep))
                if out2 != out:
                    out = out2
                    changed = True
        if not changed:
            break
    return out

def read_enforcer_java(root, props):
    ns = nsmap(root)
    for p in findall(root, "build/plugins/plugin", ns):
        gid = text(find(p, "groupId", ns)) or ""
        aid = text(find(p, "artifactId", ns)) or ""
        if gid == "org.apache.maven.plugins" and aid == "maven-enforcer-plugin":
            # look in both <executions> and direct <configuration>
            execs = findall(p, "executions/execution", ns)
            blocks = execs + [p]
            for b in blocks:
                rules_parent = find(b, "configuration/rules", ns)
                if rules_parent is None:
                    continue
                for r in list(rules_parent):
                    if r.tag.endswith("RequireJavaVersion"):
                        v = resolve_props(text(find(r, "version", ns)), props)
                        j = parse_range(v)
                        if j:
                            return j
    return None

def read_compiler_java(root, props):
    ns = nsmap(root)
    for p in findall(root, "build/plugins/plugin", ns):
        gid = text(find(p, "groupId", ns)) or ""
        aid = text(find(p, "artifactId", ns)) or ""
        if gid == "org.apache.maven.plugins" and aid == "maven-compiler-plugin":
            rel = resolve_props(text(find(p, "configuration/release", ns)), props)
            if rel:
                j = first_int(rel)
                if j:
                    return j
            tgt = resolve_props(text(find(p, "configuration/target", ns)), props)
            if tgt:
                j = first_int(tgt)
                if j:
                    return j
    return None

def detect_java_version(pom_path: Path):
    chain = load_pom_chain(pom_path)
    if not chain:
        return None
    props = collect_properties(chain)

    # 1) enforcer in child→parent order
    for _, root in chain:
        j = read_enforcer_java(root, props)
        if j:
            return j

    # 2) compiler plugin in child→parent order
    for _, root in chain:
        j = read_compiler_java(root, props)
        if j:
            return j

    # 3) properties fallback
    for key in ("maven.compiler.release", "maven.compiler.target"):
        val = resolve_props(props.get(key), props)
        j = first_int(val)
        if j:
            return j

    return None

def get_java_version(repo_path: Path):
    pom = repo_path / "pom.xml"
    if not pom.exists():
        logging.error(f"pom.xml not found in {repo_path}")
        return DEFAULT_JAVA_VERSION
    j = detect_java_version(pom)
    if not j:
        logging.error(f"Could not determine Java version for {repo_path}. Consider adding an enforcer RequireJavaVersion or compiler <release>.")
        return DEFAULT_JAVA_VERSION
    return j

if __name__ == "__main__":
    print(get_java_version(Path("/zdata/ketemadi/projects/opt/tmp/wildfly")))
