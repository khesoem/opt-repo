import subprocess
import sys
from typing import List

def run_cmd(cmd: str, path: str, args: List[str]) -> str:
    try:
        result = subprocess.run(
            [cmd] + args,
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr or str(e) + "\n")
        raise
    return result.stdout

def add_test_wise_plugin(pom_path: str) -> None:
    """
    Add the TestWise plugin to the Maven POM file.
    """
    try:
        with open(pom_path, 'r') as file:
            pom_content = file.read()

        if '<artifactId>testwise-maven-plugin</artifactId>' in pom_content:
            return  # Plugin already exists

        # Insert the plugin into the POM
        plugin_xml = """
        <plugin>
            <groupId>com.testwise</groupId>
            <artifactId>testwise-maven-plugin</artifactId>
            <version>1.0.0</version>
        </plugin>
        """
        pom_content = pom_content.replace('</plugins>', f'{plugin_xml}\n</plugins>')

        with open(pom_path, 'w') as file:
            file.write(pom_content)

    except Exception as e:
        sys.stderr.write(f"Error adding TestWise plugin: {e}\n")