#!/usr/bin/env python3
"""
Hardcoded POM modifier:
- Adds/replaces <profile id="tia"> with fixed content.
- Ensures test deps:
    * org.junit.jupiter:junit-jupiter (scope=test, no version)
    * com.teamscale:impacted-test-engine:35.2.2 (scope=test)
- Writes backup next to the pom: pom.xml.bak
Usage:
  python3 add_tia_profile.py /path/to/pom.xml
"""

from __future__ import annotations
import sys
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

# ---- Hardcoded values ----
PROFILE_ID = "tia"
SUREFIRE_VERSION = "3.2.5"
TEAMSCALE_PLUGIN_VERSION = "35.2.2"
IMPACTED_ENGINE_VERSION = "35.2.2"

# ---------- XML helpers ----------

def detect_namespace(root: ET.Element) -> str:
    if root.tag.startswith("{") and "}" in root.tag:
        return root.tag.split("}", 1)[0][1:]
    return ""

def qname(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}" if ns else tag

def pretty_write(tree: ET.ElementTree, path: Path, ns: str) -> None:
    try:
        if ns:
            ET.register_namespace('', ns)
        indent = getattr(ET, "indent", None)
        if callable(indent):  # Python 3.9+
            indent(tree, space="  ")
        tree.write(path, encoding="utf-8", xml_declaration=True)
    except Exception:
        tree.write(path, encoding="utf-8", xml_declaration=True)

# -------- Profile handling --------

def get_or_create_profiles(root: ET.Element, ns: str) -> ET.Element:
    profiles = root.find(qname(ns, "profiles"))
    if profiles is None:
        profiles = ET.SubElement(root, qname(ns, "profiles"))
    return profiles

def remove_existing_profile(profiles: ET.Element, ns: str, profile_id: str) -> None:
    for prof in list(profiles.findall(qname(ns, "profile"))):
        pid = prof.find(qname(ns, "id"))
        if pid is not None and (pid.text or "").strip() == profile_id:
            profiles.remove(prof)

def add_tia_profile(profiles: ET.Element, ns: str) -> None:
    profile = ET.SubElement(profiles, qname(ns, "profile"))
    ET.SubElement(profile, qname(ns, "id")).text = PROFILE_ID

    activation = ET.SubElement(profile, qname(ns, "activation"))
    prop = ET.SubElement(activation, qname(ns, "property"))
    ET.SubElement(prop, qname(ns, "name")).text = PROFILE_ID

    build = ET.SubElement(profile, qname(ns, "build"))
    plugins = ET.SubElement(build, qname(ns, "plugins"))

    # maven-surefire-plugin
    p_sf = ET.SubElement(plugins, qname(ns, "plugin"))
    ET.SubElement(p_sf, qname(ns, "groupId")).text = "org.apache.maven.plugins"
    ET.SubElement(p_sf, qname(ns, "artifactId")).text = "maven-surefire-plugin"
    ET.SubElement(p_sf, qname(ns, "version")).text = SUREFIRE_VERSION
    cfg_sf = ET.SubElement(p_sf, qname(ns, "configuration"))
    ET.SubElement(cfg_sf, qname(ns, "forkCount")).text = "1"
    ET.SubElement(cfg_sf, qname(ns, "threadCount")).text = "1"
    ET.SubElement(cfg_sf, qname(ns, "argLine")).text = "${surefireArgLine}"

    # teamscale-maven-plugin
    p_ts = ET.SubElement(plugins, qname(ns, "plugin"))
    ET.SubElement(p_ts, qname(ns, "groupId")).text = "com.teamscale"
    ET.SubElement(p_ts, qname(ns, "artifactId")).text = "teamscale-maven-plugin"
    ET.SubElement(p_ts, qname(ns, "version")).text = TEAMSCALE_PLUGIN_VERSION

    execs = ET.SubElement(p_ts, qname(ns, "executions"))

    ex1 = ET.SubElement(execs, qname(ns, "execution"))
    ET.SubElement(ex1, qname(ns, "id")).text = "teamscale-prepare-unit"
    ET.SubElement(ex1, qname(ns, "phase")).text = "initialize"
    goals1 = ET.SubElement(ex1, qname(ns, "goals"))
    ET.SubElement(goals1, qname(ns, "goal")).text = "prepare-tia-unit-test"
    ET.SubElement(ex1, qname(ns, "inherited")).text = "false"

    ex2 = ET.SubElement(execs, qname(ns, "execution"))
    ET.SubElement(ex2, qname(ns, "id")).text = "teamscale-report"
    ET.SubElement(ex2, qname(ns, "phase")).text = "verify"
    goals2 = ET.SubElement(ex2, qname(ns, "goals"))
    ET.SubElement(goals2, qname(ns, "goal")).text = "testwise-coverage-report"
    ET.SubElement(ex2, qname(ns, "inherited")).text = "false"

    cfg_ts = ET.SubElement(p_ts, qname(ns, "configuration"))
    ET.SubElement(cfg_ts, qname(ns, "propertyName")).text = "surefireArgLine"
    ET.SubElement(cfg_ts, qname(ns, "runImpacted")).text = "false"
    ET.SubElement(cfg_ts, qname(ns, "runAllTests")).text = "true"

# ------ Dependency handling ------

def find_dependency_anywhere(root: ET.Element, ns: str, group_id: str, artifact_id: str) -> ET.Element | None:
    """Return the first <dependency> element with matching GA anywhere in the POM."""
    for dep in root.iter(qname(ns, "dependency")):
        gid = dep.find(qname(ns, "groupId"))
        aid = dep.find(qname(ns, "artifactId"))
        if gid is not None and aid is not None:
            if (gid.text or "").strip() == group_id and (aid.text or "").strip() == artifact_id:
                return dep
    return None

def get_or_create_root_dependencies(root: ET.Element, ns: str) -> ET.Element:
    """Get or create the <project>/<dependencies> (not dependencyManagement)."""
    deps = root.find(qname(ns, "dependencies"))
    if deps is None:
        deps = ET.SubElement(root, qname(ns, "dependencies"))
    return deps

def ensure_dependency(root: ET.Element, ns: str, group_id: str, artifact_id: str,
                      version: str | None, scope: str | None) -> bool:
    """
    Ensure a dependency exists (by GA) anywhere in the POM. If not found, add it under
    <project>/<dependencies>. Returns True if added, False if already present.
    """
    if find_dependency_anywhere(root, ns, group_id, artifact_id) is not None:
        return False
    deps = get_or_create_root_dependencies(root, ns)
    dep = ET.SubElement(deps, qname(ns, "dependency"))
    ET.SubElement(dep, qname(ns, "groupId")).text = group_id
    ET.SubElement(dep, qname(ns, "artifactId")).text = artifact_id
    if version:
        ET.SubElement(dep, qname(ns, "version")).text = version
    if scope:
        ET.SubElement(dep, qname(ns, "scope")).text = scope
    return True

# ------ GroupId resolution ------

def resolve_group_id(root: ET.Element, ns: str) -> str | None:
    """Return this POM's <groupId>, or fall back to <parent>/<groupId> if missing."""
    gid_el = root.find(qname(ns, "groupId"))  # direct child of <project>
    if gid_el is not None and gid_el.text and gid_el.text.strip():
        return gid_el.text.strip()
    parent = root.find(qname(ns, "parent"))
    if parent is not None:
        pgid = parent.find(qname(ns, "groupId"))
        if pgid is not None and pgid.text and pgid.text.strip():
            return pgid.text.strip()
    return None

# --------------- POM modification ---------------

def add_tia_to_pom(pom_path: str) -> None:
    # Parse and modify
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise f"ERROR: Failed to parse XML: {e}"

    ns = detect_namespace(root)

    group_id = resolve_group_id(root, ns)

    # Profiles
    profiles_el = get_or_create_profiles(root, ns)
    remove_existing_profile(profiles_el, ns, PROFILE_ID)
    add_tia_profile(profiles_el, ns)

    # Dependencies
    # ensure_dependency(
    #     root, ns,
    #     group_id="org.junit.jupiter",
    #     artifact_id="junit-jupiter",
    #     version=None,
    #     scope="test",
    # )
    ensure_dependency(
        root, ns,
        group_id="com.teamscale",
        artifact_id="impacted-test-engine",
        version=IMPACTED_ENGINE_VERSION,
        scope="test",
    )

    # Write back
    pretty_write(tree, pom_path, ns)

if __name__ == "__main__":
    add_tia_to_pom("/home/khesoem/postdoc-eth/projects/optimization-dataset/code/tmp/quarkus/independent-projects/qute/core/pom.xml")
